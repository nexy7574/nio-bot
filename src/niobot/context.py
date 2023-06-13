import nio
import typing

from .utils.string_view import ArgumentView

if typing.TYPE_CHECKING:
    from .client import NioBot
    from .commands import Command
    from .attachment import MediaAttachment


__all__ = (
    "Context",
)


class Context:
    """Event-based context for a command callback"""
    def __init__(
            self,
            _client: "NioBot",
            room: nio.MatrixRoom,
            event: nio.RoomMessageText,
            command: "Command",
            *,
            invoking_string: str = None
    ):
        self._client = _client
        self._room = room
        self._event = event
        self._command = command
        self._invoking_string = invoking_string
        to_parse = event.body
        if invoking_string:
            if invoking_string != event.body:
                to_parse = event.body[len(invoking_string):]
        self._args = ArgumentView(to_parse)
        self._args.parse_arguments()

    @property
    def room(self) -> nio.MatrixRoom:
        """The room that the event was dispatched in"""
        return self._room

    @property
    def client(self) -> "NioBot":
        """The current instance of the client"""
        return self._client

    bot = client

    @property
    def command(self) -> "Command":
        """The current command being invoked"""
        return self.command

    @property
    def args(self) -> list[str]:
        """Each argument given to this command"""
        return self._args.arguments

    arguments = args

    @property
    def message(self) -> nio.RoomMessageText:
        return self._event

    msg = event = message

    async def reply(self, content: str = None, file: "MediaAttachment" = None):
        """Replies to the invoking message."""
        await self.client.send_message(
            self.room,
            content,
            file,
            self.message
        )
