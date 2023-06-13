from .context import Context

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
        return f"<Command name={self.name} aliases={self.aliases}>"

    def __str__(self):
        return self.name

    @staticmethod
    def construct_context(self, client, room, event):
        return Context(client, room, event)
