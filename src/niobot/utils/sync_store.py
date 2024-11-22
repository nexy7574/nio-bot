import dataclasses
import enum
import json
import logging
import os
import typing
import uuid

import aiosqlite
import nio

if typing.TYPE_CHECKING:
    from ..client import NioBot


__all__ = ("Membership", "SyncStore", "_DudSyncStore")


class Membership(enum.Enum):
    INVITE = "invite"
    JOIN = "join"
    KNOCK = "knock"
    LEAVE = "leave"


class _DudSyncStore:
    """
    Shell class context manager. Doesn't do anything.
    """

    def __bool__(self):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class SyncStore:
    """
    This is the main class for the NioBot Sync Store.

    This class handles the resolution, reading, and storing of important sync events.
    You will usually not need to interact with this.

    :param client: The NioBot client to use
    :param db_path: The path to the database file. If not provided, will resolve to
    `{client.store_path}/sync.db`
    :param important_events: A list of timeline events to keep in the sync store
    :param resolve_state: Whether to resolve the state of the room when storing events.
    Enabling this will reduce the size of your sync store, and may improve load times,
    but may impact save times and resource consuming.
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
    SCRIPTS = [
        [
            (
                """
                CREATE TABLE IF NOT EXISTS "rooms.invite" (
                    room_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL
                );
                """,
                [],
            ),
            (
                """
                CREATE TABLE IF NOT EXISTS "rooms.join" (
                    room_id TEXT PRIMARY KEY,
                    account_data TEXT NOT NULL,
                    state TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    timeline TEXT NOT NULL
                );
                """,
                [],
            ),
            (
                """
                CREATE TABLE IF NOT EXISTS "rooms.knock" (
                    room_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL
                );
                """,
                [],
            ),
            (
                """
                CREATE TABLE IF NOT EXISTS "rooms.leave" (
                    room_id TEXT PRIMARY KEY,
                    account_data TEXT NOT NULL,
                    state TEXT NOT NULL,
                    timeline TEXT NOT NULL
                );
                """,
                [],
            ),
            (
                """
                CREATE TABLE IF NOT EXISTS "meta" (
                    user_id TEXT PRIMARY KEY,
                    next_batch TEXT DEFAULT ''
                )
                """,
                (),
            ),
        ]
    ]
    log = logging.getLogger(__name__)

    def __init__(
        self,
        client: "NioBot",
        db_path: typing.Union[os.PathLike, str] = None,
        important_events: typing.Iterable[str] = IMPORTANT_TIMELINE_EVENTS,
        resolve_state: bool = False,
    ):
        self._client = client
        self._db_path = db_path
        self.important_events = tuple(important_events)
        self.resolve_state = resolve_state
        self._db: typing.Optional[aiosqlite.Connection] = None

    async def _init_db(self):
        if self._db:
            return
        self._db = await aiosqlite.connect(self._db_path)
        self.log.debug("Created database connection.")
        self._db.row_factory = aiosqlite.Row

        for migration in self.SCRIPTS:
            for script, args in migration:
                await self._db.execute(script, *args)
            await self._db.commit()

    async def close(self) -> None:
        """
        Closes the database connection, committing any unsaved data.
        """
        if self._db:
            await self._db.commit()
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
    def dumps(obj: typing.Any) -> str:
        return json.dumps(obj, separators=(",", ":"))

    async def _pop_from(self, room_id: str, *old_states: str) -> None:
        """Removes the given room ID from *old_states"""
        # If you hold this function incorrectly, you are vulnerable to SQL injection.
        # The library does not hold this function incorrectly.
        for old_state in old_states:
            self.log.debug("Removing %r from the %r state, if it is in there.", room_id, old_state)
            table = f"rooms.{old_state}"
            await self._db.execute(f'DELETE FROM "{table}" WHERE room_id=?', (room_id,))

    async def process_invite(self, room_id: str, info: nio.InviteInfo) -> None:
        """
        Processes an invite event.

        :param room_id: The room ID of the invite
        :param info: The invite information
        """
        await self._init_db()
        await self._pop_from(room_id, "join", "knock", "leave")
        self.log.debug("Processing join room %r.", room_id)
        await self._db.execute(
            "INSERT OR IGNORE INTO 'rooms.invite' (room_id, state) VALUES (?, ?)",
            (room_id, self.dumps([dataclasses.asdict(x) for x in info.invite_state])),
        )

    @staticmethod
    def summary_to_json(summary: nio.RoomSummary) -> typing.Dict:
        d = {
            "m.heroes": summary.heroes,
            "m.invited_member_count": summary.invited_member_count,
            "m.joined_member_count": summary.joined_member_count,
        }
        for k, v in d.copy().items():
            if v is None:
                del d[k]
        return d

    async def process_join(self, room_id: str, info: nio.RoomInfo) -> None:
        """
        Processes a room join

        :param room_id: The room ID of the room
        :param info: The room information
        """
        await self._init_db()
        await self._pop_from(room_id, "invite", "knock", "leave")
        self.log.debug("Processing joined room %r.", room_id)
        await self._db.execute(
            """
            INSERT OR IGNORE INTO 'rooms.join' (room_id, account_data, state, summary, timeline) VALUES (?, ?, ?, ?, ?)
            """,
            (
                room_id,
                self.dumps([dataclasses.asdict(x) for x in info.account_data]),
                self.dumps([dataclasses.asdict(x) for x in info.state]),
                self.dumps(self.summary_to_json(info.summary)),
                json.dumps([dataclasses.asdict(x) for x in info.timeline.events], separators=(",", ":")),
            ),
        )
        self.log.debug("Processed join in %r.", room_id)

    async def process_leave(self, room_id: str, info: nio.RoomInfo) -> None:
        """
        Processes a room leave
        """
        await self._init_db()
        await self._pop_from(room_id, "invite", "knock", "join")
        self.log.debug("Processing leave room %r.", room_id)
        await self._db.execute(
            "INSERT OR IGNORE INTO 'rooms.leave' (room_id, account_data, state, timeline) VALUES (?, ?, ?, ?)",
            (
                room_id,
                self.dumps([dataclasses.asdict(x) for x in info.account_data]),
                self.dumps([dataclasses.asdict(x) for x in info.state]),
                self.dumps([dataclasses.asdict(x) for x in info.timeline.events]),
            ),
        )

    async def get_state_for(self, room_id: str, membership: Membership) -> typing.List[typing.Dict]:
        """
        Fetches the stored state for a specific room.
        """
        await self._init_db()
        state_table = f"rooms.{membership.value}"
        async with self._db.execute(f'SELECT state FROM "{state_table}" WHERE room_id=?', (room_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                return json.loads(result["state"])
            return []

    async def insert_state_event(
        self, room_id: str, membership: Membership, new_event: typing.Union[dict, nio.Event], *, force: bool = False
    ) -> None:
        """
        Inserts a new event into the state store for a specified room

        :param room_id: The room ID in which this state event belongs
        :param membership: The client's membership state
        :param new_event: The new event to insert
        :param force: If True, the function will always insert the new event, even if it is deemed uninteresting
        """
        if isinstance(new_event, nio.Event):
            new_event = new_event.source["source"]
        # Just do some basic validation first
        for key in ("type", "event_id", "sender"):
            if key not in new_event:
                raise ValueError("State event %r is missing required key %r" % (new_event, key))
        if force is not True and new_event["type"] not in self.important_events:
            self.log.debug("Ignoring unimportant state event %r.", new_event)
            return
        # If you hold this function incorrectly, you are vulnerable to an SQL injection attack.
        # The library does not hold it incorrectly.
        await self._init_db()
        state_table = f"rooms.{membership.value}"
        existing_state = await self.get_state_for(room_id, membership)

        unsigned_data = new_event.get("unsigned", {})
        replaces_state = unsigned_data.get("replaces_state", None)
        if replaces_state and self.resolve_state:
            for event in existing_state:
                if event.get("event_id", None) == replaces_state:
                    self.log.debug("State event %r replaced state event %r.", new_event["event_id"], replaces_state)
                    existing_state.remove(event)
                    break
            else:
                self.log.warning(
                    "Got a state event (%r) that is meant to replace another one (%r), however we do not have"
                    " the latter.",
                    new_event["event_id"],
                    replaces_state,
                )
        if self.log.isEnabledFor(logging.DEBUG):
            dumped_state = json.dumps(existing_state, separators=(",", ":"))
            if len(dumped_state) > 512:
                dumped_state = dumped_state[:512] + "..."
            self.log.debug("Appending event %r to state %r.", new_event, dumped_state)
        existing_state.append(new_event)
        self.log.debug("Room %r now has %d state events.", room_id, len(existing_state))
        await self._db.execute(
            f'UPDATE "{state_table}" SET state=? WHERE room_id=?', (self.dumps(existing_state), room_id)
        )

    async def insert_timeline_event(
        self, room_id: str, membership: Membership, new_event: typing.Union[dict, nio.Event], *, force: bool = False
    ) -> None:
        """
        Inserts a new event into the timeline store for a specified room

        :param room_id: The room ID in which this timeline event belongs
        :param membership: The client's membership state
        :param new_event: The new event to insert
        :param force: If True, the function will always insert the new event, even if it is deemed uninteresting
        """
        if isinstance(new_event, nio.Event):
            new_event = new_event.source["source"]
        # Just do some basic validation first
        for key in ("type", "event_id", "sender"):
            if key not in new_event:
                raise ValueError("Timeline event %r is missing required key %r" % (new_event, key))
        if force is not True and new_event["type"] not in self.important_events:
            self.log.debug("Ignoring unimportant timeline event %r.", new_event)
            return
        # If you hold this function incorrectly, you are vulnerable to an SQL injection attack.
        # The library does not hold it incorrectly.
        await self._init_db()
        table = f"rooms.{membership.value}"
        existing_timeline = await self.get_state_for(room_id, membership)
        if self.log.isEnabledFor(logging.DEBUG):
            dumped_timeline = json.dumps(existing_timeline, separators=(",", ":"))
            if len(dumped_timeline) > 512:
                dumped_timeline = dumped_timeline[:512] + "..."
            self.log.debug("Appending event %r to timeline %r.", new_event, dumped_timeline)
        existing_timeline.append(new_event)
        self.log.debug("Room %r now has %d timeline events.", room_id, len(existing_timeline))
        await self._db.execute(
            f'UPDATE "{table}" SET timeline=? WHERE room_id=?', (self.dumps(existing_timeline), room_id)
        )

    async def remove_event(
        self, room_id: str, membership: Membership, event_id: str, event_type: typing.Literal["timeline", "state"]
    ) -> None:
        """
        Forcibly removes an event from the store.
        This usually is not necessary, but included for convenience
        """
        if event_type not in ("timeline", "state"):
            raise ValueError("Can only remove events from timeline or state")
        await self._init_db()
        table = f"rooms.{membership.value}"
        existing_data = await self.get_state_for(room_id, membership)
        for event in existing_data:
            if event["event_id"] == event_id:
                self.log.debug("Removing event %r", event)
                existing_data.remove(event)
                break
        await self._db.execute(
            f'UPDATE "{table}" SET {event_type}=? WHERE room_id=?', (self.dumps(existing_data), room_id)
        )

    async def get_next_batch(self, user_id: str = None) -> str:
        """Returns the next batch token for the given user ID (or the client's user ID)"""
        await self._init_db()
        user_id = user_id or self._client.user_id
        async with self._db.execute("SELECT next_batch FROM meta WHERE user_id=?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                self.log.debug("Next batch record for %r: %r", result["user_id"], result["next_batch"])
                return result["next_batch"]
            self.log.debug("No next batch stored, returning empty token.")
            return ""

    async def set_next_batch(self, user_id: str, next_batch: str) -> None:
        """Sets the next batch token for the given user ID"""
        await self._init_db()
        self.log.debug("Setting next batch to %r for %r.", next_batch, user_id)
        await self._db.execute(
            """
            INSERT INTO meta (user_id, next_batch) VALUES (?, ?)
            ON CONFLICT(user_id) 
            DO 
                UPDATE SET next_batch=excluded.next_batch
                WHERE user_id=excluded.user_id
            """,
            (user_id, next_batch),
        )

    async def handle_sync(self, response: nio.SyncResponse) -> None:
        """
        Handles a sync response from the server
        """
        await self._init_db()
        self.log.debug("Handling sync: %r", response.uuid or uuid.uuid4())
        for room_id, room in response.rooms.invite.items():
            self.log.debug("Processing invited room %r: %r", room_id, room)
            await self.process_invite(room_id, room)
        for room_id, room in response.rooms.join.items():
            self.log.debug("Processing joined room %r: %r", room_id, room)
            await self.process_join(room_id, room)
        for room_id, room in response.rooms.leave.items():
            self.log.debug("Processing left room %r: %r", room_id, room)
            await self.process_leave(room_id, room)

        if self.log.isEnabledFor(logging.DEBUG):
            self.log.debug(
                "Processed sync response %r, next batch is now %r.",
                await self.get_next_batch(self._client.user_id),
                response.next_batch,
            )
        await self.set_next_batch(self._client.user_id, response.next_batch)

    async def generate_sync(self) -> nio.SyncResponse:
        """
        Generates a sync response, ready for replaying.
        """
        log = self.log.getChild("generate_sync")
        payload = {
            "next_batch": await self.get_next_batch(self._client.user_id),
            "rooms": {"invite": {}, "join": {}, "leave": {}},
        }
        async with self._db.execute('SELECT * FROM "rooms.join"') as cursor:
            async for row in cursor:
                summary = json.loads(row["summary"])
                payload["rooms"]["join"][row["room_id"]] = {
                    "timeline": {"events": json.loads(row["timeline"])},
                    "state": {"events": json.loads(row["state"])},
                    "account_data": {"events": json.loads(row["account_data"])},
                    "summary": summary,
                    "ephemeral": {},
                }
                log.debug("Added room %r to `rooms.join`", row["room_id"])

        async with self._db.execute('SELECT room_id, state FROM "rooms.invite"') as cursor:
            async for row in cursor:
                payload["rooms"]["invite"][row["room_id"]] = {"invite_state": {"events": json.loads(row["state"])}}
                log.debug("Added room %r to `rooms.invite`", row["room_id"])

        async with self._db.execute('SELECT * FROM "rooms.leave"') as cursor:
            async for row in cursor:
                payload["rooms"]["leave"][row["room_id"]] = {
                    "timeline": {"events": json.loads(row["timeline"])},
                    "state": {"events": json.loads(row["state"])},
                    "account_data": {"events": json.loads(row["account_data"])},
                    "summary": {},
                    "ephemeral": {},
                }
                log.debug("Added room %r to `rooms.leave`", row["room_id"])

        return nio.SyncResponse.from_dict(payload)

    async def commit(self) -> None:
        """forcefully writes unsaved changes to the database, without closing the connection"""
        await self._db.commit()

    def __bool__(self):
        return True
