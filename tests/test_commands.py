from app.services.commands import parse_command


def test_parse_create_command() -> None:
    command = parse_command("/新建 小红书 社团招新怎么提高转化")
    assert command is not None
    assert command.name == "新建"
    assert command.args == ["小红书", "社团招新怎么提高转化"]


def test_ignore_plain_text() -> None:
    assert parse_command("今天发什么") is None

