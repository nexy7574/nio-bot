import re
import typing

import pytest

import niobot

DEFAULT_HELP_COMMAND = niobot.Command(
    "help",
    niobot.default_help_command,
    aliases=["h"],
    description="Shows a list of commands for this bot",
)


@pytest.mark.parametrize(
    "kwargs,expected_error,expected_attrs",
    [
        ({"homeserver": "https://example.com", "user_id": "@example:example.com", "command_prefix": "!"}, None, ...),
        (
            {
                "homeserver": "https://example.com",
                "user_id": "@example:example.com",
                "command_prefix": re.compile(r"^!"),
            },
            None,
            ...,
        ),
        (
            {"homeserver": "https://example.com", "user_id": "@example:example.com", "command_prefix": "foo bar"},
            RuntimeError,
            ...,
        ),
        (
            {"homeserver": "https://example.com", "user_id": "@example:example.com", "command_prefix": None},
            TypeError,
            ...,
        ),
        (
            {
                "homeserver": "https://example.com",
                "user_id": "@example:example.com",
                "command_prefix": re.compile(r"^!"),
                "help_command": "none",
            },
            TypeError,
            ...,
        ),
    ],
)
def test_client_init(
    kwargs,
    expected_error: typing.Optional[type(Exception)],
    expected_attrs: typing.Union[dict[str, typing.Any], type(Ellipsis)],
):
    if expected_error is not None:
        with pytest.raises(expected_error):
            niobot.NioBot(**kwargs)
    else:
        if expected_attrs is ...:
            expected_attrs = kwargs
        client = niobot.NioBot(**kwargs)
        for expected_attr_name, expected_attr_value in expected_attrs.items():
            assert (
                getattr(client, expected_attr_name) == expected_attr_value
            ), f"Attribute {expected_attr_name} is not {expected_attr_value}"
