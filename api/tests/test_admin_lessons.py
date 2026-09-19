from typing import Any

import pytest
from sqlalchemy import select

from app.models import Job, Lesson, LessonStatus, Role, Segment
from tests.support import Harness, build_harness, make_settings, wav_bytes

FORM = {
    "title": "Scientists Study Sleep",
    "topic": "news",
    "level": "beginner",
    "source_name": "VOA Learning English",
    "source_url": "https://learningenglish.voanews.com/a/sleep",
    "license": "Public domain — VOA",
    "transcript": (
        "Scientists say the new study could change how we think about sleep. It was published today."
    ),
}


async def _admin(h: Harness) -> dict[str, str]:
    return {"X-CSRF-Token": await h.login("admin@example.com", Role.ADMIN)}


async def _upload(h: Harness, headers: dict[str, str], audio: bytes | None = None, **form: str) -> Any:
    files = {"audio": ("clip.wav", audio if audio is not None else wav_bytes(3), "audio/wav")}
    return await h.client.post("/api/v1/admin/lessons", data={**FORM, **form}, files=files, headers=headers)


def words(*spans: tuple[str, int, int]) -> list[dict[str, Any]]:
    return [{"word": w, "start_ms": s, "end_ms": e, "probability": 0.9} for w, s, e in spans]


async def _seed_review_lesson(h: Harness, status: str = LessonStatus.REVIEW) -> Lesson:
    """A lesson as the ingest pipeline leaves it: 3 aligned segments."""
    async with h.sessions() as db:
        lesson = Lesson(
            slug="seed",
            title="Seed",
            topic="news",
            level="beginner",
            source_name="VOA",
            license="Public domain",
            audio_key="audio/seed.wav",
            audio_mime="audio/wav",
            duration_ms=10_000,
            transcript="…",
            status=status,
        )
        lesson.segments = [
            Segment(
                idx=0,
                text="One two three",
                translation_vi="Một hai ba",
                start_ms=0,
                end_ms=3000,
                words=words(("One", 0, 900), ("two", 1000, 1900), ("three", 2000, 2900)),
            ),
            Segment(
                idx=1,
                text="Four five",
                translation_vi="Bốn năm",
                start_ms=3000,
                end_ms=6000,
                words=words(("Four", 3000, 4000), ("five", 4500, 5800)),
            ),
            Segment(
                idx=2,
                text="Six",
                translation_vi="Sáu",
                start_ms=6000,
                end_ms=9000,
                words=words(("Six", 6000, 8900)),
            ),
        ]
        db.add(lesson)
        await db.commit()
        return lesson


async def _detail(h: Harness, lesson_id: int) -> dict[str, Any]:
    res = await h.client.get(f"/api/v1/admin/lessons/{lesson_id}")
    assert res.status_code == 200
    return res.json()  # type: ignore[no-any-return]


async def test_upload_creates_processing_lesson_and_enqueues_ingest(harness: Harness) -> None:
    res = await _upload(harness, await _admin(harness))
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "processing"
    assert body["duration_ms"] == 3000
    assert body["slug"].startswith("scientists-study-sleep-")
    assert body["license"] == "Public domain — VOA"
    [(key, (data, mime))] = harness.storage.objects.items()
    assert key.startswith("audio/") and key.endswith(".wav") and mime == "audio/wav"
    assert body["audio_url"] == f"http://audio.test/{key}"
    async with harness.sessions() as db:
        job = (await db.execute(select(Job))).scalar_one()
    assert (job.type, job.payload) == ("ingest_lesson", {"lesson_id": body["id"]})


@pytest.mark.parametrize(
    ("audio", "form", "status"),
    [
        (b"just some text, not audio", {}, 422),
        (b"\x89PNG\r\n\x1a\n" + b"0" * 64, {}, 422),
        (None, {"transcript": "   "}, 422),
        (None, {"transcript": "x" * 20_001}, 422),
        (None, {"license": ""}, 422),
        (None, {"topic": "gossip"}, 422),
        (None, {"source_url": "not a url"}, 422),
    ],
)
async def test_upload_validation(
    harness: Harness, audio: bytes | None, form: dict[str, str], status: int
) -> None:
    res = await _upload(harness, await _admin(harness), audio, **form)
    assert res.status_code == status, res.text
    assert harness.storage.objects == {}


