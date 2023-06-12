import nio
import typing

if typing.TYPE_CHECKING:
    from ..client import NioBot


__all__ = (
    "Context",
)


class Context:
    """Event-based context for a command callback"""
    def __init__(
            self,
            _client: "NioBot",
            room: nio.MatrixRoom,
            event: nio.Event,
            command: str = None
    ):
        self._client = _client
        self._room = room
        self._event = event

    @property
    def room(self) -> nio.MatrixRoom:
        """The room that the event was dispatched in"""
        return self._room

    @property
    def client(self) -> "NioBot":
        """The current instance of the client"""
        return self._client

    @property
    def bot(self) -> "NioBot":
        """The current instance of the client"""
        return self._client

    async def reply(self, content: str = None, body_type: str = "org.matrix.custom.html"):
        """Replies to the invoking message."""
        await self._client.room_send(
            self._room.room_id,
            "m.room.message",
            {
                "msgtype": "m.notice",
                "body": content,
                "format": body_type,
                "formatted_body": content,
                "m.relates_to": {
                    "m.in_reply_to": {
                        "event_id": self._event.event_id,
                    }
                }
            },
        )

