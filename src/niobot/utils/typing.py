import asyncio
import logging
import typing

if typing.TYPE_CHECKING:
    from ..client import NioBot


__all__ = ("Typing",)

log = logging.getLogger(__name__)
_TYPING_STATES: dict[str, "Typing"] = {}


class Typing:
    """
    Context manager to manage typing notifications.

    :param client: The `NioBot` instance
    :param room_id: The room id to send the typing notification to
    :param timeout: The timeout in seconds
    :param persistent: Whether to send a typing notification every `timeout` seconds, to keep the typing status active
    """

    def __init__(self, client: "NioBot", room_id: str, *, timeout: int = 30, persistent: bool = True):
        if room_id in _TYPING_STATES:
            log.warning("A typing notification is already active for this room: %s", _TYPING_STATES[room_id])
        self.room_id = room_id
        self.client = client
        self.persistent = persistent
        self._task = None
        self.timeout = timeout * 1000

    async def persistence_loop(self):
        while True:
            _TYPING_STATES[self.room_id] = self
            await self.client.room_typing(self.room_id, True, timeout=self.timeout)
            await asyncio.sleep(self.timeout - 1000)
            _TYPING_STATES[self.room_id] = self

    async def __aenter__(self):
        """Starts the typing notification loop, or sends a single typing notification if not persistent."""
        if self.room_id in _TYPING_STATES:
            raise RuntimeError("A typing notification is already active for this room", _TYPING_STATES[self.room_id])
        if not self.persistent:
            await self.client.room_typing(self.room_id, True, timeout=self.timeout)
        else:
            self._task = asyncio.create_task(self.persistence_loop())

    async def __aexit__(self, exc_type, exc, tb):
        """Cancels any existing typing loop under this instance and sends a typing notification to stop typing."""
        if self._task:
            self._task.cancel()
        await self.client.room_typing(self.room_id, False)
        _TYPING_STATES.pop(self.room_id, None)
