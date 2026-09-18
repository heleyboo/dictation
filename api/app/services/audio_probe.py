"""Validate uploaded audio by its bytes, not by the filename or client-sent MIME (NFR-05)."""

import io
from dataclasses import dataclass

import filetype
import mutagen

ALLOWED = {
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "video/mp4": "m4a",  # m4a audio is sometimes sniffed as the generic MP4 container
    "audio/x-wav": "wav",
    "audio/wav": "wav",
}
CONTENT_TYPE = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav"}


class InvalidAudio(ValueError):
    pass


@dataclass(frozen=True)
class AudioInfo:
    extension: str
    content_type: str
    duration_ms: int


def probe(data: bytes) -> AudioInfo:
    kind = filetype.guess(data)
    if kind is None or kind.mime not in ALLOWED:
        raise InvalidAudio("Chỉ chấp nhận file âm thanh mp3, m4a hoặc wav")
    ext = ALLOWED[kind.mime]
    try:
        parsed = mutagen.File(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001 — any parse failure means unusable audio
        raise InvalidAudio("Không đọc được file âm thanh") from exc
    if parsed is None or not getattr(parsed.info, "length", 0):
        raise InvalidAudio("Không đọc được thời lượng file âm thanh")
    return AudioInfo(
        extension=ext, content_type=CONTENT_TYPE[ext], duration_ms=round(parsed.info.length * 1000)
    )
