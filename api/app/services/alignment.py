"""Forced alignment of a known transcript to audio with stable-ts (worker image only).

`stable_whisper` is imported lazily: it lives in the `alignment` dependency group, installed in the
worker image but not the API image.
"""

from functools import lru_cache
from typing import Any

from app.services.segmentation import AlignedWord


@lru_cache(maxsize=1)
def _model(name: str) -> Any:
    import stable_whisper  # noqa: PLC0415 — heavy optional dependency

    return stable_whisper.load_model(name, device="cpu")


def align(audio_path: str, transcript: str, model_name: str) -> list[AlignedWord]:
    """Blocking and CPU-heavy: call via `asyncio.to_thread`."""
    result = _model(model_name).align(audio_path, transcript, language="en")
    return [
        AlignedWord(
            text=word.word,
            start_ms=round(word.start * 1000),
            end_ms=round(word.end * 1000),
            probability=float(word.probability if word.probability is not None else 0.0),
        )
        for segment in result.segments
        for word in segment.words
    ]
