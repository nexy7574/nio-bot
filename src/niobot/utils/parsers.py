"""
This utility modules contains a handful of simple off-the-shelf parser for some basic python types.
"""

import re
import typing
from ..exceptions import CommandArgumentsError
if typing.TYPE_CHECKING:
    from ..context import Context
    from ..commands import Argument


__all__ = (
    "boolean_parser",
    "float_parser",
    "integer_parser",
    "json_parser",
)


def boolean_parser(_, __, value: str) -> bool:
    """
    Converts a given string into a boolean. Value is lower-cased before being parsed.

    The following resolves to true:
        1, y, yes, true, on

    The following resolves to false:
        0, n, no, false, off

    The following will raise a command argument error: anything else

    :param _: Value is unused
    :param __: Value is unused
    :param value: The value to parse
    :return: The parsed boolean
    """
    value = value.lower()
    if value in ('1', 'y', 'yes', 'true', 'on'):
        return True
    if value in ('0', 'n', 'no', 'false', 'off'):
        return False
    raise CommandArgumentsError(f'Invalid boolean value: {value}. Should be a sensible value, such as 1, yes, false.')


def float_parser(_, __, value: str) -> float:
    """
    Converts a given string into a floating point number.

    :param _: Value is unused
    :param __: Value is unused
    :param value: The value to parse
    :return: A parsed boolean
    :raises CommandArgumentsError: if the value is not a valid number.
    """
    try:
        return float(value)
    except ValueError:
        raise CommandArgumentsError(f'Invalid float value: {value}. Should be a number.')


def integer_parser(allow_floats: bool = False, base: int = 10) -> typing.Callable[
    ["Context", "Argument", str], typing.Union[int, float]
]:
    """
    Converts a given value into an integer, or a float if allowed.

    :param allow_floats: Whether to allow parsing for floating numbers (decimals). Defaults to False.
    :param base: The base to parse (defaults to base 10, denary)
    :return: The parsed number.
    :raises CommandArgumentsError: if the value is not a valid number.
    """
    def __parser(_, __, v) -> typing.Union[int, float]:
        try:
            return int(v, base)
        except ValueError as e:
            if allow_floats:
                try:
                    return float_parser(_, __, v)
                except CommandArgumentsError as e2:
                    e = e2
            raise CommandArgumentsError(f'Invalid integer value: {v}. Should be a number.', exception=e)

    return __parser


def json_parser(_, __, value: str) -> typing.Union[list, dict, str, int, float, type(None), bool]:
    """
    Converts a given string into a JSON object.

    .. Note::
        If you want this to be fast, you should install orjson. It is a drop-in replacement for the standard library.
        While the parser will still work without it, it may be slower, especially for larger payloads.

    :param _: Value is unused
    :param __: Value is unused
    :param value: The value to parse
    :return: The parsed JSON object
    :raises CommandArgumentsError: if the value is not a valid JSON object.
    """
    try:
        import orjson as json
    except ImportError:
        # Orjson is not installed.
        import json

    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise CommandArgumentsError(f'Invalid JSON value: {value}. Should be a valid JSON object.', exception=e)
