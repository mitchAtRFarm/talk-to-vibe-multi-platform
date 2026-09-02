from talk_to_vibe.audio.wav import SAMPLE_RATE

CHUNK_SECONDS = 20.0
OVERLAP_SECONDS = 1.0
_MAX_OVERLAP_WORDS = 12


def pcm_duration_seconds(audio_data) -> float:
    if audio_data is None or len(audio_data) == 0:
        return 0.0
    return len(audio_data) / float(SAMPLE_RATE)


def split_audio_chunks(
    audio_data,
    chunk_seconds: float = CHUNK_SECONDS,
    overlap_seconds: float = OVERLAP_SECONDS,
):
    if audio_data is None or len(audio_data) == 0:
        return []
    chunk_samples = int(chunk_seconds * SAMPLE_RATE)
    overlap_samples = int(overlap_seconds * SAMPLE_RATE)
    if chunk_samples <= 0:
        return [audio_data]
    if overlap_samples >= chunk_samples:
        overlap_samples = max(0, chunk_samples // 5)
    if len(audio_data) <= chunk_samples:
        return [audio_data]

    pieces = []
    start = 0
    length = len(audio_data)
    while start < length:
        end = min(start + chunk_samples, length)
        pieces.append(audio_data[start:end])
        if end >= length:
            break
        start = end - overlap_samples
    return pieces


def stitch_transcripts(parts: list[str]) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return ""
    result = cleaned[0]
    for piece in cleaned[1:]:
        result = _join_overlap(result, piece)
    return result


def _join_overlap(left: str, right: str) -> str:
    left_words = left.split()
    right_words = right.split()
    max_n = min(len(left_words), len(right_words), _MAX_OVERLAP_WORDS)
    for n in range(max_n, 0, -1):
        if [word.lower() for word in left_words[-n:]] == [word.lower() for word in right_words[:n]]:
            remainder = right_words[n:]
            if not remainder:
                return left
            return left + " " + " ".join(remainder)
    return left + " " + right
