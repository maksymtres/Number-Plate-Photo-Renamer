import re

ALLOWED_SUFFIXES = {"a", "b", "c", "d", "e"}


def normalize_text(raw_text: str) -> str:
    if raw_text is None:
        return ""

    text = raw_text.strip().lower()
    text = text.replace(" ", "")

    match = re.fullmatch(r"(\d+)([a-z]?)", text)
    if not match:
        return text

    digits, suffix = match.groups()
    digits = digits.lstrip("0") or "0"

    return digits + suffix


def validate_text(normalized_text: str) -> tuple[bool, str | None]:
    if not normalized_text:
        return False, "пустая строка"

    match = re.fullmatch(r"(\d{1,4})([a-z]?)", normalized_text)
    if not match:
        return False, "формат должен быть: 1-4 цифры и необязательная буква"

    digits, suffix = match.groups()

    if suffix and suffix not in ALLOWED_SUFFIXES:
        return False, f"недопустимая буква: {suffix}"

    return True, None
