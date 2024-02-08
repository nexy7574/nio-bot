import typing

import pytest

from niobot.commands import Argument
from niobot.context import Context
from niobot.utils.parsers import *

EXAMPLE_MXC = "mxc://nexy7574.co.uk/6cefe7e807bb846ec44e1a5ec4fdbd5703e932bd46ad500012c16d4d44a79c32"


@pytest.mark.parametrize(
    "parser, input_value, expected_value, ctx, arg",
    [
        (IntegerParser(), "1", 1, None, None),
        (IntegerParser(allow_floats=True), "1.0", 1, None, None),
        (IntegerParser(base=16), "0xFFF", 0xFFF, None, None),
        (FloatParser(), "1.0", 1.0, None, None),
        (FloatParser(), "1", 1.0, None, None),
        (FloatParser(), "1.0e-3", 1.0e-3, None, None),
        (FloatParser(), "1.0e3", 1.0e3, None, None),
        (BooleanParser(), "true", True, None, None),
        (BooleanParser(), "false", False, None, None),
        (BooleanParser(), "1", True, None, None),
        (BooleanParser(), "0", False, None, None),
        (BooleanParser(), "yes", True, None, None),
        (BooleanParser(), "no", False, None, None),
        (BooleanParser(), "on", True, None, None),
        (BooleanParser(), "off", False, None, None),
        (BooleanParser(), "y", True, None, None),
        (BooleanParser(), "n", False, None, None),
        (JSONParser(), '{"a": 1}', {"a": 1}, None, None),
        (JSONParser(), "[1, 2, 3]", [1, 2, 3], None, None),
        (JSONParser(), "1", 1, None, None),
        (JSONParser(), "1.0", 1.0, None, None),
        (JSONParser(), "true", True, None, None),
        (JSONParser(), "false", False, None, None),
        (JSONParser(), "null", None, None, None),
    ],
)
def test_generic_parsers(
    parser: Parser,
    input_value: typing.Any,
    expected_value: typing.Optional[typing.Any],
    ctx: typing.Optional[Context],
    arg: typing.Optional[Argument],
):
    assert parser(ctx, arg, input_value) == expected_value


def test_mxc_parser():
    parser = MXCParser()
    parsed = parser(None, None, EXAMPLE_MXC)
    assert parsed.server == "nexy7574.co.uk"
    assert parsed.media_id == "6cefe7e807bb846ec44e1a5ec4fdbd5703e932bd46ad500012c16d4d44a79c32"


@pytest.mark.parametrize(
    "input_url, expected_value",
    [
        (
            "https://matrix.to/#/!rwJEulKnHLoffvXAof:nexy7574.co.uk/$_dC9O1LkAVxVjZpPowkdg7CbEfUMA3TuWpeLcUzzVa8",
            MatrixToLink("!rwJEulKnHLoffvXAof:nexy7574.co.uk", "$_dC9O1LkAVxVjZpPowkdg7CbEfUMA3TuWpeLcUzzVa8", ""),
        ),
        (
            "https://matrix.to/#/!rwJEulKnHLoffvXAof:nexy7574.co.uk",
            MatrixToLink("!rwJEulKnHLoffvXAof:nexy7574.co.uk", "", ""),
        ),
        ("https://matrix.to/#/@nex:nexy7574.co.uk", MatrixToLink("@nex:nexy7574.co.uk", "", "")),
    ],
)
@pytest.mark.asyncio
async def test_matrix_to_parser(input_url: str, expected_value: typing.Any):
    parser = MatrixToParser(stateless=True)
    parsed = await parser(None, None, input_url)
    for n in range(len(parsed)):
        assert parsed[n] == expected_value[n]
