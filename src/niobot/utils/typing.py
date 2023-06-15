import asyncio


__all__ = (
    "Typing",
)


class Typing:
    """Context manager to manage typing notifications."""
    def __init__(self, client, room_id: str, *, timeout: float = 30, persistent: bool = True):
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
        if not self.persistent:
            await self.client.room_typing(self.room_id, True, timeout=self.timeout)
        else:
            self._task = asyncio.create_task(self.persistence_loop())

    async def __aexit__(self, exc_type, exc, tb):
        if self._task:
            self._task.cancel()
        await self.client.room_typing(self.room_id, False)
