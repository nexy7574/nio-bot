"""
This utility modules contains a handful of simple off-the-shelf parser for some basic python types.
"""

import abc
import re
import typing
import urllib.parse as urllib
from collections import namedtuple
from typing import Union as U

import nio

from ..exceptions import CommandParserError
from .lib import deprecated

if typing.TYPE_CHECKING:
    from ..commands import Argument
    from ..context import Context

try:
    import orjson as json
except ImportError:
    # Orjson is not installed.
    import json


__all__ = (
    "Parser",
    "StatelessParser",
    "BooleanParser",
    "FloatParser",
    "IntegerParser",
    "JSONParser",
    "EventParser",
    "RoomParser",
    "BUILTIN_MAPPING",
    "MATRIX_TO_REGEX",
    "MatrixToLink",
    "MatrixMXCUrl",
    "MatrixToParser",
    "MXCParser",
    # And the deprecated aliases
    "boolean_parser",
    "float_parser",
    "integer_parser",
    "json_parser",
    "room_parser",
    "event_parser",
    "matrix_to_parser",
    "mxc_parser",
)
MATRIX_TO_REGEX = re.compile(
    r"(http(s)?://)?matrix\.to/#/(?P<room_id>[^/]+)(/(?P<event_id>[^/?&#]+))?(?P<qs>([&?](via=[^&]+))*)?",
)
MatrixToLink = namedtuple("MatrixToLink", ("room", "event", "query"), defaults=("", "", ""))
MatrixMXCUrl = namedtuple("MatrixMXCUrl", ("server", "media_id"), defaults=(None, None))


class Parser(abc.ABC):
    """
    A base model class for parsers.

    This ABC defines one uniform method, which is `__call__`, which takes a [Context][niobot.context.Context] instance,
    [Argument][niobot.commands] instance, and the user-provided string value.

    This parser is designed to be instantiated, and then called with the above arguments.
    If you want to make a simple parser that does not take additional configuration, it is recommended to use
    [StatelessParser][niobot.utils.parsers.StatelessParser] instead.
    """

    @abc.abstractmethod
    def __call__(self, ctx: "Context", arg: "Argument", value: str) -> typing.Optional[typing.Any]: ...


class StatelessParser(Parser, abc.ABC):
    r"""
    A parser base that will not be instantiated, but rather called directly.

    This is useful for parsers that do not take any configuration
    (such as the simple [BooleanParser][niobot.utils.parsers]), where a
    simple one-off call is enough.

    Traditionally, you'd call a [Parser][niobot.utils.parsers] like this:

    ```python
    parser = Parser(my_argument=True)
    result = parser(ctx, arg, value)
    # or, in one line
    result = Parser(my_argument=True)(ctx, arg, value)
    ```

    However, for some simple parsers, there's no need to instantiate them. Instead, you can call them directly.
    The `StatelessParser` ABC adds the `parse` classmethod, meaning you can simply do the following:

    ```python
    result = Parser.parse(ctx, arg, value)
    ```
    Which is just a shortand for the above one-liner.
    This offers little to no performance benefit, however can make code look cleaner.

    As this ABC subclasses the regular [Parser][niobot.utils.parsers],
    you can still use the traditional instantiation+call method.
    """

    @classmethod
    def parse(cls, ctx: "Context", arg: "Argument", value: str) -> typing.Optional[typing.Any]:
        r"""Parses the given value using this parser without needing to call \_\_init\_\_() first.

        :param ctx: The context instance
        :param arg: The argument instance
        :param value: The value to parse
        :return: The parsed value
        :rtype: typing.Optional[typing.Any]"""
        return cls()(ctx, arg, value)


class BooleanParser(StatelessParser):
    """
    Converts a given string into a boolean. Value is casefolded before being parsed.

    The following resolves to true:
    * 1, y, yes, true, on

    The following resolves to false:
    * 0, n, no, false, off

    The following will raise a command argument error: anything else

    :return: A parsed boolean
    :rtype: bool
    """

    def __call__(self, ctx: "Context", arg: "Argument", value: str) -> bool:
        value = value.casefold()
        if value in {"1", "y", "yes", "true", "on"}:
            return True
        if value in {"0", "n", "no", "false", "off"}:
            return False
        raise CommandParserError(f"Invalid boolean value: {value}. Should be a sensible value, such as 1, yes, false.")


