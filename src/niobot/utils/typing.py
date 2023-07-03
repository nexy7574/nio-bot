import asyncio
import typing

if typing.TYPE_CHECKING:
    from ..client import NioBot


__all__ = (
    "Typing",
)


class Typing:
    """
    Context manager to manage typing notifications.

    :param client: The `NioBot` instance
    :param room_id: The room id to send the typing notification to
    :param timeout: The timeout in seconds
    :param persistent: Whether to send a typing notification every `timeout` seconds, to keep the typing status active
    """
    def __init__(self, client: "NioBot", room_id: str, *, timeout: int = 30, persistent: bool = True):
        self.room_id = room_id
        self.client = client
        self.persistent = persistent
        self._task = None
        self.timeout = timeout * 1000

    async def persistence_loop(self):
        while True:
            await self.client.room_typing(self.room_id, True, timeout=self.timeout)
            await asyncio.sleep(self.timeout - 1000)

    async def __aenter__(self):
        """Starts the typing notification loop, or sends a single typing notification if not persistent."""
        if not self.persistent:
            await self.client.room_typing(self.room_id, True, timeout=self.timeout)
        else:
            self._task = asyncio.create_task(self.persistence_loop())

    async def __aexit__(self, exc_type, exc, tb):
        """Cancels any existing typing loop under this instance and sends a typing notification to stop typing."""
        if self._task:
            self._task.cancel()
        await self.client.room_typing(self.room_id, False)
