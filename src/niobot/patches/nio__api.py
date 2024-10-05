# Join API fix
import logging
from typing import Union as U

from nio import (
    Api,
    AsyncClient,
    DirectRoomsResponse,
    JoinError,
    JoinResponse,
    Response,
    RoomLeaveError,
    RoomLeaveResponse,
)

__all__ = ("AsyncClientWithFixedJoin",)
logger = logging.getLogger(__name__)


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
        r = await self._send(RoomLeaveResponse, method, path, Api.to_json(data))
        if isinstance(r, RoomLeaveResponse):
            logger.debug("Left a room successfully. Updating account data if it was a DM room.")
            # Remove from account data
            # First, need to get the DM list.
            # THIS IS NOT THREAD SAFE
            # hell it probably isn't even async safe.
            rooms = await self.list_direct_rooms()
            # NOW it's fine
            cpy = rooms.rooms.copy()

            updated = False
            if isinstance(rooms, DirectRoomsResponse):
                for user_id, dm_rooms in rooms.rooms.items():
                    for dm_room_id in dm_rooms:
                        if dm_room_id == room_id:
                            cpy[user_id].remove(room_id)
                            updated = True
                            break
                else:
                    logger.warning("Room %s not found in DM list. Possibly not a DM.", room_id)

            if updated:
                logger.debug(f"Updating DM list in account data from {rooms.rooms} to {cpy}")
                # Update the DM list
                method, path = "PUT", Api._build_path(["user", self.user_id, "account_data", "m.direct"])
                logger.debug("Account data response: %r", await self._send(Response, method, path, Api.to_json(cpy)))
        return r