class FloatParser(StatelessParser):
    """
    Converts a given string into a floating point number.

    :return: A parsed floating point number
    :rtype: float
    :raises CommandParserError: if the value is not a valid number.
    """

    def __call__(self, ctx: "Context", arg: "Argument", value: str) -> float:
        try:
            return float(value)
        except ValueError:
            raise CommandParserError(f"Invalid float value: {value}. Should be a number.")


class IntegerParser(Parser):
    """
    Parses an integer, or optionally a real number.

    :param allow_floats: Whether to simply defer non-explicit-integer values to the float parser.
        This results in the return type being [float][]
    :param base: The base to parse the integer in. Defaults to 10 (denary). 2 is Binary, and 16 is Hexadecimal.
    :return: A parsed integer or float, depending on input & allow_floats
    :rtype: Union[int, float]
    :raises CommandParserError: if the value is not a valid number.
    """

    def __init__(self, allow_floats: bool = False, base: int = 10):
        self.allow_floats = allow_floats
        self.base = base

    def __call__(self, ctx: "Context", arg: "Argument", value: str) -> U[int, float]:
        try:
            return int(value, self.base)
        except ValueError:
            if self.allow_floats:
                try:
                    return float(value)
                except ValueError as e:
                    raise CommandParserError(f"Invalid integer value: {value}. Should be a number.", exception=e)
            raise CommandParserError(f"Invalid integer value: {value}. Should be a number.")


class JSONParser(StatelessParser):
    """
    Converts a given string into a JSON object.

    !!! note "Performance boost"
        If you want this to be fast, you should install orjson. It is a drop-in replacement for the standard library.
        While the parser will still work without it, it may be slower, especially for larger payloads.

    :return: The parsed JSON object
    :rtype: Union[dict, list, str, int, float, None, bool]
    :raises CommandParserError: if the value is not a valid JSON object.
    """

    def __call__(self, ctx: "Context", arg: "Argument", value: str) -> typing.Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise CommandParserError(f"Invalid JSON value: {value}. Should be a valid JSON object.", exception=e)


class RoomParser(StatelessParser):
    """
    Parses a room ID, alias, or matrix.to link into a MatrixRoom object.

    ??? warning "This parser is async"
        This parser is async, and should be awaited when used manually.

    :return: The parsed room instance
    :rtype: nio.MatrixRoom
    """

    @staticmethod
    async def internal(ctx: "Context", value: str) -> nio.MatrixRoom:
        if value.startswith("!"):
            # Room ID
            room = ctx.client.rooms.get(value)
        elif value.startswith("#"):
            # Room alias
            # Attempt to find the room in the cache, before requesting it from the server
            for room in ctx.client.rooms.values():
                room: nio.MatrixRoom
                if value == room.canonical_alias:
                    break
            else:
                room: U[nio.RoomResolveAliasResponse, nio.RoomResolveAliasError] = await ctx.client.room_resolve_alias(
                    value
                )
                if isinstance(room, nio.RoomResolveAliasError):
                    raise CommandParserError(f"Invalid room alias: {value}.", response=room)
                room = ctx.client.rooms.get(room.room_id)
        elif m := MATRIX_TO_REGEX.match(value):
            # matrix.to link
            groups = m.groupdict()
            if "room_id" not in groups:
                raise CommandParserError(f"Invalid matrix.to link: {value} (no room).")
            room = ctx.client.rooms.get(groups["room_id"])
        else:
            raise CommandParserError(f"Invalid room ID, alias, or matrix.to link: {value!r}.")

        if room is None:
            raise CommandParserError("No room with that ID, alias, or matrix.to link found.")
        return room

    def __call__(self, ctx, arg, value: str) -> typing.Coroutine[typing.Any, typing.Any, nio.MatrixRoom]:
        return self.internal(ctx, value)


