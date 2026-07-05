from dataclasses import dataclass


@dataclass(frozen=True)
class BotCommand:
    name: str
    args: list[str]
    raw: str


def parse_command(text: str) -> BotCommand | None:
    cleaned = " ".join(text.replace("\u00a0", " ").strip().split())
    if not cleaned.startswith("/"):
        return None
    parts = cleaned[1:].split(" ")
    if not parts or not parts[0]:
        return None
    return BotCommand(name=parts[0], args=parts[1:], raw=cleaned)

