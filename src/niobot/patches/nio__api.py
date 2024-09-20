# Join API fix
from typing import Union

from nio import Api, AsyncClient, JoinError, JoinResponse

__all__ = ("AsyncClientWithFixedJoin",)


class AsyncClientWithFixedJoin(AsyncClient):
    async def join(self, room_id: str, reason: str = None) -> Union[JoinResponse, JoinError]:
        """Joins a room. room_id must be a room ID, not alias"""
        method, path = Api.join(self.access_token, room_id)
        data = {}
        if reason is not None:
            data["reason"] = reason
        return await self._send(JoinResponse, method, path, Api.to_json(data))
