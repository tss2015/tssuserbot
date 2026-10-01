import re

SECRET_PATTERNS = [
    re.compile(r"(?i)(api_hash|bot_token|session|otp|password)\s*=\s*\S+"),
]


def redact(text: str) -> str:
    value = text
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def valid_chat_id(value: str) -> bool:
    return bool(re.fullmatch(r"-?\d{5,15}", value))


def safe_display_name(value: str, fallback="user") -> str:
    value = re.sub(r"[\r\n\t]+", " ", value or "").strip()
    return value[:64] or fallback
