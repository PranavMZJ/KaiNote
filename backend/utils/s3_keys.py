"""S3 key generation utilities for user-scoped storage.

Generates keys following the patterns defined in the design document:
- users/{user_id}/transcripts/{meeting_id}/raw.json
- users/{user_id}/transcripts/{meeting_id}/cleaned.json
- users/{user_id}/reports/{meeting_id}/minutes.json
- users/{user_id}/reports/{meeting_id}/minutes_edited.json
- meetings/{meeting_id}/status.json
"""


def transcript_key(user_id: str, meeting_id: str, variant: str = "raw") -> str:
    """Generate an S3 key for a transcript file.

    Args:
        user_id: The Cognito user sub identifier.
        meeting_id: The meeting UUID.
        variant: Either "raw" or "cleaned". Defaults to "raw".

    Returns:
        The S3 object key, e.g. ``users/{user_id}/transcripts/{meeting_id}/raw.json``.
    """
    return f"users/{user_id}/transcripts/{meeting_id}/{variant}.json"


def report_key(user_id: str, meeting_id: str, edited: bool = False) -> str:
    """Generate an S3 key for a minutes report file.

    Args:
        user_id: The Cognito user sub identifier.
        meeting_id: The meeting UUID.
        edited: If True, returns the key for the user-edited version.

    Returns:
        The S3 object key, e.g. ``users/{user_id}/reports/{meeting_id}/minutes.json``.
    """
    filename = "minutes_edited.json" if edited else "minutes.json"
    return f"users/{user_id}/reports/{meeting_id}/{filename}"


def status_key(meeting_id: str) -> str:
    """Generate an S3 key for a meeting status file.

    Args:
        meeting_id: The meeting UUID.

    Returns:
        The S3 object key, e.g. ``meetings/{meeting_id}/status.json``.
    """
    return f"meetings/{meeting_id}/status.json"
