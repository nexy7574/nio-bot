import nio
import typing

from .context import Context

if typing.TYPE_CHECKING:
    from .client import NioBot


class Command:
    """Represents a command."""
    def __init__(
            self,
            name: str,
            callback: callable,
            *,
            aliases: list[str] = None,
            description: str = None,
            disabled: bool = False
    ):
        self.name = name
        self.callback = callback
        self.description = description
        self.disabled = disabled
        self.aliases = aliases or []

    def __repr__(self):
        return "<Command name={0.name} aliases={0.aliases} disabled={0.disabled}>".format(self)

    def __str__(self):
        return self.name

    def construct_context(self, client: "NioBot", room: nio.MatrixRoom, event: nio.RoomMessageText) -> Context:
        return Context(client, room, event, self)
