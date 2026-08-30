from app.core.pagination import decode_cursor, encode_cursor


def test_cursor_round_trip() -> None:
    payload = {"created_at": "2026-08-30T10:00:00+00:00", "id": "abc"}
    assert decode_cursor(encode_cursor(payload)) == payload


def test_cursor_is_url_safe() -> None:
    cursor = encode_cursor({"created_at": "2026-08-30T10:00:00+00:00", "id": "x" * 40})
    assert "+" not in cursor and "/" not in cursor and "=" not in cursor
