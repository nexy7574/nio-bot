import os

import pytest

import niobot


async def loaded_func(
    ctx: niobot.Context,
    arg1: str,
    arg2: int,
    optional_arg3: str | None = None,
    implicit_optional_arg4: str = "default",
    *,
    greedy_arg: str,
):
    return arg1, arg2, optional_arg3, implicit_optional_arg4, greedy_arg


def test_arg_detection():
    func = niobot.command("test")(loaded_func)
    instance: niobot.Command = func.__nio_command__

    assert len(instance.arguments) == 6, "Expected 6 arguments"
    assert instance.arguments[0].name == "ctx", "Expected ctx as first argument"
    assert instance.arguments[1].name == "arg1", "Expected arg1 as second argument"
    assert instance.arguments[2].name == "arg2", "Expected arg2 as third argument"
    assert instance.arguments[3].name == "optional_arg3", "Expected optional_arg3 as fourth argument"
    assert instance.arguments[4].name == "implicit_optional_arg4", "Expected implicit_optional_arg4 as fifth argument"
    assert instance.arguments[5].name == "greedy_arg", "Expected greedy_arg as sixth argument"
    assert instance.arguments[5].greedy, "Expected greedy_arg to be greedy"
    assert instance.arguments[1].type is str, "Expected arg1 to be a string"
    assert instance.arguments[2].type is int, "Expected arg2 to be an int"
    assert instance.arguments[3].type is str, "Expected optional_arg3 to be a string"
    assert instance.arguments[4].type is str, "Expected implicit_optional_arg4 to be a string"
    assert instance.arguments[5].type is str, "Expected greedy_arg to be a string"

    assert instance.arguments[3].required is False, "Expected optional_arg3 to be not required"
    assert instance.arguments[4].default == "default", "Expected implicit_optional_arg4 to have a default value"


@pytest.mark.parametrize(
    "input_string, expected_result",
    # input string should not have a prefix
    [
        ("test arg1 0", ("arg1", 0, None, "default", "")),
        ("test 'arg1 part 2' 0", ("arg1 part 2", 0, None, "default", "")),
        ("test arg1 0 arg3", ("arg1", 0, "arg3", "default", "")),
        ("test arg1 0 arg3 arg4", ("arg1", 0, "arg3", "arg4", "")),
        ("test arg1 0 arg3 arg4 hello world extra text", ("arg1", 0, "arg3", "arg4", "hello world extra text")),
    ],
)
@pytest.mark.asyncio
async def test_arg_parsing(input_string, expected_result):
    bot = niobot.NioBot("https://example.invalid", "@example:example.invalid", command_prefix="!")
    bot.command("test")(loaded_func)
    cmd = bot.commands["test"]
    ctx = cmd.construct_context(
        bot,
        niobot.MatrixRoom("!example:example.invalid", "@example:example.invalid"),
        niobot.RoomMessageText.parse_event(
            {
                "type": "m.room.message",
                "content": {"body": input_string, "msgtype": "m.text"},
                "sender": "@example:example.invalid",
                "room_id": "!example:example.invalid",
                "event_id": os.urandom(16).hex(),
                "origin_server_ts": 0,
            }
        ),
        "!",
        "test",
    )
    result = await (await cmd.invoke(ctx))
    if expected_result is None:
        assert result is None
    else:
        assert result == expected_result
