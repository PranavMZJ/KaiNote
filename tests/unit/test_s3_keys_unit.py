"""Unit tests for S3 key generation utilities."""

from backend.utils.s3_keys import transcript_key, report_key, status_key


class TestTranscriptKey:
    def test_raw_default(self):
        assert transcript_key("user-1", "meeting-1") == "users/user-1/transcripts/meeting-1/raw.json"

    def test_raw_explicit(self):
        assert transcript_key("user-1", "meeting-1", "raw") == "users/user-1/transcripts/meeting-1/raw.json"

    def test_cleaned(self):
        assert transcript_key("user-1", "meeting-1", "cleaned") == "users/user-1/transcripts/meeting-1/cleaned.json"

    def test_user_scoped_prefix(self):
        key = transcript_key("abc-123", "m-456")
        assert key.startswith("users/abc-123/")


class TestReportKey:
    def test_original(self):
        assert report_key("user-1", "meeting-1") == "users/user-1/reports/meeting-1/minutes.json"

    def test_edited(self):
        assert report_key("user-1", "meeting-1", edited=True) == "users/user-1/reports/meeting-1/minutes_edited.json"

    def test_user_scoped_prefix(self):
        key = report_key("abc-123", "m-456")
        assert key.startswith("users/abc-123/")


class TestStatusKey:
    def test_basic(self):
        assert status_key("meeting-1") == "meetings/meeting-1/status.json"

    def test_not_user_scoped(self):
        key = status_key("m-1")
        assert key.startswith("meetings/")
        assert "users/" not in key


class TestKeyIsolation:
    def test_different_users_no_overlap(self):
        """Keys for different users must not share a prefix below users/."""
        k1 = transcript_key("user-A", "m-1")
        k2 = transcript_key("user-B", "m-1")
        # Both start with users/ but diverge immediately after
        prefix1 = k1.split("/")[1]  # "user-A"
        prefix2 = k2.split("/")[1]  # "user-B"
        assert prefix1 != prefix2

    def test_different_users_report_no_overlap(self):
        k1 = report_key("user-A", "m-1")
        k2 = report_key("user-B", "m-1")
        prefix1 = k1.split("/")[1]
        prefix2 = k2.split("/")[1]
        assert prefix1 != prefix2
