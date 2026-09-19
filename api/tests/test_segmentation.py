from app.services.segmentation import (
    AlignedWord,
    assign_word_timings,
    build_segments,
    split_sentences,
)


def w(text: str, start: int, end: int, p: float = 0.9) -> AlignedWord:
    return AlignedWord(text, start, end, p)


def test_split_sentences_keeps_punctuation_and_abbreviations() -> None:
    text = 'Dr. Smith arrived at 3 p.m. today.\n\nHe said, "Hello!" Then he left?  Yes.'
    assert split_sentences(text) == [
        "Dr. Smith arrived at 3 p.m. today.",
        'He said, "Hello!"',
        "Then he left?",
        "Yes.",
    ]
    assert split_sentences("   ") == []


def test_word_timings_follow_tokens_even_when_aligner_splits_words() -> None:
    tokens = ["A", "well-known", "fact."]
    aligned = [w(" A", 0, 100), w(" well", 200, 400), w("-known", 400, 700), w(" fact.", 800, 1200)]
    timed = assign_word_timings(tokens, aligned)
    assert [(t.word, t.start_ms, t.end_ms) for t in timed] == [
        ("A", 0, 100),
        ("well-known", 200, 700),
        ("fact.", 800, 1200),
    ]


def test_word_missing_from_alignment_has_no_time() -> None:
    timed = assign_word_timings(["one", "two", "three"], [w(" one", 0, 100), w(" three", 500, 700)])
    assert timed[1].start_ms is None
    assert (timed[2].start_ms, timed[2].end_ms) == (500, 700)


def test_segment_bounds_pad_and_never_overlap() -> None:
    sentences = ["One two.", "Three four."]
    aligned = [w("One", 1000, 1300), w("two.", 1400, 1900), w("Three", 2000, 2400), w("four.", 2500, 3000)]
    first, second = build_segments(sentences, aligned, duration_ms=10_000)
    # start = first word − 150; end = last word + 500 but not past next start
    assert (first.start_ms, first.end_ms) == (850, 1850)
    assert (second.start_ms, second.end_ms) == (1850, 3500)
    assert first.end_ms <= second.start_ms


def test_segment_bounds_clamped_to_audio() -> None:
    [seg] = build_segments(["Hi there."], [w("Hi", 50, 300), w("there.", 400, 990)], duration_ms=1000)
    assert (seg.start_ms, seg.end_ms) == (0, 1000)


def test_attention_flags() -> None:
    long_sentence = " ".join(f"w{i}" for i in range(26)) + "."
    aligned = [w(f"w{i}", i * 100, i * 100 + 90) for i in range(26)]
    aligned += [w("Short.", 3000, 3300, p=0.1)]
    aligned += [w("Two", 5000, 5200)]  # "words" missing from alignment
    drafts = build_segments([long_sentence, "Short.", "Two words."], aligned, duration_ms=9000)
    assert drafts[0].needs_attention and "26 từ" in drafts[0].attention_reason
    assert "1 giây" in drafts[1].attention_reason and "kém tin cậy" in drafts[1].attention_reason
    assert "không căn được" in drafts[2].attention_reason
    # the unplaced word still gets an interpolated time
    assert drafts[2].words[1].start_ms is not None


def test_clean_segment_not_flagged() -> None:
    [seg] = build_segments(
        ["Good morning everyone."],
        [w("Good", 0, 300), w("morning", 300, 800), w("everyone.", 800, 1500)],
        5000,
    )
    assert not seg.needs_attention and seg.attention_reason == ""


def test_closing_quote_stays_with_its_sentence() -> None:
    # Real VOA text: opens with a straight quote, closes with a curly one, so the splitter misplaces it.
    text = (
        "The year after that the survey recorded 335,479 monarchs. "
        '"This is bad news," Pelton said. "But we have seen incredible recovery. '
        "This doesn't mean we're not going to have western monarchs.\u201d "
        "The U.S. Fish and Wildlife Service acted."
    )
    sentences = split_sentences(text)
    assert sentences[0] == "The year after that the survey recorded 335,479 monarchs."
    assert sentences[1].startswith('"This is bad news,"')
    assert "This doesn't mean we're not going to have western monarchs.\u201d" in sentences
    assert sentences[-1] == "The U.S. Fish and Wildlife Service acted."
    assert not any(s[0] in "\u201d\u2019)]" for s in sentences)


def test_single_weak_word_is_not_flagged_but_many_are() -> None:
    words = [f"w{i}" for i in range(10)]
    sentence = " ".join(words) + "."
    one_weak = [w(t, i * 100, i * 100 + 90, p=0.1 if i == 3 else 0.9) for i, t in enumerate(words)]
    [seg] = build_segments([sentence], one_weak, 5000)
    assert not seg.needs_attention
    three_weak = [w(t, i * 100, i * 100 + 90, p=0.1 if i in (1, 2, 3) else 0.9) for i, t in enumerate(words)]
    [seg] = build_segments([sentence], three_weak, 5000)
    assert seg.needs_attention and "3 từ" in seg.attention_reason


def test_unplaced_leading_token_does_not_clip_previous_sentence() -> None:
    # "--" has no alignment; its interpolated time must not move sentence 2's start before "Next".
    aligned = [w("Last", 0, 400), w("words.", 500, 1200), w("Next", 2500, 2800), w("one.", 2900, 3300)]
    first, second = build_segments(["Last words.", "-- Next one."], aligned, duration_ms=5000)
    assert second.start_ms == 2350
    assert first.end_ms == 1700  # last word end + 500, not cut at the interpolated time
