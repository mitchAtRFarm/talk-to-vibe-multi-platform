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

# Collapse runs of whitespace left over after removals.
_WHITESPACE = re.compile(r"  +")


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
    # Capitalize the first word if we removed a leading filler — detected by
    # the result starting with a different character than the original.
    if t and t[0].islower() and text and not text.startswith(t[0]):
        t = t[0].upper() + t[1:]
    return t