async def test_upload_limits_on_size_and_duration(sessions) -> None:  # type: ignore[no-untyped-def]
    h = build_harness(sessions, make_settings(max_audio_seconds=2, max_audio_bytes=100_000))
    async with h.client:
        headers = await _admin(h)
        assert (await _upload(h, headers, wav_bytes(3))).status_code == 422  # 3 s > 2 s
        assert (await _upload(h, headers, wav_bytes(1, rate=200_000))).status_code == 413  # 200 KB > 100 KB
        assert (await _upload(h, headers, wav_bytes(1))).status_code == 201


async def test_upload_requires_admin_and_csrf(harness: Harness) -> None:
    learner = {"X-CSRF-Token": await harness.login()}
    assert (await _upload(harness, learner)).status_code == 403
    await harness.login("admin@example.com", Role.ADMIN)
    assert (await _upload(harness, {})).status_code == 403


async def test_list_counts_segments_and_flags(harness: Harness) -> None:
    await _admin(harness)
    lesson = await _seed_review_lesson(harness)
    async with harness.sessions() as db:
        seg = (await db.execute(select(Segment).where(Segment.idx == 1))).scalar_one()
        seg.needs_attention = True
        await db.commit()
    [row] = (await harness.client.get("/api/v1/admin/lessons")).json()
    assert (row["id"], row["segment_count"], row["attention_count"]) == (lesson.id, 3, 1)


async def test_edit_segment_text_translation_and_timing(harness: Harness) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness)
    seg_id = (await _detail(harness, lesson.id))["segments"][1]["id"]
    res = await harness.client.patch(
        f"/api/v1/admin/segments/{seg_id}",
        json={"text": "Four five!", "translation_vi": "Bốn, năm!", "start_ms": 3100, "end_ms": 5900},
        headers=headers,
    )
    assert res.status_code == 200
    seg = res.json()["segments"][1]
    assert (seg["text"], seg["translation_vi"], seg["start_ms"], seg["end_ms"]) == (
        "Four five!",
        "Bốn, năm!",
        3100,
        5900,
    )
    assert seg["id"] == seg_id


@pytest.mark.parametrize(
    "payload",
    [{"start_ms": 2500}, {"end_ms": 6500}, {"start_ms": 5000, "end_ms": 4000}, {"text": "  "}],
)
async def test_edit_segment_rejects_overlap_and_bad_values(
    harness: Harness, payload: dict[str, object]
) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness)
    seg_id = (await _detail(harness, lesson.id))["segments"][1]["id"]
    res = await harness.client.patch(f"/api/v1/admin/segments/{seg_id}", json=payload, headers=headers)
    assert res.status_code == 422


async def test_processing_lesson_cannot_be_edited(harness: Harness) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness, LessonStatus.PROCESSING)
    seg_id = (await _detail(harness, lesson.id))["segments"][0]["id"]
    res = await harness.client.patch(f"/api/v1/admin/segments/{seg_id}", json={"text": "x"}, headers=headers)
    assert res.status_code == 409


async def test_merge_adjacent_segments_renumbers(harness: Harness) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness)
    segs = (await _detail(harness, lesson.id))["segments"]
    bad = await harness.client.post(
        "/api/v1/admin/segments/merge",
        json={"first_id": segs[0]["id"], "second_id": segs[2]["id"]},
        headers=headers,
    )
    assert bad.status_code == 422

    res = await harness.client.post(
        "/api/v1/admin/segments/merge",
        json={"first_id": segs[0]["id"], "second_id": segs[1]["id"]},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    after = res.json()["segments"]
    assert [(s["idx"], s["text"], s["start_ms"], s["end_ms"]) for s in after] == [
        (0, "One two three Four five", 0, 6000),
        (1, "Six", 6000, 9000),
    ]
    assert after[0]["translation_vi"] == "Một hai ba Bốn năm"
    assert after[0]["word_count_aligned"] is True


async def test_split_uses_word_timing_and_flags_for_retranslation(harness: Harness) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness)
    segs = (await _detail(harness, lesson.id))["segments"]
    res = await harness.client.post(
        f"/api/v1/admin/segments/{segs[0]['id']}/split", json={"word_index": 2}, headers=headers
    )
    assert res.status_code == 200, res.text
    after = res.json()["segments"]
    assert [(s["idx"], s["text"], s["start_ms"], s["end_ms"]) for s in after] == [
        (0, "One two", 0, 2000),
        (1, "three", 2000, 3000),
        (2, "Four five", 3000, 6000),
        (3, "Six", 6000, 9000),
    ]
    assert after[1]["translation_vi"] == "" and after[1]["needs_attention"] is True