class EventParser(Parser):
    """
    Parses an event reference from either its ID, or matrix.to link.

    :param event_type: The event type to expect (such as m.room.message). If None, any event type is allowed.
    :return: The actual internal (async) parser.
    :rtype: typing.Coroutine
    """

    def __init__(self, event_type: typing.Optional[str] = None):
        self.event_type = event_type

    async def internal(self, ctx: "Context", value: str) -> nio.Event:
        room_id = ctx.room.room_id
        if m := MATRIX_TO_REGEX.match(value):
            # matrix.to link
            groups = m.groupdict()
            if "room_id" not in groups:
                raise CommandParserError(f"Invalid matrix.to link: {value} (no room).")
            if "event_id" not in groups:
                raise CommandParserError(f"Invalid matrix.to link: {value} (expected an event).")
            value = groups["event_id"]
            room_id = groups["room_id"]
            value = urllib.unquote(value)
            room_id = urllib.unquote(room_id)

        if value.startswith("$"):
            # from raw ID
            event: U[nio.RoomGetEventResponse, nio.RoomGetEventError] = await ctx.client.room_get_event(room_id, value)
            if not isinstance(event, nio.RoomGetEventResponse):
                raise CommandParserError(f"Invalid event ID: {value}.", response=event)
            event: nio.Event = event.event
            if self.event_type is not None and self.event_type != event.source.get("type"):
                raise CommandParserError(
                    f"Invalid event ID: {value} (expected {self.event_type}, got {event.source.get('type')})."
                )
            return event
        else:
            raise CommandParserError(f"Invalid event ID or matrix.to link: {value!r}.")

    def __call__(self, *args, **kwargs) -> typing.Coroutine[typing.Any, typing.Any, nio.Event]:
        return self.internal(*args, **kwargs)


class MatrixDotToParser(Parser):
    """
    Converts a matrix.to link into a MatrixRoomLink namedtuple, which consists of the room, event, and any query
    passed to the URL.

    :param domain: The domain to check for. Defaults to matrix.to, consistent with average client behaviour.
    :param require_room: Whether to require the room part of this url to be present
    :param require_event: Whether to require the event part of this url to be present
    :param allow_user_as_room: Whether to allow user links as room links
    :param stateless: If true, the link will only be parsed, not resolved. This means rooms will stay as their IDs, etc.
    :return: The actual internal (async) parser.
    :rtype: typing.Coroutine
    """

    def __init__(
        self,
        domain: str = "matrix.to",
        require_room: bool = True,
        require_event: bool = False,
        allow_user_as_room: bool = True,
        *,
        stateless: bool = False,
    ):
        self.domain = domain
        self.require_room = require_room
        self.require_event = require_event
        self.allow_user_as_room = allow_user_as_room
        self.stateless = stateless

    async def internal(self, ctx: "Context", value: str) -> MatrixToLink:
        if not (m := MATRIX_TO_REGEX.match(value)):
            raise CommandParserError(f"Invalid matrix.to link: {value!r}.")

        # matrix.to link
        groups = m.groupdict()
        event_id = groups.get("event_id", "")
        room_id = groups.get("room_id", "")
        event_id = urllib.unquote(event_id or "")
        room_id = urllib.unquote(room_id or "")

        if self.require_room and not room_id:
            raise CommandParserError(f"Invalid matrix.to link: {value} (no room).")
        if self.require_event and not event_id:
            raise CommandParserError(f"Invalid matrix.to link: {value} (no event).")

        if room_id.startswith("@") and not self.allow_user_as_room:
            raise CommandParserError(f"Invalid matrix.to link: {value} (expected room, got user).")

        if self.stateless:
            room = room_id
        else:
            if room_id.startswith("@"):
                dm_rooms = await ctx.client.get_dm_rooms(room_id)
                if not dm_rooms:
                    new_dm_room = await ctx.client.create_dm_room(room_id)
                    dm_rooms.append(new_dm_room.room_id)
                room_id = dm_rooms[0]
            room = ctx.client.rooms.get(room_id)
            if room is None:
                raise CommandParserError("No room with that ID, alias, or matrix.to link found.")

        if event_id and not self.stateless:
            event: U[nio.RoomGetEventResponse, nio.RoomGetEventError] = await ctx.client.room_get_event(
                room_id, event_id
            )
            if not isinstance(event, nio.RoomGetEventResponse):
                raise CommandParserError(f"Invalid event ID: {event_id}.", response=event)
            event: nio.Event = event.event
        elif self.stateless:
            event: str = event_id
        else:
            event: None = None
        return MatrixToLink(room, event, groups.get("qs"))

    def __call__(
        self, ctx: "Context", arg: "Argument", value: str
    ) -> typing.Coroutine[typing.Any, typing.Any, MatrixToLink]:
        return self.internal(ctx, value)


MatrixToParser = MatrixDotToParser


