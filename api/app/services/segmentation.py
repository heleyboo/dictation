"""Turn a transcript + word-level alignment into dictation segments (AC-M2-02.2, AC-M2-02.5).

Pure functions — no I/O — so the timing rules are unit-tested without running a speech model.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

import pysbd

LEAD_PAD_MS = 150
# Aligners tend to end the last word early (measured on VOA audio: +200 ms clipped "monarchs", +500 ms did
# not). Still capped by the next sentence's start, so segments never overlap.
TAIL_PAD_MS = 500
MAX_WORDS = 25
MIN_DURATION_MS = 1000
LOW_CONFIDENCE = 0.4
# One shaky word is normal; flag a sentence only when weak timings are frequent enough to matter.
WEAK_WORDS_TO_FLAG = 3
WEAK_SHARE_TO_FLAG = 0.2


@dataclass(frozen=True)
class AlignedWord:
    """One word as returned by the aligner (text may carry spaces/punctuation, split differently)."""

    text: str
    start_ms: int
    end_ms: int
    probability: float


@dataclass(frozen=True)
class TimedToken:
    word: str
    start_ms: int | None
    end_ms: int | None
    probability: float


@dataclass(frozen=True)
class SegmentDraft:
    text: str
    start_ms: int
    end_ms: int
    words: list[TimedToken]
    needs_attention: bool
    attention_reason: str


# Closing marks the splitter can leave at the start of the next sentence (e.g. `…monarchs.” The`).
_LEADING_CLOSERS = re.compile(r"^([”’)\]]+)\s*")
_STRAIGHT_QUOTE = re.compile(r'^"\s*')


def _leading_closer(sentence: str, previous: str) -> re.Match[str] | None:
    """A curly closing quote/bracket always closes; a straight `"` only when `previous` has one open."""
    closer = _LEADING_CLOSERS.match(sentence)
    if closer:
        return closer
    if previous.count('"') % 2 == 1:
        return _STRAIGHT_QUOTE.match(sentence)
    return None


def split_sentences(transcript: str) -> list[str]:
    """Sentence split that keeps the original punctuation; whitespace (incl. newlines) collapsed."""
    text = re.sub(r"\s+", " ", transcript).strip()
    if not text:
        return []
    sentences: list[str] = []
    for raw in pysbd.Segmenter(language="en", clean=False).segment(text):
        sentence = raw.strip()
        closer = _leading_closer(sentence, sentences[-1]) if sentences else None
        if closer:
            # A closing quote/bracket belongs to the sentence it ends.
            sentences[-1] += closer.group(0).strip()
            sentence = sentence[closer.end() :]
        if sentence:
            sentences.append(sentence)
    return sentences


def _key(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.lower())


def assign_word_timings(tokens: list[str], aligned: list[AlignedWord]) -> list[TimedToken]:
    """Map aligner words onto transcript tokens by character alignment.

    The aligner may split or join words differently from whitespace tokens ("well-known" → "well", "-known";
    numbers, contractions). Both sides are reduced to lowercase alphanumerics and matched character by
    character; each token takes the earliest start / latest end of the aligner words overlapping it.
    """
    token_keys = [_key(t) for t in tokens]
    word_keys = [_key(w.text) for w in aligned]
    target = "".join(token_keys)
    source = "".join(word_keys)

    # char index in `source` → aligner word index
    src_owner: list[int] = [i for i, k in enumerate(word_keys) for _ in k]
    # char index in `target` → token index
    tgt_owner: list[int] = [i for i, k in enumerate(token_keys) for _ in k]

    spans: dict[int, list[AlignedWord]] = {}
    matcher = SequenceMatcher(None, source, target, autojunk=False)
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            word = aligned[src_owner[block.a + offset]]
            spans.setdefault(tgt_owner[block.b + offset], []).append(word)

    timed: list[TimedToken] = []
    for i, token in enumerate(tokens):
        hits = spans.get(i)
        if not hits:
            timed.append(TimedToken(token, None, None, 0.0))
            continue
        timed.append(
            TimedToken(
                token,
                min(w.start_ms for w in hits),
                max(w.end_ms for w in hits),
                min(w.probability for w in hits),
            )
        )
    return timed


def _fill_missing(tokens: list[TimedToken], duration_ms: int) -> list[TimedToken]:
    """Tokens the aligner could not place get an interpolated time between known neighbours."""
    known = [i for i, t in enumerate(tokens) if t.start_ms is not None]
    if not known:
        return tokens
    out = list(tokens)
    for i, t in enumerate(tokens):
        if t.start_ms is not None:
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        lo = tokens[prev].end_ms if prev is not None else 0
        hi = tokens[nxt].start_ms if nxt is not None else duration_ms
        assert lo is not None and hi is not None
        out[i] = TimedToken(t.word, lo, max(lo, hi), 0.0)
    return out


def build_segments(sentences: list[str], aligned: list[AlignedWord], duration_ms: int) -> list[SegmentDraft]:
    """Sentence spans with padding: start = first word − 150 ms, end = last word + 500 ms, never
    overlapping the next sentence's start and never beyond the audio."""
    sentence_tokens = [s.split() for s in sentences]
    flat = [tok for toks in sentence_tokens for tok in toks]
    raw = assign_word_timings(flat, aligned)
    timed = _fill_missing(raw, duration_ms)

    per_sentence: list[tuple[list[TimedToken], list[TimedToken]]] = []
    pos = 0
    for toks in sentence_tokens:
        per_sentence.append((raw[pos : pos + len(toks)], timed[pos : pos + len(toks)]))
        pos += len(toks)

    # Bounds come from words the aligner actually placed; interpolated times (unplaced tokens such as a
    # stray quote) would otherwise pull a sentence's start into its neighbour and clip its last word.
    def anchors(raw_words: list[TimedToken], words: list[TimedToken]) -> list[TimedToken]:
        placed = [w for w in raw_words if w.start_ms is not None]
        return placed or words

    starts: list[int] = []
    for raw_words, words in per_sentence:
        first = next((w.start_ms for w in anchors(raw_words, words) if w.start_ms is not None), 0)
        starts.append(max(0, first - LEAD_PAD_MS))
    # Keep starts monotonic even if alignment is off.
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1])

    drafts: list[SegmentDraft] = []
    for i, (sentence, (raw_words, words)) in enumerate(zip(sentences, per_sentence, strict=True)):
        last = max((w.end_ms for w in anchors(raw_words, words) if w.end_ms is not None), default=starts[i])
        limit = starts[i + 1] if i + 1 < len(starts) else duration_ms
        end = min(last + TAIL_PAD_MS, limit, duration_ms)
        end = max(end, starts[i] + 1)

        reasons: list[str] = []
        if len(words) > MAX_WORDS:
            reasons.append(f"Câu dài {len(words)} từ (> {MAX_WORDS})")
        if end - starts[i] < MIN_DURATION_MS:
            reasons.append("Câu ngắn hơn 1 giây")
        unplaced = sum(1 for w in raw_words if w.start_ms is None)
        weak = sum(1 for w in raw_words if w.start_ms is not None and w.probability < LOW_CONFIDENCE)
        if unplaced:
            reasons.append(f"{unplaced} từ không căn được thời gian")
        elif weak >= WEAK_WORDS_TO_FLAG or (words and weak / len(words) >= WEAK_SHARE_TO_FLAG):
            reasons.append(f"{weak} từ căn thời gian kém tin cậy")

        drafts.append(
            SegmentDraft(
                text=sentence,
                start_ms=starts[i],
                end_ms=end,
                words=words,
                needs_attention=bool(reasons),
                attention_reason="; ".join(reasons),
            )
        )
    return drafts
