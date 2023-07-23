"""
This utility modules contains a handful of simple off-the-shelf parser for some basic python types.
"""

import re
import typing
import urllib.parse as urllib
from collections import namedtuple

import nio

from ..exceptions import CommandParserError

if typing.TYPE_CHECKING:
    from ..commands import Argument
    from ..context import Context


__all__ = (
    "boolean_parser",
    "float_parser",
    "integer_parser",
    "json_parser",
    "event_parser",
    "room_parser",
    "BUILTIN_MAPPING",
    "MATRIX_TO_REGEX",
    "MatrixToLink",
    "MatrixMXCUrl",
    "matrix_to_parser",
    "mxc_url_parser",
)
MATRIX_TO_REGEX = re.compile(
    r"(http(s)?://)?matrix\.to/#/(?P<room_id>[^/]+)(/(?P<event_id>[^/?&#]+))?(?P<qs>([&?](via=[^&]+))*)?",
)
MatrixToLink = namedtuple("MatrixToLink", ("room", "event", "query"), defaults=(None, None, None))
MatrixMXCUrl = namedtuple("MatrixMXCUrl", ("server", "media_id"), defaults=(None, None))


def boolean_parser(_: "Context", __, value: str) -> bool:
    """
    Converts a given string into a boolean. Value is lower-cased before being parsed.

    The following resolves to true:
    * 1, y, yes, true, on

    The following resolves to false:
    * 0, n, no, false, off

    The following will raise a command argument error: anything else

    :return: The parsed boolean
    """
    value = value.lower()
    if value in ("1", "y", "yes", "true", "on"):
        return True
    if value in ("0", "n", "no", "false", "off"):
        return False
    raise CommandParserError(f"Invalid boolean value: {value}. Should be a sensible value, such as 1, yes, false.")


def float_parser(_: "Context", __: "Argument", value: str) -> float:
    """
    Converts a given string into a floating point number.

    :return: A parsed boolean
    :raises CommandParserError: if the value is not a valid number.
    """
    try:
        return float(value)
    except ValueError:
        raise CommandParserError(f"Invalid float value: {value}. Should be a number.")


def integer_parser(
    allow_floats: bool = False, base: int = 10
) -> typing.Callable[["Context", "Argument", str], typing.Union[int, float]]:
    """
    Converts a given value into an integer, or a float if allowed.

    :param allow_floats: Whether to allow parsing for floating numbers (decimals). Defaults to False.
    :param base: The base to parse (defaults to base 10, denary)
    :return: The parsed number.
    :raises CommandParserError: if the value is not a valid number.
    """

    def __parser(_, __, v) -> typing.Union[int, float]:
        try:
            return int(v, base)
        except ValueError as e:
            if allow_floats:
                try:
                    return float_parser(_, __, v)
                except CommandParserError as e2:
                    e = e2
            raise CommandParserError(f"Invalid integer value: {v}. Should be a number.", exception=e)

    return __parser


def json_parser(
    _: "Context", __: "Argument", value: str
) -> typing.Union[list, dict, str, int, float, type(None), bool]:
    """
    Converts a given string into a JSON object.

    !!! note "Performance boost"
        If you want this to be fast, you should install orjson. It is a drop-in replacement for the standard library.
        While the parser will still work without it, it may be slower, especially for larger payloads.

    :return: The parsed JSON object
    :raises CommandParserError: if the value is not a valid JSON object.
    """
    try:
        import orjson as json
    except ImportError:
        # Orjson is not installed.
        import json

    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise CommandParserError(f"Invalid JSON value: {value}. Should be a valid JSON object.", exception=e)


async def room_parser(ctx: "Context", arg: "Argument", value: str) -> nio.MatrixRoom:
    """
    Parses a room ID, alias, or matrix.to link into a MatrixRoom object.

    ??? warning "This parser is async"
        This parser is async, and should be awaited when used manually.

    :return: The MatrixRoom object
    """
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
            room: nio.RoomResolveAliasResponse | nio.RoomResolveAliasError = await ctx.client.room_resolve_alias(value)
            if isinstance(room, nio.RoomResolveAliasError):
                raise CommandParserError(f"Invalid room alias: {value}.", response=room)
            room = ctx.client.rooms.get(room.room_id)
    elif m := MATRIX_TO_REGEX.match(value):
        # matrix.to link
        groups = m.groupdict()
        if "room_id" not in groups:
            raise CommandParserError(f"Invalid matrix.to link: {value} (no room).")
        room_id = urllib.unquote(groups["room_id"])
        room = ctx.client.rooms.get(groups["room_id"])
    else:
        raise CommandParserError(f"Invalid room ID, alias, or matrix.to link: {value!r}.")

    if room is None:
        raise CommandParserError(f"No room with that ID, alias, or matrix.to link found.")
    return room