class MXCParser(StatelessParser):
    """
    Parses an MXC URL into a MatrixMXCUrl namedtuple, which consists of the server and media ID.

    :return: The parsed MXC URL
    :rtype: MatrixMXCUrl (namedtuple)
    """

    def __call__(self, ctx, arg, value: str) -> MatrixMXCUrl:
        if not value.startswith("mxc://"):
            raise CommandParserError(f"Invalid MXC URL: {value!r}.")
        parsed = urllib.urlparse(value, "mxc://", allow_fragments=False)
        if not parsed.path:
            raise CommandParserError(f"Invalid MXC URL: {value!r} (missing media ID).")
        if parsed.path == "/":
            raise CommandParserError(f"Invalid MXC URL: {value!r} (no media ID).")
        if not parsed.netloc:
            raise CommandParserError(f"Invalid MXC URL: {value!r} (no server).")

        return MatrixMXCUrl(parsed.netloc, parsed.path[1:])


class MatrixUserParser(StatelessParser):
    """
    Parses a string into a MatrixUser instance from matrix-nio.
    """

    def __call__(self, ctx, arg, value):
        if not value.startswith("@"):
            raise CommandParserError(f"Invalid matrix user ID: {value!r}.")

        # Check the local room for the user
        for member in ctx.room.users.values():
            if member.user_id == value:
                return member
        raise CommandParserError(f"Invalid matrix user ID: {value!r} (not in room).")


BUILTIN_MAPPING = {
    bool: BooleanParser(),
    float: FloatParser(),
    int: IntegerParser(),
    list: JSONParser(),
    dict: JSONParser(),
    nio.RoomMessageText: EventParser("m.room.message"),
    nio.Event: EventParser(),
    nio.MatrixRoom: RoomParser(),
    nio.MatrixUser: MatrixUserParser(),
    MatrixToLink: MatrixDotToParser(),
}
# Now add the aliases for backward compatability with <1.1.0
# These will be removed in 1.2.0.


@deprecated("niobot.utils.parsers.BooleanParser")
def boolean_parser(*args, **kwargs):
    """Deprecated boolean parser. Please use niobot.utils.parsers.BooleanParser instead.

    !!! danger "Deprecated function"
        This function is deprecated and will be removed in 1.2.0.
    """
    return BooleanParser.parse(*args, **kwargs)


@deprecated("niobot.utils.parsers.FloatParser")
def float_parser(*args, **kwargs):
    """Deprecated float parser. Please use niobot.utils.parsers.FloatParser instead.

    !!! danger "Deprecated function"
        This function is deprecated and will be removed in 1.2.0.
    """
    return FloatParser.parse(*args, **kwargs)


@deprecated("niobot.utils.parsers.IntegerParser")
def integer_parser(allow_floats: bool = False, base: int = 10):
    """Deprecated integer parser. Please use niobot.utils.parsers.IntegerParser instead.

    !!! danger "Deprecated function"
        This function is deprecated and will be removed in 1.2.0.
    """
    return IntegerParser(allow_floats, base)


@deprecated("niobot.utils.parsers.JSONParser")
def json_parser(*args, **kwargs):
    """Deprecated integer parser. Please use niobot.utils.parsers.JSONParser instead.

    !!! danger "Deprecated function"
        This function is deprecated and will be removed in 1.2.0.
    """
    return JSONParser.parse(*args, **kwargs)


@deprecated("niobot.utils.parsers.RoomParser")
def room_parser(*args, **kwargs):
    """Deprecated room parser. Please use niobot.utils.parsers.RoomParser instead.

    !!! danger "Deprecated function"
        This function is deprecated and will be removed in 1.2.0.
    """
    return RoomParser.parse(*args, **kwargs)


@deprecated("niobot.utils.parsers.EventParser")
def event_parser(event_type: typing.Optional[str] = None):
    """Deprecated event parser. Please use niobot.utils.parsers.EventParser instead.

    !!! danger "Deprecated function"
        This function is deprecated and will be removed in 1.2.0.
    """
    return EventParser(event_type)


@deprecated("niobot.utils.parsers.MatrixDotToParser")
def matrix_to_parser(require_room: bool = True, require_event: bool = False, allow_user_as_room: bool = True):
    """Deprecated matrix.to parser. Please use niobot.utils.parsers.MatrixDotToParser instead.

    !!! danger "Deprecated function"
        This function is deprecated and will be removed in 1.2.0.
    """
    return MatrixDotToParser("matrix.to", require_room, require_event, allow_user_as_room)


@deprecated("niobot.utils.parsers.MXCParser")
def mxc_parser(*args, **kwargs):
    """Deprecated MXC parser. Please use niobot.utils.parsers.MXCParser instead.

    !!! danger "Deprecated function"
        This function is deprecated and will be removed in 1.2.0.
    """
    return MXCParser.parse(*args, **kwargs)
