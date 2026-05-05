import pytest
from talk_to_vibe.providers.post_process import clean_transcript


class TestDisfluencyRemoval:
    def test_removes_um(self):
        assert clean_transcript("Um, run pytest.") == "Run pytest."

    def test_removes_uh(self):
        assert clean_transcript("uh run the tests") == "Run the tests"

    def test_removes_hmm(self):
        assert clean_transcript("hmm let me check") == "Let me check"

    def test_removes_mid_sentence_um(self):
        assert clean_transcript("Open um the file.") == "Open the file."

    def test_removes_you_know(self):
        assert clean_transcript("You know, run the script.") == "Run the script."

    def test_removes_i_mean(self):
        assert clean_transcript("I mean, use pytest.") == "Use pytest."

    def test_removes_leading_like(self):
        assert clean_transcript("Like run the tests.") == "Run the tests."

    def test_removes_trailing_like(self):
        assert clean_transcript("run the tests like") == "run the tests"

    def test_removes_repeated_word(self):
        assert clean_transcript("open the the file") == "open the file"

    def test_repeated_word_case_insensitive(self):
        assert clean_transcript("The the function") == "The function"

    def test_preserves_technical_terms(self):
        text = "Run pytest -x tests/test_app.py"
        assert clean_transcript(text) == text

    def test_preserves_file_paths(self):
        text = "Edit src/utils/helpers.py and commit."
        assert clean_transcript(text) == text

    def test_preserves_empty_string(self):
        assert clean_transcript("") == ""

    def test_restores_initial_capital_after_leading_filler(self):
        result = clean_transcript("Um, update the config.")
        assert result[0].isupper()

    def test_preserves_identifier_casing(self):
        text = "Use WhisperModel with beam_size five."
        assert clean_transcript(text) == text

    def test_mid_sentence_like_not_removed(self):
        # "like" inside a sentence where it functions as a comparison is kept
        result = clean_transcript("It looks like a decorator.")
        assert "like" in result
