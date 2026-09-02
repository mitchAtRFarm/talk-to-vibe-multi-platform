import numpy as np

from talk_to_vibe.audio.chunk import (
    CHUNK_SECONDS,
    pcm_duration_seconds,
    split_audio_chunks,
    stitch_transcripts,
)
from talk_to_vibe.audio.wav import SAMPLE_RATE


def _audio(seconds: float) -> np.ndarray:
    return np.zeros((int(seconds * SAMPLE_RATE), 1), dtype=np.int16)


class TestPcmDuration:
    def test_empty(self):
        assert pcm_duration_seconds(np.zeros((0, 1), dtype=np.int16)) == 0.0

    def test_one_second(self):
        assert pcm_duration_seconds(_audio(1.0)) == 1.0


class TestSplitAudioChunks:
    def test_short_audio_is_one_chunk(self):
        audio = _audio(5.0)
        chunks = split_audio_chunks(audio)
        assert len(chunks) == 1
        assert len(chunks[0]) == len(audio)

    def test_exact_chunk_length_is_one_chunk(self):
        audio = _audio(CHUNK_SECONDS)
        chunks = split_audio_chunks(audio)
        assert len(chunks) == 1

    def test_long_audio_splits_with_overlap(self):
        audio = _audio(25.0)
        chunks = split_audio_chunks(audio)
        assert len(chunks) == 2
        assert len(chunks[0]) == int(CHUNK_SECONDS * SAMPLE_RATE)
        assert len(chunks[1]) < len(chunks[0])

    def test_empty_audio(self):
        assert split_audio_chunks(np.zeros((0, 1), dtype=np.int16)) == []


class TestStitchTranscripts:
    def test_empty(self):
        assert stitch_transcripts([]) == ""
        assert stitch_transcripts(["", "  "]) == ""

    def test_single(self):
        assert stitch_transcripts(["Hello world"]) == "Hello world"

    def test_joins_without_overlap(self):
        assert stitch_transcripts(["Hello there", "how are you"]) == "Hello there how are you"

    def test_drops_overlapping_words(self):
        assert stitch_transcripts(
            ["one two three four", "three four five six"]
        ) == "one two three four five six"
