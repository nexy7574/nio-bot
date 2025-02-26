import enum
import json
import logging
import os
import time
import typing
import uuid
import warnings

import aiosqlite
import nio

try:
    import orjson
except ImportError:
    orjson = None

if typing.TYPE_CHECKING:
    from ..client import NioBot


__all__ = ("Membership", "SyncStore", "_DudSyncStore")


class Membership(enum.Enum):
    INVITE = "invite"
    JOIN = "join"
    KNOCK = "knock"
    LEAVE = "leave"


class _DudSyncStore:
    """Shell class context manager. Doesn't do anything."""

    def __bool__(self):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class SyncStore:
    """This is the main class for the NioBot Sync Store.

    This class handles the resolution, reading, and storing of important sync events.
    You will usually not need to interact with this.

    :param client: The NioBot client to use
    :param db_path: The path to the database file. If not provided, will resolve to
    `{client.store_path}/sync.db`
    :param important_events: A list of timeline events to keep in the sync store
    :param resolve_state: Whether to resolve the state of the room when storing events.
    Enabling this will reduce the size of your sync store, and may improve load times,
    but may impact save times and resource consuming.
    :param checkpoint_every: The number of changes to make before committing to the database
    """

    IMPORTANT_TIMELINE_EVENTS = (
        "m.room.create",
        "m.room.join_rules",
        "m.room.name",
        "m.room.avatar",
        "m.room.canonical_alias",
        "m.room.history_visibility",
        "m.room.guest_access",
        "m.room.power_levels",
        "m.room.encryption",
        "m.room.topic",
        "m.room.member",
    )
    # [ ["foo $2", [ "foo" ] ] ]
    SCRIPTS: list[list[str, list[typing.Any]]] = [
        [
            """
            CREATE TABLE IF NOT EXISTS niobot_meta (
                next_batch TEXT,
                store_version INTEGER DEFAULT 1
            );
            """,
            [],
        ],
        [
            """
            CREATE TABLE IF NOT EXISTS room_state (
                room_id VARCHAR(255),
                event_type TEXT NOT NULL,
                state_key TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                event_id TEXT UNIQUE,
                origin_server_ts INTEGER,
                unsigned TEXT
            );
            """,
            [],
        ],
        [
            """
            CREATE TABLE IF NOT EXISTS room_summary (
                room_id VARCHAR(255) PRIMARY KEY,
                heroes TEXT,
                invited_member_count INTEGER,
                joined_member_count INTEGER
            );
            """,
            [],
        ],
    ]
    log = logging.getLogger(__name__)

    def __init__(
        self,
        client: "NioBot",
        db_path: typing.Union[os.PathLike, str] = None,
    ):
        self._client = client
        self._db_path = db_path

        self._db: typing.Optional[aiosqlite.Connection] = None
        self.membership_cache: dict[str, int] = {}

    async def _init_db(self):
        if self._db:
            return
        self._db = await aiosqlite.connect(self._db_path)
        self.log.debug("Created database connection.")
        self._db.row_factory = aiosqlite.Row

        for script, args in self.SCRIPTS:
            await self._db.execute(script, *args)

    async def close(self) -> None:
        """Closes the database connection, committing any unsaved data."""
        if self._db:
            await self.commit()
            await self._db.close()
        self._db = None

    async def __aenter__(self) -> "SyncStore":
        await self._init_db()
        self.log.debug("SyncStore initialised via context manager.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        self.log.debug("SyncStore closed via context manager.")

    @staticmethod
    def _resolve_state_list(obj: list[dict[str, typing.Any]]) -> list[dict[str, typing.Any]]:
        resolved = obj.copy()
        for event in obj:
            if isinstance(event.get("unsigned"), dict) and "replaces_state" in event["unsigned"]:
                for r_event in resolved:
                    if r_event.get("event_id") == event["event_id"]:
                        resolved.remove(r_event)
        return resolved

    @staticmethod
    def _create_event_from_row(
        room_id: str,
        event_type: str,
        state_key: str,
        sender: str,
        content_raw: str,
        event_id: str | None,
        origin_server_ts,
        unsigned,
    ) -> dict[str, typing.Any]:
        content = {
            "room_id": room_id,
            "type": event_type,
            "state_key": state_key,
            "sender": sender,
            "content": json.loads(content_raw),
        }
        if event_id:
            content["event_id"] = event_id
        if origin_server_ts is not None:
            content["origin_server_ts"] = origin_server_ts
        if unsigned is not None:
            content["unsigned"] = unsigned
        return content

    async def get_room_state(self, room_id: str) -> list[dict[str, typing.Any]]:
        """
        Fetches the entire state for a given room from the store.

        An empty list is returned if the room does not exist.
        """
        await self._init_db()
        async with self._db.execute(
            """
                SELECT room_id,event_type,state_key,sender,content,event_id,origin_server_ts,unsigned
                FROM room_state
                WHERE room_id = ?
                """,
            (room_id,),
        ) as cursor:
            event_rows = await cursor.fetchall()
            state = list(map(lambda r: self._create_event_from_row(*r), event_rows))
        return self._resolve_state_list(state)

    async def get_room_state_event(
        self, room_id: str, event_type: str, state_key: str = ""
    ) -> dict[str, typing.Any] | None:
        """
        Fetches a state event matching the given criteria for a room from the store.

        Returns `None` if there's no state matching the given criteria.
        """
        await self._init_db()
        async with self._db.execute(
            """
                SELECT room_id,event_type,state_key,sender,content,event_id,origin_server_ts,unsigned
                FROM room_state
                WHERE room_id = ? AND event_type = ? AND state_key = ?
                LIMIT 1
                ORDER BY origin_server_ts DESC
                """,
            (room_id, event_type, state_key),
        ) as cursor:
            row: aiosqlite.Row = await cursor.fetchone()
            if row is None:
                return None
            return self._create_event_from_row(*row)

    async def append_state_event(self, client_event: dict[str, typing.Any], room_id: str | None = None):
        """Appends a new state event into the state store."""
        if isinstance(client_event, (nio.Event, nio.InviteEvent)):
            warnings.warn("Accidentally got an event object instead of source.", stacklevel=2)
            client_event = client_event.source
        elif not isinstance(client_event, dict):
            raise TypeError("Expected a dictionary state event, got %r" % client_event)

        if room_id is None and "room_id" not in client_event:
            raise ValueError("Got a state event for an unknown room!")
        elif room_id is None and "room_id" in client_event:
            room_id = client_event["room_id"]
        elif room_id is not None and "room_id" in client_event:
            if room_id != client_event["room_id"]:
                raise ValueError(
                    f"Received mismatched room IDs for state event - explicitly given {room_id!r}, but event was for"
                    f" {client_event['room_id']!r}"
                )

        if "content" not in client_event:
            raise ValueError("No content in event: %r" % client_event)

        args = [
            room_id,
            client_event["type"],
            client_event["state_key"],
            client_event["sender"],
            json.dumps(client_event["content"], separators=(",", ":")),
            client_event.get("event_id"),
            client_event.get("origin_server_ts"),
        ]
        if client_event.get("unsigned") is not None:
            args.append(json.dumps(client_event["unsigned"], separators=(",", ":")))
        else:
            args.append(None)

        # Check that it is not already in the database
        if event_id := client_event.get("event_id"):
            existing_result = await self._db.execute(
                "SELECT room_id FROM room_state WHERE room_id = ? AND event_id = ?", (room_id, event_id)
            )
            if await existing_result.fetchone():
                self.log.debug(
                    "Refusing to re-append conflicting state event %s in %s: %r", event_id, room_id, client_event
                )
                return
        else:
            existing_result = await self._db.execute(
                "SELECT content FROM room_state WHERE room_id = ? AND event_type = ? AND state_key = ?",
                (room_id, client_event["type"], client_event["state_key"]),
            )
            content = await existing_result.fetchone()
            if content == client_event["content"]:
                self.log.debug("Refusing to append duplicate state event %s in %s: %r", event_id, room_id, client_event)
                return

        await self._db.execute(
            """
            INSERT INTO room_state (room_id,event_type,state_key,sender,content,event_id,origin_server_ts,unsigned)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            args,
        )

    async def get_next_batch(self, user_id: str = None) -> str:
        """Returns the next batch token for the given user ID (or the client's user ID)"""
        await self._init_db()
        user_id = user_id or self._client.user_id
        async with self._db.execute("SELECT next_batch FROM niobot_meta") as cursor:
            result = await cursor.fetchone()
            if result:
                self.log.debug("Next batch record for %r: %r", user_id, result["next_batch"])
                return result["next_batch"]
            self.log.debug("No next batch stored, returning empty token.")
            return ""

    async def set_next_batch(self, user_id: str, next_batch: str) -> None:
        """Sets the next batch token for the given user ID"""
        await self._init_db()
        self.log.debug("Setting next batch to %r for %r.", next_batch, user_id)
        if await self.get_next_batch(""):
            query = "UPDATE niobot_meta SET next_batch = ?"
        else:
            query = "INSERT INTO niobot_meta (next_batch) VALUES (?)"
        await self._db.execute(query, (next_batch,))

    async def handle_sync(self, response: nio.SyncResponse) -> None:
        """Handles a sync response from the server"""
        await self._init_db()
        self.log.debug("Handling sync: %r", response.uuid or uuid.uuid4())

        for room_id, room in response.rooms.invite.items():
            self.membership_cache[room_id] = 1
            for event in room.invite_state:
                try:
                    await self.append_state_event(event.source, room_id)
                except (TypeError, ValueError) as e:
                    self.log.warning(
                        "Failed to append state event %r in %s: %r",
                        room_id,
                        event,
                        e,
                        exc_info=e,
                    )

        for room_id, room in response.rooms.join.items():
            self.membership_cache[room_id] = 2
            for event in room.state:
                try:
                    await self.append_state_event(event.source, room_id)
                except (TypeError, ValueError) as e:
                    self.log.warning(
                        "Failed to append state event %r in %s: %r",
                        room_id,
                        event,
                        e,
                        exc_info=e,
                    )

        for room_id, room in response.rooms.leave.items():
            self.membership_cache[room_id] = 0
            await self._db.execute(
                """
                DELETE FROM room_state WHERE room_id = ?
                """,
                (room_id,),
            )
            await self._db.execute("DELETE FROM room_summary WHERE room_id = ?", (room_id,))

        await self.set_next_batch(self._client.user_id, response.next_batch)
        await self.commit()

    async def generate_sync(self) -> nio.SyncResponse:
        """Generates a sync response, ready for replaying."""
        # I wonder if an incremental sync would make sense here
        # Large accounts in lots of rooms or with complex states will struggle with this replay
        # because the construction of the SyncResponse dataclass does a lot of validation and is
        # very expensive.
        # Incrementally returning little bits of the sync would probably be better in this scenario, but I feel there
        # may be unintended side effects of this.
        # log = self.log.getChild("generate_sync")
        payload = {
            "next_batch": await self.get_next_batch(self._client.user_id),
            "rooms": {"invite": {}, "join": {}, "leave": {}},
        }
        # TODO: convert this to new format
        # async with self._db.execute('SELECT * FROM "rooms.join"') as cursor:
        #     async for row in cursor:
        #         self.log.debug("Loading state for joined room %r", row["room_id"])
        #         summary = await self.aloads(row["summary"])
        #         timeline_events = await self.aloads(row["timeline"])
        #         state_events = await self.aloads(row["state"])
        #         account_data = await self.aloads(row["account_data"])
        #         payload["rooms"]["join"][row["room_id"]] = {
        #             "timeline": {"events": timeline_events},
        #             "state": {"events": state_events},
        #             "account_data": {"events": account_data},
        #             "summary": summary,
        #             "ephemeral": {},
        #         }
        #         log.debug("Added room %r to `rooms.join`", row["room_id"])
        #
        # async with self._db.execute('SELECT room_id, state FROM "rooms.invite"') as cursor:
        #     async for row in cursor:
        #         log.debug("Loading state for invited room %r", row["room_id"])
        #         payload["rooms"]["invite"][row["room_id"]] = {"invite_state": {"events": json.loads(row["state"])}}
        #         log.debug("Added room %r to `rooms.invite`", row["room_id"])
        #
        # async with self._db.execute('SELECT * FROM "rooms.leave"') as cursor:
        #     async for row in cursor:
        #         log.debug("Loading state for left room %r", row["room_id"])
        #         payload["rooms"]["leave"][row["room_id"]] = {
        #             "timeline": {"events": json.loads(row["timeline"])},
        #             "state": {"events": json.loads(row["state"])},
        #             "account_data": {"events": json.loads(row["account_data"])},
        #             "summary": {},
        #             "ephemeral": {},
        #         }
        #         log.debug("Added room %r to `rooms.leave`", row["room_id"])

        return nio.SyncResponse.from_dict(payload)

    async def commit(self) -> None:
        """Forcefully writes unsaved changes to the database, without closing the connection"""
        await self._db.commit()
        self._last_commit = time.monotonic()
        self._change_count = self._db.total_changes

    def __bool__(self):
        return True
