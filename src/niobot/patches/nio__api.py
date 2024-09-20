# Join API fix
from typing import Union as U

from nio import Api, AsyncClient, JoinError, JoinResponse, RoomLeaveError, RoomLeaveResponse

__all__ = ("AsyncClientWithFixedJoin",)


class AsyncClientWithFixedJoin(AsyncClient):
    async def join(self, room_id: str, reason: str = None) -> U[JoinResponse, JoinError]:
        """Joins a room. room_id must be a room ID, not alias"""
        method, path = Api.join(self.access_token, room_id)
        data = {}
        if reason is not None:
            data["reason"] = reason
        return await self._send(JoinResponse, method, path, Api.to_json(data))

    async def room_leave(self, room_id: str, reason: str = None) -> U[RoomLeaveError, RoomLeaveResponse]:
        """Leaves a room. room_id must be an ID, not alias"""
        method, path = Api.room_leave(self.access_token, room_id)
        data = {}
        if reason is not None:
            data["reason"] = reason
        return await self._send(RoomLeaveResponse, method, path, Api.to_json(data))