async def test_split_after_text_edit_needs_explicit_time(harness: Harness) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness)
    seg_id = (await _detail(harness, lesson.id))["segments"][0]["id"]
    await harness.client.patch(
        f"/api/v1/admin/segments/{seg_id}", json={"text": "One, two and three"}, headers=headers
    )
    url = f"/api/v1/admin/segments/{seg_id}/split"
    assert (await harness.client.post(url, json={"word_index": 2}, headers=headers)).status_code == 422
    res = await harness.client.post(url, json={"word_index": 2, "split_ms": 1500}, headers=headers)
    assert res.status_code == 200
    assert [s["text"] for s in res.json()["segments"][:2]] == ["One, two", "and three"]


async def test_publish_requires_translations_then_locks_structure(harness: Harness) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness)
    segs = (await _detail(harness, lesson.id))["segments"]
    await harness.client.patch(
        f"/api/v1/admin/segments/{segs[2]['id']}", json={"translation_vi": ""}, headers=headers
    )
    publish = f"/api/v1/admin/lessons/{lesson.id}/publish"
    assert (await harness.client.post(publish, headers=headers)).status_code == 422

    await harness.client.patch(
        f"/api/v1/admin/segments/{segs[2]['id']}", json={"translation_vi": "Sáu"}, headers=headers
    )
    res = await harness.client.post(publish, headers=headers)
    assert res.status_code == 200 and res.json()["status"] == "published" and res.json()["published_at"]

    # Published: in-place edits allowed, merge/split blocked (AC-M2-04.3).
    ok = await harness.client.patch(
        f"/api/v1/admin/segments/{segs[0]['id']}", json={"text": "One, two, three."}, headers=headers
    )
    assert ok.status_code == 200
    merge = await harness.client.post(
        "/api/v1/admin/segments/merge",
        json={"first_id": segs[0]["id"], "second_id": segs[1]["id"]},
        headers=headers,
    )
    split = await harness.client.post(
        f"/api/v1/admin/segments/{segs[1]['id']}/split", json={"word_index": 1}, headers=headers
    )
    assert (merge.status_code, split.status_code) == (409, 409)

    unpub = await harness.client.post(f"/api/v1/admin/lessons/{lesson.id}/unpublish", headers=headers)
    assert unpub.json()["status"] == "unpublished"
    assert (await harness.client.post(publish, headers=headers)).json()["status"] == "published"


async def test_retry_only_failed_lessons(harness: Harness) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness, LessonStatus.FAILED)
    res = await harness.client.post(f"/api/v1/admin/lessons/{lesson.id}/retry", headers=headers)
    assert res.status_code == 200 and res.json()["status"] == "processing"
    again = await harness.client.post(f"/api/v1/admin/lessons/{lesson.id}/retry", headers=headers)
    assert again.status_code == 409


async def test_update_lesson_metadata(harness: Harness) -> None:
    headers = await _admin(harness)
    lesson = await _seed_review_lesson(harness)
    res = await harness.client.patch(
        f"/api/v1/admin/lessons/{lesson.id}",
        json={"title": "New", "level": "advanced", "license": "CC BY"},
        headers=headers,
    )
    assert (res.json()["title"], res.json()["level"], res.json()["license"]) == ("New", "advanced", "CC BY")
    bad = await harness.client.patch(
        f"/api/v1/admin/lessons/{lesson.id}", json={"license": ""}, headers=headers
    )
    assert bad.status_code == 422


async def test_saving_a_flagged_segment_clears_its_warning(harness: Harness) -> None:
    headers = await _admin(harness)
    await _seed_review_lesson(harness)
    async with harness.sessions() as db:
        seg = (await db.execute(select(Segment).where(Segment.idx == 1))).scalar_one()
        seg.needs_attention, seg.attention_reason = True, "5 từ căn thời gian kém tin cậy"
        await db.commit()
        seg_id = seg.id
    res = await harness.client.patch(
        f"/api/v1/admin/segments/{seg_id}", json={"end_ms": 5900}, headers=headers
    )
    body = res.json()
    assert body["attention_count"] == 0
    assert (body["segments"][1]["needs_attention"], body["segments"][1]["attention_reason"]) == (False, "")
