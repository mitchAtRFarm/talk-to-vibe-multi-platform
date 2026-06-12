import re

# Matches pure disfluency tokens — sounds that are never meaningful words in
# technical speech. Kept deliberately narrow to avoid touching real vocabulary.
_DISFLUENCY = re.compile(
    r"\b(u+h+|u+m+|h+m+|e+r+m?|a+h+)\b[,.]?\s*",
    re.IGNORECASE,
)

# "you know" and "I mean" at any position; "like" only when it appears alone
# at the start or end of a sentence fragment (not mid-sentence).
_YOU_KNOW = re.compile(r"\byou know\b[,.]?\s*", re.IGNORECASE)
_I_MEAN = re.compile(r"\bI mean\b[,.]?\s*", re.IGNORECASE)
# "like" only when leading a fragment with no preceding text or trailing alone
_LEADING_LIKE = re.compile(r"^like[,.]?\s+", re.IGNORECASE)
_TRAILING_LIKE = re.compile(r"\s+like[,.]?$", re.IGNORECASE)

# Repeated word self-corrections: "the the", "I I", "and and", etc.
_REPEAT = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)

# Sentence-like chunks used to remove Whisper tail loops such as
# "Thank you. Thank you. Thank you." without touching unpunctuated dictation.
_SENTENCE_CHUNK = re.compile(r"\s*[^.!?\n]+[.!?\n]+")
_REPEAT_TAIL_CHARS = 250
_MIN_REPEAT_PHRASE_CHARS = 5

# Collapse runs of whitespace left over after removals.
_WHITESPACE = re.compile(r"  +")


def _normalize_repeat_phrase(text: str) -> str:
    normalized = re.sub(r"[^\w']+", " ", text.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _dedupe_trailing_phrases(text: str) -> str:
    chunks = [
        (match.start(), match.end(), _normalize_repeat_phrase(match.group()))
        for match in _SENTENCE_CHUNK.finditer(text)
    ]
    if len(chunks) < 2:
        return text

    tail_start = max(0, len(text) - _REPEAT_TAIL_CHARS)
    previous = chunks[-2]
    last = chunks[-1]
    if previous[1] <= tail_start:
        return text

    repeated_phrase = last[2]
    if len(repeated_phrase) < _MIN_REPEAT_PHRASE_CHARS or previous[2] != repeated_phrase:
        return text

    first_repeated = len(chunks) - 1
    while first_repeated > 0 and chunks[first_repeated - 1][2] == repeated_phrase:
        first_repeated -= 1

    remove_from = chunks[first_repeated + 1][0]
    return text[:remove_from].rstrip()


def clean_transcript(text: str) -> str:
    """Remove disfluencies and common filler patterns from a Whisper segment."""
    if not text:
        return text
    t = _DISFLUENCY.sub("", text)
    t = _YOU_KNOW.sub("", t)
    t = _I_MEAN.sub("", t)
    t = _LEADING_LIKE.sub("", t)
    t = _TRAILING_LIKE.sub("", t)
    t = _REPEAT.sub(r"\1", t)
    t = _WHITESPACE.sub(" ", t).strip()
    t = _dedupe_trailing_phrases(t)
    # Capitalize the first word if we removed a leading filler — detected by
    # the result starting with a different character than the original.
    if t and t[0].islower() and text and not text.startswith(t[0]):
        t = t[0].upper() + t[1:]
    return t
