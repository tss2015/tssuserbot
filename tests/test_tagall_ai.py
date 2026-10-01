from types import SimpleNamespace

from handlers.tagall import MOOD_ALIASES, _parse_request
from services.mention_manager import mention


def test_all_five_tagging_moods_are_available():
    assert MOOD_ALIASES == {
        "happy": "happy",
        "sassy": "sassy",
        "sulky": "sulky",
        "romantic": "romantic",
        "sleepy": "sleepy",
    }


def test_parse_tgall_alias():
    update = SimpleNamespace(
        effective_message=SimpleNamespace(text="/tgallhappy hello everyone"),
    )
    context = SimpleNamespace(args=["hello", "everyone"])

    mood, instruction = _parse_request(update, context)

    assert mood == "happy"
    assert instruction == "hello everyone"


def test_parse_tagmood_command():
    update = SimpleNamespace(
        effective_message=SimpleNamespace(text="/tagmood romantic come back"),
    )
    context = SimpleNamespace(args=["romantic", "come", "back"])

    mood, instruction = _parse_request(update, context)

    assert mood == "romantic"
    assert instruction == "come back"


def test_mentions_escape_html():
    user = SimpleNamespace(id=123, first_name="<Alice & Bob>")
    result = mention(user)

    assert result == '<a href="tg://user?id=123">&lt;Alice &amp; Bob&gt;</a>'
