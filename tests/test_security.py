from utils.security import redact, valid_chat_id

def test_chat_id():
    assert valid_chat_id("-1001234567890")
    assert not valid_chat_id("abc")

def test_redact():
    assert "secret" not in redact("session=secret")