def event_parser(
    event_type: str = None,
) -> typing.Callable[["Context", "Argument", str], typing.Coroutine[typing.Any, typing.Any, nio.Event]]:
    """
    Parses an event reference from either its ID, or matrix.to link.

    :param event_type: The event type to expect (such as m.room.message). If None, any event type is allowed.
    :return: The actual internal (async) parser.
    """

    async def internal(ctx: "Context", _, value: str) -> nio.Event:
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
            event: nio.RoomGetEventResponse | nio.RoomGetEventError = await ctx.client.room_get_event(room_id, value)
            if not isinstance(event, nio.RoomGetEventResponse):
                raise CommandParserError(f"Invalid event ID: {value}.", response=event)
            event: nio.Event = event.event
            if event_type is not None and event_type != event.source.get("type"):
                raise CommandParserError(
                    f"Invalid event ID: {value} (expected {event_type}, got {event.source.get('type')})."
                )
            return event
        else:
            raise CommandParserError(f"Invalid event ID or matrix.to link: {value!r}.")

    return internal


def matrix_to_parser(
    require_room: bool = True, require_event: bool = False, allow_user_as_room: bool = True
) -> typing.Callable[["Context", "Argument", str], typing.Coroutine[typing.Any, typing.Any, MatrixToLink],]:
    """
    Advanced multi-functional parser for matrix.to links.

    This parser takes an https://matrix.to link, and breaks it down into room-id and event-id where applicable. It then
    returns all of these as a namedtuple.

    :param require_room: Whether to require the room part of this url to be present
    :param require_event: Whether to require the event part of this url to be present
    :param allow_user_as_room: Whether to allow user links as room links
    :return: The actual internal (async) parser.
    """

    async def internal(ctx: "Context", _, value: str) -> MatrixToLink:
        if m := MATRIX_TO_REGEX.match(value):
            # matrix.to link
            groups = m.groupdict()
            event_id = groups.get("event_id", "")
            room_id = groups.get("room_id", "")
            event_id = urllib.unquote(event_id)
            room_id = urllib.unquote(room_id)

            if require_room and not room_id:
                raise CommandParserError(f"Invalid matrix.to link: {value} (no room).")
            if require_event and not event_id:
                raise CommandParserError(f"Invalid matrix.to link: {value} (no event).")

            if room_id.startswith("@") and not allow_user_as_room:
                raise CommandParserError(f"Invalid matrix.to link: {value} (expected room, got user).")

            if room_id.startswith("@"):
                room = await ctx.client.get_dm_room(room_id)
            else:
                room = ctx.client.rooms.get(room_id)

            if room is None:
                raise CommandParserError(f"No room with that ID, alias, or matrix.to link found.")

            if event_id:
                event: nio.RoomGetEventResponse | nio.RoomGetEventError = await ctx.client.room_get_event(
                    room_id, event_id
                )
                if not isinstance(event, nio.RoomGetEventResponse):
                    raise CommandParserError(f"Invalid event ID: {event_id}.", response=event)
                event: nio.Event = event.event
            else:
                event: None = None
            return MatrixToLink(room, event, groups.get("qs"))
        else:
            raise CommandParserError(f"Invalid matrix.to link: {value!r}.")

    return internal


def mxc_url_parser(_, __, value: str) -> MatrixMXCUrl:
    """
    Parses an MXC URL. Basically just a validator
    """
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


BUILTIN_MAPPING = {
    bool: boolean_parser,
    float: float_parser,
    int: integer_parser,
    list: json_parser,
    dict: json_parser,
    nio.RoomMessageText: event_parser("m.room.message"),
    nio.Event: event_parser(),
    nio.MatrixRoom: room_parser,
    MatrixToLink: matrix_to_parser(require_event=True),
}
