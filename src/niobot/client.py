import asyncio
import collections
import functools
import getpass
import importlib
import inspect
import json
import logging
import os
import pathlib
import re
import sys
import time
import types
import typing
import warnings
from collections import deque
from typing import Optional, Type, Union as U
from urllib.parse import urlparse

import marko
import nio
from nio.crypto import ENCRYPTION_ENABLED

from . import ImageAttachment
from .attachment import BaseAttachment
from .commands import Command, Module
from .exceptions import (
    CheckFailure,
    CommandArgumentsError,
    CommandDisabledError,
    CommandError,
    GenericMatrixError,
    LoginException,
    MessageException,
    NioBotException,
)
from .utils import (
    MXID_REGEX,
    Mentions,
    SyncStore,
    Typing,
    _DudSyncStore,
    deprecated,
    force_await,
    run_blocking,
)
from .utils.help_command import DefaultHelpCommand

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

if typing.TYPE_CHECKING:
    from .context import Context

# Join API fix

from nio import (
    Api,
    AsyncClient,
    DirectRoomsResponse,
    JoinError,
    JoinResponse,
    RoomLeaveError,
    RoomLeaveResponse,
)

__all__ = ("NioBot",)

T = typing.TypeVar("T")


class NioBot(AsyncClient):
    """The main client for NioBot.

    !!! warning "Forcing an initial sync is slow"
        (for the `force_initial_sync` parameter)
        By default, nio-bot stores what the last sync token was, and will resume from that next time it starts.
        This allows you to start up near instantly, and makes development easier and faster.

        However, in some cases, especially if you are missing some metadata such as rooms or their members,
        you may need to perform an initial (sometimes referred to as "full") sync.
        An initial sync will fetch ALL the data from the server, rather than just what has changed since the last sync.

        This initial sync can take several minutes, especially the larger your bot gets, and should only be used
        if you are missing aforementioned data that you need.

    :param homeserver: The homeserver to connect to. e.g. https://matrix-client.matrix.org
    :param user_id: The user ID to log in as. e.g. @user:matrix.org
    :param device_id: The device ID to log in as. e.g. nio-bot
    :param store_path: The path to the store file. Defaults to ./store. Must be a directory.
    :param command_prefix: The prefix to use for commands. e.g. `!`. Can be a string, a list of strings,
     or a regex pattern.
    :param case_insensitive: Whether to ignore case when checking for commands. If True, this casefold()s
     incoming messages for parsing.
    :param global_message_type: The message type to default to. Defaults to m.notice
    :param ignore_old_events: Whether to simply discard events before the bot's login.
    :param auto_join_rooms: Whether to automatically join rooms the bot is invited to.
    :param auto_read_messages: Whether to automatically update read recipts
    :param owner_id: The user ID of the bot owner. If set, only this user can run owner-only commands, etc.
    :param max_message_cache: The maximum number of messages to cache. Defaults to 1000.
    :param ignore_self: Whether to ignore messages sent by the bot itself. Defaults to False. Useful for self-bots.
    :param import_keys: A key export file and password tuple. These keys will be imported at startup.
    :param startup_presence: The presence to set on startup. `False` disables presence altogether, and `None`
    is automatic based on the startup progress.
    :param default_parse_mentions: Whether to parse mentions in send_message by default to make them intentional.
    :param force_initial_sync: Forcefully perform a full initial sync at startup.
    :param use_fallback_replies: Whether to force the usage of deprecated fallback replies. Not recommended outside
    of compatibility reasons.
    """

    # Long typing definitions out here instead of in __init__ to just keep it cleaner.
    _events: typing.Dict[typing.Union[str, nio.Event], typing.List[typing.Callable[..., typing.Any]]]
    """Internal events register."""
    _commands: typing.Dict[str, Command]
    """Internal command register."""
    _modules: typing.Dict[typing.Type, Module]
    """Internal module register."""

    def __init__(
        self,
        homeserver: str,
        user_id: str,
        device_id: str = "nio-bot",
        store_path: typing.Optional[str] = None,
        *,
        command_prefix: typing.Union[str, re.Pattern, typing.Iterable[str]],
        case_insensitive: bool = True,
        owner_id: typing.Optional[str] = None,
        config: typing.Optional[nio.AsyncClientConfig] = None,
        ssl: bool = True,
        proxy: typing.Optional[str] = None,
        help_command: typing.Optional[typing.Union[Command, typing.Callable[["Context"], typing.Any]]] = None,
        global_message_type: typing.Literal["m.text", "m.notice"] = "m.notice",
        ignore_old_events: bool = True,
        auto_join_rooms: bool = True,
        auto_read_messages: bool = True,
        max_message_cache: int = 1000,
        ignore_self: bool = True,
        import_keys: typing.Tuple[os.PathLike, typing.Optional[str]] = None,
        startup_presence: typing.Literal["online", "unavailable", "offline", False, None] = None,
        sync_full_state: bool = True,
        default_parse_mentions: bool = True,
        force_initial_sync: bool = False,
        use_fallback_replies: bool = False,
        onsite_state_resolution: bool = False,
    ):
        if user_id == owner_id and ignore_self is True:
            warnings.warn(
                UserWarning(
                    "User ID and owner ID are the same, but ignore_self is True, meaning no owner systems can be used."
                    " This is probably not what you want.",
                ),
            )
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None
        self.log = logging.getLogger(__name__)
        if store_path:
            if not os.path.exists(store_path):
                self.log.warning("Store path %s does not exist, creating...", store_path)
                os.makedirs(store_path, mode=0o751, exist_ok=True)
            elif not os.path.isdir(store_path):
                raise FileNotFoundError("Store path %s is not a directory!" % store_path)

        if ENCRYPTION_ENABLED:
            if not config:
                config = nio.AsyncClientConfig(encryption_enabled=True, store_sync_tokens=force_initial_sync is False)
                self.log.info("Encryption support enabled automatically.")
                if force_initial_sync:
                    self.log.warning("An initial sync is being forced. Your next/first sync() call will be slow.")
        else:
            self.log.info("Encryption support is not available (are the e2ee extras installed?)")

        super().__init__(
            homeserver,
            user_id,
            device_id,
            store_path=store_path,
            config=config,
            ssl=ssl,
            proxy=proxy,
        )
        self.user_id = user_id
        self.device_id = device_id
        self.store_path = store_path
        self.case_insensitive = case_insensitive
        self.owner_id = owner_id
        self.ignore_self = ignore_self

        if not isinstance(command_prefix, (str, re.Pattern)):
            try:
                iter(command_prefix)
            except TypeError:
                raise TypeError("Command prefix must be a string,  or a regex pattern.") from None
            else:
                self.command_prefix: typing.Tuple[str, ...] = tuple(command_prefix)
        elif isinstance(command_prefix, re.Pattern):
            self.command_prefix: re.Pattern = command_prefix
        else:
            self.command_prefix: typing.Tuple[str] = (command_prefix,)

        if isinstance(self.command_prefix, re.Pattern):
            if self.command_prefix.match("/"):
                self.log.warning(
                    "The prefix '/' may interfere with client-side commands on some clients, such as Element.",
                )
            if self.command_prefix.match(">"):
                self.log.warning("The prefix '>' may interfere with fallback reply stripping in command parsing.")
        else:
            if "/" in self.command_prefix:
                self.log.warning(
                    "The prefix '/' may interfere with client-side commands on some clients, such as Element.",
                )
            if ">" in self.command_prefix:
                self.log.warning("The prefix '>' may interfere with fallback reply stripping in command parsing.")
            if re.search(r"\s", ";".join(command_prefix)):
                raise RuntimeError("Command prefix cannot contain whitespace.")

        self.start_time: typing.Optional[float] = None
        help_cmd = Command(
            "help",
            DefaultHelpCommand().respond,
            aliases=["h"],
            description="Shows a list of commands for this bot",
        )
        if help_command:
            cmd = help_command
            if isinstance(cmd, Command):
                help_cmd = cmd
            elif asyncio.iscoroutinefunction(cmd) or inspect.isfunction(cmd):
                self.log.warning(
                    "Manually changing default help command callback to %r. Please consider passing your own"
                    " Command instance instead.",
                    cmd,
                )
                help_cmd.callback = cmd
            else:
                raise TypeError("help_command must be a Command instance or a coroutine/function.")
        self._commands = {}
        self._modules = {}
        self._events: typing.Dict[str, typing.List[typing.Union[types.FunctionType, typing.Callable]]] = {}
        self._raw_events = {}
        self._raw_events: typing.Dict[
            typing.Type[nio.Event], typing.List[typing.Union[types.FunctionType, typing.Callable]]
        ]
        self._event_tasks = []

        self.global_message_type = global_message_type
        self.ignore_old_events = ignore_old_events
        self.auto_join_rooms = auto_join_rooms
        self.auto_read_messages = auto_read_messages
        self.use_fallback_replies = use_fallback_replies

        self.add_event_callback(self.process_message, nio.RoomMessage)  # type: ignore
        self.direct_rooms: dict[str, nio.MatrixRoom] = {}

        self.message_cache: typing.Deque[typing.Tuple[nio.MatrixRoom, nio.RoomMessage]] = deque(
            maxlen=max_message_cache,
        )
        self.is_ready = asyncio.Event()
        self._waiting_events = {}

        if self.auto_join_rooms:
            self.log.info("Auto-joining rooms enabled.")
            self.add_event_callback(self._auto_join_room_backlog_callback, nio.InviteMemberEvent)  # type: ignore

        if self.auto_read_messages:
            self.log.info("Auto-updating read receipts enabled.")
            self.add_event_callback(self.update_read_receipts, nio.RoomMessage)

        if import_keys:
            keys_path, keys_password = import_keys
            if not keys_password:
                if sys.stdin.isatty():
                    keys_password = getpass.getpass(f"Password for key import ({keys_path}): ")
                else:
                    raise ValueError(
                        "No password was provided for automatic key import and cannot interactively get password.",
                    )

            self.__key_import = pathlib.Path(keys_path), keys_password
        else:
            self.__key_import = None

        self.server_info: typing.Optional[dict] = None
        self.add_command(help_cmd)

        self._startup_presence = startup_presence
        self._sync_full_state = sync_full_state
        self.default_parse_mentions = default_parse_mentions

        self._event_id_cache = collections.deque(maxlen=1000)
        self._message_process_lock = asyncio.Lock()

        self.sync_store: typing.Union[SyncStore, _DudSyncStore] = _DudSyncStore()
        if self.store_path:
            self.sync_store = SyncStore(self, self.store_path + "/sync.db", resolve_state=onsite_state_resolution)

    @property
    def supported_server_versions(self) -> typing.List[typing.Tuple[int, int, int]]:
        """Returns the supported server versions as a list of `major`, `minor`, `patch` tuples.

        The only time `patch` is >0 is when the server is using a deprecated `r` release.
        All stable releases (`v1`) will have `patch` as 0.

        This property returns `[(1, 1, 0)]` if no server info is available.
        """
        parsed = []
        if self.server_info:
            for version in self.server_info.get("versions", []):
                if version.startswith("r"):
                    major, minor, patch = map(int, version[1:].split("."))
                else:
                    major, minor = map(int, version[1:].split("."))
                    patch = 0
                parsed.append((major, minor, patch))
        return parsed or [(1, 1, 0)]  # default to 1.1.0 if no server info is available

    def server_supports(self, version: typing.Union[typing.Tuple[int, int], typing.Tuple[int, int, int]]) -> bool:
        """Checks that the server supports at least this matrix version."""
        return any(v >= version for v in self.supported_server_versions)
        # e.g. (1, 1, 0) >= (1, 12, 0) = False | (1, 12, 0) >= (1, 11, 0) = True

    async def mxc_to_http(
        self,
        mxc: str,
        homeserver: Optional[str] = None,
    ) -> Optional[str]:
        """Converts an `mxc://` URI to a downloadable HTTP URL.

        This function is identical the [nio.AsyncClient.mxc_to_http()][nio.AsyncClient.mxc_to_http] function,
        however supports matrix 1.10 and below's unauthenticated media automatically.

        :param mxc: The mxc URI
        :param homeserver: The homeserver to download this through (defaults to the bot's homeserver)
        :return: an MXC URL, if applicable
        """
        http: Optional[str] = await super().mxc_to_http(mxc, homeserver)
        if http is not None and not self.server_supports((1, 11, 0)):  # 1.10 and below
            http = http.replace("/_matrix/client/v1/media/download/", "/_matrix/media/r0/download/")
        return http

    async def sync(self, *args, **kwargs) -> U[nio.SyncResponse, nio.SyncError]:
        sync = await super().sync(*args, **kwargs)
        if isinstance(sync, nio.SyncResponse):
            self._populate_dm_rooms(sync)
            if self.sync_store:
                await self.sync_store.handle_sync(sync)
        return sync

    def _populate_dm_rooms(self, sync: nio.SyncResponse):
        # This function is a historical workaround. It is kept as it is still useful in some cases.
        for room_id, room_info in sync.rooms.join.items():
            for event in room_info.state:
                if isinstance(event, nio.RoomMemberEvent):
                    prev = event.prev_content or {}
                    if event.content.get("is_direct", prev.get("is_direct", False)):
                        self.log.debug("Found DM room in sync: %s", room_id)
                        self.direct_rooms[event.state_key] = self.rooms[room_id]

    async def _auto_join_room_callback(self, room: nio.MatrixRoom, event: nio.InviteMemberEvent):
        """Callback for auto-joining rooms"""
        if self.auto_join_rooms:
            self.log.info("Joining room %s", room.room_id)
            result = await self.join(room.room_id, reason=f"Auto-joining from invite sent by {event.sender}")
            if isinstance(result, nio.JoinError):
                self.log.error("Failed to join room %s: %s", room.room_id, result.message)
            else:
                self.log.info("Joined room %s", room.room_id)

    async def _auto_join_room_backlog_callback(self, room: nio.MatrixRoom, event: nio.InviteMemberEvent):
        """Callback for auto-joining rooms that are backlogged on startup"""
        if event.state_key == self.user_id:
            await self._auto_join_room_callback(room, event)

    @staticmethod
    def latency(event: nio.Event, *, received_at: typing.Optional[float] = None) -> float:
        """Returns the latency for a given event in milliseconds

        :param event: The event to measure latency with
        :param received_at: The optional time the event was received at. If not given, uses the current time.
        :return: The latency in milliseconds
        """
        now = received_at or time.time()
        return (now - event.server_timestamp / 1000) * 1000

    def dispatch(self, event_name: typing.Union[str, nio.Event], *args, **kwargs):
        """Dispatches an event to listeners"""
        if event_name in self._events:
            for handler in self._events[event_name]:
                self.log.debug("Dispatching %s to %r" % (event_name, handler))
                try:
                    task = asyncio.create_task(
                        handler(*args, **kwargs),
                        name="DISPATCH_%s_%s" % (handler.__qualname__, os.urandom(3).hex()),
                    )
                    self._event_tasks.append(task)
                    task.add_done_callback(
                        lambda *_, **__: self._event_tasks.remove(task) if task in self._event_tasks else None,
                    )
                except Exception as e:
                    self.log.exception("Error dispatching %s to %r", event_name, handler, exc_info=e)
        else:
            self.log.debug("%r is not in registered events: %s", event_name, self._events)

    def is_old(self, event: nio.Event) -> bool:
        """Checks if an event was sent before the bot started. Always returns False when ignore_old_events is False"""
        if not self.start_time:
            self.log.warning("have not started yet, using relative age comparison")
            start_time = time.time() - 30  # relative
        else:
            start_time = self.start_time
        if self.ignore_old_events is False:
            return False
        return start_time - event.server_timestamp / 1000 > 0

    async def update_read_receipts(self, room: U[str, nio.MatrixRoom], event: nio.Event):
        """Moves the read indicator to the given event in the room.

        !!! info "This is automatically done for you."
            Whenever a message is received, this is automatically called for you.
            As such, your read receipt will always be the most recent message. You rarely need to call this function.

        :param room: The room to update the read receipt in.
        :param event: The event to move the read receipt to.
        :return: Nothing
        """
        room = self._get_id(room)
        if self.is_old(event):
            self.log.debug("Ignoring event %s, sent before bot started.", event.event_id)
            return
        event_id = event.event_id
        result = await self.room_read_markers(room, event_id, event_id)
        if not isinstance(result, nio.RoomReadMarkersResponse):
            msg = result.message if isinstance(result, nio.ErrorResponse) else "?"
            self.log.warning("Failed to update read receipts for %s: %s", room, msg)
        else:
            self.log.debug("Updated read receipts for %s to %s.", room, event_id)

    async def process_message(self, room: nio.MatrixRoom, event: nio.RoomMessage) -> None:
        """Processes a message and runs the command it is trying to invoke if any."""
        lock = self._message_process_lock
        if lock is None:
            lock = asyncio.Lock()
        async with lock:
            if event.event_id in self._event_id_cache:
                self.log.warning("Not processing duplicate message event %r.", event.event_id)
                return
            if self.start_time is None:
                raise RuntimeError("Bot has not started yet!")
            self._event_id_cache.append(event.event_id)
            self.message_cache.append((room, event))
            self.dispatch("message", room, event)
            if not isinstance(event, nio.RoomMessageText):
                self.log.debug("Ignoring non-text message %r", event.event_id)
                return
            if event.sender == self.user and self.ignore_self is True:
                self.log.debug("Ignoring message sent by self.")
                return
            if self.is_old(event):
                age = self.start_time - event.server_timestamp / 1000
                self.log.debug(f"Ignoring message sent {age:.0f} seconds before startup.")
                return

            if self.case_insensitive:
                content = event.body.casefold()
            else:
                content = event.body

            def get_prefix(c: str) -> typing.Union[str, None]:
                if isinstance(self.command_prefix, re.Pattern):
                    _m = re.match(self.command_prefix, c)
                    if _m:
                        return _m.group(0)
                else:
                    for pfx in self.command_prefix:
                        if c.startswith(pfx):
                            return pfx

            if content.startswith(">"):
                try:
                    rep, content = content.split("\n\n", 1)
                except ValueError:
                    self.log.warning("Error while splitting message %r.", content)
                else:
                    self.log.debug("Parsed message, split into reply and content: %r, %r", rep[:50], content[:50])
            matched_prefix = get_prefix(content)
            if matched_prefix:
                try:
                    command_name = original_command = content[len(matched_prefix) :].splitlines()[0].split(" ")[0]
                except IndexError:
                    self.log.info(
                        "Failed to parse message %r - message terminated early (was the content *just* the prefix?)",
                        event.body,
                    )
                    return
                command: typing.Optional[Command] = self.get_command(command_name)
                if command:
                    if command.disabled is True:
                        error = CommandDisabledError(command)
                        self.dispatch("command_error", command, error)
                        return

                    context = command.construct_context(
                        self,
                        room=room,
                        src_event=event,
                        invoking_prefix=matched_prefix,
                        meta=matched_prefix + original_command,
                    )

                    try:
                        if not await context.command.can_run(context):
                            raise CheckFailure(None, "Unknown check failure")
                    except CheckFailure as err:
                        self.dispatch("command_error", context, err)
                        return

                    def _task_callback(t: asyncio.Task):
                        try:
                            exc = t.exception()
                        except asyncio.CancelledError:
                            self.dispatch("command_cancelled", context, t)
                        else:
                            if exc:
                                if "command_error" not in self._events:
                                    self.log.exception(
                                        "There was an error while running %r: %r",
                                        command,
                                        exc,
                                        exc_info=exc,
                                    )
                                self.dispatch("command_error", context, CommandError(exception=exc))
                            else:
                                self.dispatch("command_complete", context, t)
                        if hasattr(context, "_perf_timer"):
                            self.log.debug(
                                "Command %r finished in %.2f seconds",
                                command.name,
                                time.perf_counter() - context._perf_timer,
                            )

                    self.log.debug(f"Running command {command.name} with context {context!r}")
                    try:
                        task = asyncio.create_task(await command.invoke(context))
                        context._task = task
                        context._perf_timer = time.perf_counter()
                    except CommandArgumentsError as e:
                        self.dispatch("command_error", context, e)
                    except Exception as e:
                        self.log.exception("Failed to invoke command %s", command.name, exc_info=e)
                        self.dispatch("command_error", context, CommandError(exception=e))
                    else:
                        task.add_done_callback(_task_callback)
                else:
                    self.log.debug(f"Command {original_command!r} not found.")

    def is_owner(self, user_id: str) -> bool:
        """Checks whether a user is the owner of the bot.

        :param user_id: The user ID to check.
        :return: Whether the user is the owner.
        """
        if not self.owner_id:
            self.log.warning("Attempted to check for owner, but no owner ID was set!")
            return False  # no owner ID set.
        return self.owner_id == user_id

    def mount_module(self, import_path: str) -> typing.Optional[list[Command]]:
        """Mounts a module including all of its commands.

        Must be a subclass of niobot.commands.Module, or else this function will not work.

        ??? danger "There may not be an event loop running when this function is called."
            If you are calling this function before you call `bot.run()`, it is entirely possible that you don't have
            a running [asyncio][] event loop. If you use the event loop in `Module.__init__`, you will get an error,
            and the module will fail the mount.

            You can get around this by deferring mounting your modules until the `ready` event is fired,
            at which point not only will the first full sync have completed (meaning the bot has all of its caches
            populated), but the event loop will be running.

        :param import_path: The import path (such as modules.file), which would be ./modules/file.py in a file tree.
        :returns: Optional[list[Command]] - A list of commands mounted. None if the module's setup() was called.
        :raise ImportError: The module path is incorrect of there was another error while importing
        :raise TypeError: The module was not a subclass of Module.
        :raise ValueError: There was an error registering a command (e.g. name conflict)
        """
        added = []
        module = importlib.import_module(import_path)
        if hasattr(module, "setup") and callable(module.setup):
            # call setup
            self.log.debug("Calling module-defined setup() function rather than doing it manually.")
            _c = self.commands.copy()
            _e = self._events.copy()
            module.setup(self)
            if _c == self.commands and _e == self._events:
                self.log.warning(
                    "Module %r did not add any commands or events with the custom setup function?",
                    module,
                )
            return None

        self.log.debug("%r does not have its own setup() - auto-discovering commands and events", module)
        for _, item in inspect.getmembers(module):
            if inspect.isclass(item):
                if getattr(item, "__is_nio_module__", False):
                    if item in self._modules:
                        raise ValueError("%r is already loaded." % item.__class__.__name__)
                    instance = item(self)
                    if not isinstance(instance, Module):
                        raise TypeError("%r is not a subclass of Module." % instance.__class__.__name__)
                    instance.__setup__()
                    self._modules[item] = instance
                    added += list(instance.list_commands())
                    self.log.debug(
                        "Loaded %d commands from %r",
                        len(set(instance.list_commands())),
                        instance.__class__.__qualname__,
                    )
                else:
                    self.log.debug("%r does not appear to be a niobot module", item)
        return added

    def unmount_module(self, module: Module) -> None:
        """Does the opposite of mounting the module.
        This will remove any commands that have been added to the bot from the given module.

        :param module: The module to unmount
        """
        self.log.debug("Unmounting module %r", module)
        module.__teardown__()

    @property
    def commands(self) -> dict[str, Command]:
        """Returns the internal command register.

        !!! warning
            Modifying any values here will update the internal register too.

        !!! note
            Aliases of commands are treated as their own command instance. You will see the same command show up as a
            value multiple times if it has aliases.

            You can check if two commands are identical by comparing them (`command1instance == command2instance`)
        """
        return self._commands

    @property
    def modules(self) -> dict[typing.Type, Module]:
        """Returns the internal module register.

        !!! warning
            Modifying any values here will update the internal register too.
        """
        return self._modules

    def get_command(self, name: str) -> typing.Optional[Command]:
        """Attempts to retrieve an internal command

        :param name: The name of the command to retrieve
        :return: The command, if found. None otherwise.
        """
        return self._commands.get(name)

    def add_command(self, command: Command) -> None:
        """Adds a command to the internal register

        if a name or alias is already registered, this throws a ValueError.
        Otherwise, it returns None.
        """
        if self.get_command(command.name):
            raise ValueError(f"Command or alias {command.name} is already registered.")
        if any(self.get_command(alias) for alias in command.aliases):
            raise ValueError(f"Command or alias for {command.name} is already registered.")

        self._commands[command.name] = command
        self.log.debug("Registered command %r into %s", command, command.name)
        for alias in command.aliases:
            self._commands[alias] = command
            self.log.debug("Registered command %r into %s", command, alias)

    def remove_command(self, command: Command) -> None:
        """Removes a command from the internal register.

        If the command is not registered, this is a no-op.
        """
        if not self.get_command(command.name):
            return

        self.log.debug("Removed command %r from the register.", self._commands.pop(command.name, None))
        for alias in command.aliases:
            self.log.debug("Removed command %r from the register.", self._commands.pop(alias, None))

    def command(self, name: typing.Optional[str] = None, **kwargs):
        """Registers a command with the bot."""
        cls = kwargs.pop("cls", Command)

        def decorator(func):
            nonlocal name
            name = name or func.__name__
            command = cls(name, func, **kwargs)
            self.add_command(command)
            return func

        return decorator

    def add_event_listener(self, event_type: typing.Union[str, nio.Event, Type[nio.Event]], func):
        self._events.setdefault(event_type, [])
        if not isinstance(event_type, str):

            @functools.wraps(func)
            async def event_safety_wrapper(*args):
                # This is necessary to stop callbacks crashing the process
                self.log.debug("Raw event received: %r", args)
                try:
                    return await func(*args)
                except Exception as e:
                    self.log.exception("Error in raw event listener %r", func, exc_info=e)

            func = event_safety_wrapper
            self._raw_events.setdefault(event_type, [])
            self._raw_events[event_type].append(func)
            self.add_event_callback(func, event_type)
            self.log.debug("Added raw event listener %r for %r", func, event_type)
            return func
        else:
            self._events[event_type].append(func)
            self.log.debug("Added event listener %r for %r", func, event_type)
            return func

    def on_event(self, event_type: typing.Optional[typing.Union[str, Type[nio.Event]]] = None):
        """Wrapper that allows you to register an event handler.

        Event handlers **must** be async.

        if event_type is None, the function name is used as the event type.

        Please note that if you pass a [Event][nio.events.room_events.Event], you are responsible for capturing errors.
        """

        def wrapper(func):
            nonlocal event_type
            event_type = event_type or func.__name__
            if isinstance(event_type, str):
                if event_type.startswith("on_"):
                    self.log.warning("No events start with 'on_' - stripping prefix from %r", event_type)
                    event_type = event_type[3:]
            self.add_event_listener(event_type, func)
            return func

        return wrapper

    def remove_event_listener(self, function):
        """Removes an event listener from the bot. Must be the exact function passed to add_event_listener."""
        removed = 0
        for event_type, functions in self._events.items():
            if function in functions:
                self._events[event_type].remove(function)
                self.log.debug("Removed %r from event %r", function, event_type)
                removed += 1
        for event_type, functions in self._raw_events.items():
            if function in functions:
                self._raw_events[event_type].remove(function)
                self.log.debug("Removed %r from raw event %r", function, event_type)
                removed += 1

        if removed == 0:
            self.log.warning("Function %r was not found in any event listeners.", function)

    async def set_room_nickname(
        self,
        room: U[str, nio.MatrixRoom],
        new_nickname: str = None,
        user: typing.Optional[U[str, nio.MatrixUser]] = None,
    ) -> nio.RoomPutStateResponse:
        """Changes the user's nickname in the given room.

        :param room: The room to change the nickname in.
        :param new_nickname: The new nickname. If None, defaults to the user's display name.
        :param user: The user to update. Defaults to the bot's user.
        :return: The response from the server.
        :raise: GenericMatrixError - The request failed.
        """
        room_id = self._get_id(room)
        user = user or self.user_id
        user_id = self._get_id(user)
        profile = await self.get_profile(user_id)
        if isinstance(profile, nio.ProfileGetError):
            raise GenericMatrixError("Failed to get profile", response=profile)

        result = await self.room_put_state(
            room_id,
            "m.room.member",
            {"membership": "join", "displayname": new_nickname, "avatar_url": profile.avatar_url},
            user_id,
        )
        if isinstance(result, nio.RoomPutStateError):
            raise GenericMatrixError("Failed to set nickname", response=result)
        return result

    async def room_send(
        self,
        room_id: str,
        message_type: str,
        content: dict,
        tx_id: typing.Optional[str] = None,
        ignore_unverified_devices: bool = True,
    ) -> U[nio.RoomSendResponse, nio.RoomSendError]:
        return await super().room_send(
            room_id,
            message_type,
            content,
            tx_id,
            ignore_unverified_devices,
        )

    def get_cached_message(self, event_id: str) -> typing.Optional[typing.Tuple[nio.MatrixRoom, nio.RoomMessage]]:
        """Fetches a message from the cache.

        This returns both the room the message was sent in, and the event itself.

        If the message is not in the cache, this returns None.
        """
        for room, event in self.message_cache:
            if event_id == event.event_id:
                return room, event

    async def fetch_message(self, room_id: str, event_id: str):
        """Fetches a message from the server."""
        cached = self.get_cached_message(event_id)
        if cached:
            return cached

        result: typing.Union[nio.RoomGetEventError, nio.RoomGetEventResponse]
        result = await self.room_get_event(room_id, event_id)
        if isinstance(result, nio.RoomGetEventError):
            raise NioBotException(f"Failed to fetch message {event_id} from {room_id}: {result}", original=result)
        return result

    async def wait_for_message(
        self,
        room_id: typing.Optional[str] = None,
        sender: typing.Optional[str] = None,
        check: typing.Optional[typing.Callable[[nio.MatrixRoom, nio.RoomMessageText], typing.Any]] = None,
        *,
        timeout: typing.Optional[float] = None,
        msg_type: typing.Type[nio.RoomMessage] = nio.RoomMessageText,
    ) -> typing.Optional[typing.Tuple[nio.MatrixRoom, nio.RoomMessage]]:
        """Alias for [niobot.NioBot.wait_for_event][] with a message type filter."""

        def _check(event: nio.MatrixRoom, msg: nio.RoomMessageText):
            return isinstance(msg, msg_type) and (not check or check(event, msg))

        return await self.wait_for_event("message", room_id, sender, _check, timeout=timeout)

    async def wait_for_event(
        self,
        event_type: typing.Union[str, typing.Type[nio.Event]],
        room_id: typing.Optional[str] = None,
        sender: typing.Optional[str] = None,
        check: typing.Optional[typing.Callable[[nio.MatrixRoom, nio.RoomMessageText], typing.Any]] = None,
        *,
        timeout: typing.Optional[float] = None,
    ) -> typing.Optional[typing.Tuple[nio.MatrixRoom, nio.RoomMessage]]:
        """Waits for an event, optionally with a filter.

        If this function times out, asyncio.TimeoutError is raised.

        :param event_type: The type of event to wait for.
        :param room_id: The room ID to wait for a message in. If None, waits for any room.
        :param sender: The user ID to wait for a message from. If None, waits for any sender.
        :param check: A function to check the message with. If the function returns False, the message is ignored.
        :param timeout: The maximum time to wait for a message. If None, waits indefinitely.
        :return: The room and message that was received.
        """
        event = asyncio.Event()
        value = None

        async def event_handler(_room, _event):
            if room_id and _room.room_id != room_id:
                self.log.debug("Ignoring bubbling event from %r (vs %r)", _room.room_id, room_id)
                return False
            if sender and _event.sender != sender:
                self.log.debug("Ignoring bubbling event from %r (vs %r)", _event.sender, sender)
                return False
            if check:
                try:
                    result = await force_await(check, _room, _event)
                except Exception as e:
                    self.log.error("Error in check function: %r", e, exc_info=e)
                    return False
                if not result:
                    self.log.debug("Ignoring bubbling event, check was false")
                    return False
            event.set()
            nonlocal value
            value = _room, _event

        real_callback = self.add_event_listener(event_type, event_handler)
        try:
            self.log.debug("Waiting for event %r", event_type, stack_info=True)
            # Stack is logged since it's easier to trace back to *why* an event is being traced
            await asyncio.wait_for(event.wait(), timeout=timeout)
            self.log.debug("Received event %r", event_type)
        except asyncio.TimeoutError:
            self.log.debug("Timed out waiting for event %r", event_type)
            raise
        finally:
            self.remove_event_listener(real_callback)
        return value

    @staticmethod
    async def markdown_to_html(text: str) -> str:
        """Converts markdown to HTML.

        :param text: The markdown to render as HTML
        :return: the rendered HTML
        """
        parsed = await run_blocking(marko.parse, text)
        if parsed.children:
            rendered = await run_blocking(marko.render, parsed)
        else:
            rendered = text
        return rendered

    @property
    @deprecated("niobot.NioBot.markdown_to_html")
    def _markdown_to_html(self) -> typing.Callable[[str], typing.Awaitable[str]]:
        return self.markdown_to_html

    @staticmethod
    def _get_id(obj: typing.Union[nio.Event, nio.MatrixRoom, nio.MatrixUser, str, typing.Any]) -> str:
        """Gets the id of most objects as a string.

        :param obj: The object whose ID to get, or the ID itself.
        :type obj: typing.Union[nio.Event, nio.MatrixRoom, nio.MatrixUser, str, Any]
        :returns: the ID of the object
        :raises: ValueError - the Object doesn't have an ID
        """
        if hasattr(obj, "event_id"):
            return obj.event_id
        if hasattr(obj, "room_id"):
            return obj.room_id
        if hasattr(obj, "user_id"):
            return obj.user_id
        if isinstance(obj, str):
            return obj
        raise ValueError("Unable to determine ID of object: %r" % obj)

    @deprecated(None)
    def generate_mx_reply(self, room: nio.MatrixRoom, event: nio.RoomMessageText) -> str:
        """Fallback replies have been removed by MSC2781. Do not use this anymore."""
        if not self.use_fallback_replies:
            return ""
        return (
            "<mx-reply>"
            "<blockquote>"
            '<a href="{reply_url}">{reply}</a> '
            '<a href="{user_url}">{user}</a><br/>'
            "</blockquote>"
            "</mx-reply>".format(
                reply_url="https://matrix.to/#/{}:{}/{}".format(
                    room.room_id,
                    room.machine_name.split(":")[1],
                    event.event_id,
                ),
                reply=event.body,
                user_url=f"https://matrix.to/#/{event.sender}",
                user=event.sender,
            )
        )

    @typing.overload
    async def get_dm_rooms(self) -> typing.Dict[str, typing.List[str]]:
        """Gets all DM rooms stored in account data.

        :return: A dictionary containing user IDs as keys, and lists of room IDs as values.
        """

    @typing.overload
    async def get_dm_rooms(self, user: U[nio.MatrixUser, str]) -> typing.List[str]:
        """Gets DM rooms for a specific user.

        :param user: The user to fetch DM rooms for.
        :return: A list of room IDs
        """

    async def get_dm_rooms(
        self,
        user: typing.Optional[U[nio.MatrixUser, str]] = None,
    ) -> typing.Union[typing.Dict[str, typing.List[str]], typing.List[str]]:
        """Gets DM rooms, optionally for a specific user.

        If no user is given, this returns a dictionary of user IDs to lists of rooms.

        :param user: The user ID or object to get DM rooms for.
        :return: A dictionary of user IDs to lists of rooms, or a list of rooms.
        """
        result = await self.list_direct_rooms()
        if isinstance(result, nio.DirectRoomsErrorResponse):
            if result.status_code == "M_NOT_FOUND":
                # No DM rooms for this account are known
                return {} if user is None else []
            raise GenericMatrixError("Failed to get DM rooms", response=result)
        if user:
            user_id = self._get_id(user)
            return result.rooms.get(user_id, [])
        return result.rooms

    async def create_dm_room(
        self,
        user: U[nio.MatrixUser, str],
    ) -> nio.RoomCreateResponse:
        """Creates a DM room with a given user.

        :param user: The user to create a DM room with.
        :return: The response from the server.
        """
        user_id = self._get_id(user)
        result = await self.room_create(
            is_direct=True,
            invite=[user_id],
            visibility=nio.api.RoomVisibility.private,
            preset=nio.api.RoomPreset.trusted_private_chat,
        )
        if isinstance(result, nio.RoomCreateError):
            raise GenericMatrixError("Failed to create DM room", response=result)

        dm_rooms = {user_id: [result.room_id]}

        logging.debug(f"create_dm_user: user_id {user_id} self.user_id {self.user_id}")
        # Trying to send m.direct type eventfrom nio.responses import DirectRoomsErrorResponse, DirectRoomsResponse
        logging.debug(f"create_dm_user: setting m.direct type with rooms {nio.Api.to_json(dm_rooms)}")
        await self._send(
            nio.DirectRoomsResponse,
            "PUT",
            nio.Api._build_path(
                ["user", self.user_id, "account_data", "m.direct"],
                {"access_token": self.access_token},
            ),
            nio.Api.to_json(dm_rooms),
        )

        return result

    @staticmethod
    def parse_user_mentions(content: str) -> typing.List[str]:
        # This is super crude
        results = MXID_REGEX.findall(content)

        def filter_func(mxid: str):
            if len(mxid) > 255:
                return False  # too long
            _, server_name = mxid.split(":", 1)
            parsed_sn = urlparse("https://" + server_name)
            if not parsed_sn.hostname:
                return False
            return True

        return list(filter(filter_func, results))

    async def send_message(
        self,
        room: U[nio.MatrixRoom, nio.MatrixUser, str],
        content: typing.Optional[str] = None,
        file: typing.Optional[BaseAttachment] = None,
        reply_to: typing.Optional[U[nio.RoomMessage, str]] = None,
        message_type: typing.Optional[str] = None,
        *,
        content_type: typing.Literal["plain", "markdown", "html", "html.raw"] = "markdown",
        override: typing.Optional[dict] = None,
        mentions: typing.Union[Mentions, typing.Literal[False], None] = None,
    ) -> nio.RoomSendResponse:
        """Sends a message. Doesn't get any more simple than this.

        ??? tip "DMs"
            As of v1.1.0, you can now send messages to users (either a [nio.MatrixUser][nio.rooms.MatrixUser]
            or a user ID string),
            and a direct message room will automatically be created for you if one does not exist, using an existing
            one if it does.

        !!! tip "Content Type"
            **Separate to `message_type`**, `content_type` controls what sort of parsing and formatting will be applied
            to the provided content. This is useful for sending messages that are not markdown, or for sending HTML.
            Before, all content was assumed to be markdown, and was parsed as such. However, this may cause
            undesirable effects if you are sending messages that are not markdown.

            * **`plain`** - No parsing or formatting is applied, and the content is sent as-is.
            * **`markdown`** - The content is parsed as markdown and rendered as HTML, with a fallback plain text
            body. This is the default.
            * **`html`** - The content is sent as HTML, with no fallback to plain text. If BeautifulSoup is installed,
            the provided content will be sanitised and pretty-printed before sending.
            ** **`html.raw`** - The content is sent as HTML, with no fallback to plain text,
            nor sanitising or formatting.

        :param room: The room or to send this message to
        :param content: The content to send. Cannot be used with file.
        :param file: A file to send, if any. Cannot be used with content.
        :param reply_to: A message to reply to.
        :param message_type: The message type to send. If none, defaults to NioBot.global_message_type,
        which itself is `m.notice` by default.
        :param override: A dictionary containing additional properties to pass to the body.
        Overrides existing properties.
        :param content_type: The type of content to send. Defaults to "markdown".
        :param mentions: Intentional mentions to send with the message. If not provided, or `False`, then auto-detected.
        :return: The response from the server.
        :raises MessageException: If the message fails to send, or if the file fails to upload.
        :raises ValueError: You specified neither file nor content.
        :raises RuntimeError: An internal error occured. A room was created, but is not in the bot room list.
        """
        if file and BaseAttachment is None:
            raise ValueError("You are missing required libraries to use attachments.")
        if not any((content, file)):
            raise ValueError("You must specify either content or file.")

        if isinstance(room, nio.MatrixUser) or (isinstance(room, str) and room.startswith("@")):
            _user = room
            room = None
            rooms = await self.get_dm_rooms(_user)
            logging.debug(f"send_message get_dm_rooms returns rooms {json.dumps(rooms)}")

            if rooms:
                for r_id in rooms:
                    if r_id in self.rooms:
                        room = r_id
                        break
                    logging.warning(f"room {r_id} not found in bot.rooms")
            if not room:
                logging.info("creating dm room for user {_user}")
                response = await self.create_dm_room(_user)

                room = self.rooms.get(response.room_id)
                if not room:
                    raise RuntimeError(
                        "DM room %r was created, but could not be found in the room list!" % response.room_id,
                    )

        self.log.debug("Send message resolved room to %r", room)

        body: dict[str, typing.Any] = {
            "msgtype": message_type or self.global_message_type,
        }

        if file is not None:
            if hasattr(file, "thumbnail") and isinstance(file.thumbnail, ImageAttachment):
                self.log.info("Uploading thumbnail %r for %r.", file.thumbnail, file)
                await file.thumbnail.upload(self)
                self.log.info("Finished uploading thumbnail %r.", file.thumbnail)
            self.log.info("Uploading %r.", file)
            await file.upload(self)
            self.log.info("Finished uploading %r.", file)
            body = file.as_body(content)
        else:
            body["body"] = content
            if content_type == "markdown":
                parsed = await run_blocking(marko.parse, content)
                if parsed.children:
                    rendered = await run_blocking(marko.render, parsed)
                    body["formatted_body"] = rendered
                    body["format"] = "org.matrix.custom.html"
            elif content_type == "html":
                if BeautifulSoup:
                    soup = BeautifulSoup(content)
                    content_new = soup.prettify("utf-8", "minimal")
                else:
                    self.log.debug("Content type was HTML, however BeautifulSoup is not installed. Treating as raw.")
                    content_new = content
                body["formatted_body"] = content_new
                body["format"] = "org.matrix.custom.html"
            elif content_type == "html.raw":
                body["formatted_body"] = content
                body["format"] = "org.matrix.custom.html"

        if reply_to:
            body["m.relates_to"] = {"m.in_reply_to": {"event_id": self._get_id(reply_to)}}
        if isinstance(mentions, Mentions):
            body.update(mentions.as_body())
        elif mentions is None and content and self.default_parse_mentions:
            mxids = self.parse_user_mentions(content)
            mentions = Mentions("@room" in content, *mxids)
            body.update(mentions.as_body())

        if override:
            body.update(override)
        try:
            async with Typing(self, self._get_id(room)):
                response = await self.room_send(
                    self._get_id(room),
                    "m.room.message",
                    body,
                )
        except RuntimeError:  # already typing
            response = await self.room_send(
                self._get_id(room),
                "m.room.message",
                body,
            )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to send message.", response)
        return response

    async def edit_message(
        self,
        room: U[nio.MatrixRoom, str],
        message: U[nio.Event, str],
        content: str,
        *,
        message_type: typing.Optional[str] = None,
        content_type: typing.Literal["plain", "markdown", "html", "html.raw"] = "markdown",
        mentions: typing.Optional[Mentions] = None,
        override: typing.Optional[dict] = None,
    ) -> nio.RoomSendResponse:
        """Edit an existing message. You must be the sender of the message.

        You also cannot edit messages that are attachments.

        :param room: The room the message is in.
        :param message: The message to edit.
        :param content: The new content of the message.
        :param message_type: The new type of the message (i.e. m.text, m.notice. Defaults to client.global_message_type)
        :param override: A dictionary containing additional properties to pass to the body.
        Overrides existing properties.
        :param content_type: The type of content to send. Defaults to "markdown".
        :raises RuntimeError: If you are not the sender of the message.
        :raises TypeError: If the message is not text.
        """
        room = self._get_id(room)

        event_id = self._get_id(message)
        message_type = message_type or self.global_message_type
        content_dict = {
            "msgtype": message_type,
            "body": content,
            "format": "org.matrix.custom.html",
            "formatted_body": await self.markdown_to_html(content),
        }

        body = {
            "msgtype": message_type,
            "m.new_content": {**content_dict},
            "m.relates_to": {
                "rel_type": "m.replace",
                "event_id": event_id,
            },
            "body": "* %s" % content_dict["body"],
        }

        if content_type == "markdown":
            parsed = await run_blocking(marko.parse, content)
            if parsed.children:
                rendered = await run_blocking(marko.render, parsed)
                body["formatted_body"] = rendered
                body["format"] = "org.matrix.custom.html"
        elif content_type == "html":
            if BeautifulSoup is not None:
                soup = BeautifulSoup(content)
                content_new = soup.prettify("utf-8", "minimal")
            else:
                self.log.debug("Content type was HTML, however BeautifulSoup is not installed. Treating as raw.")
                content_new = content
            body["formatted_body"] = content_new
            body["format"] = "org.matrix.custom.html"
        elif content_type == "html.raw":
            body["formatted_body"] = content
            body["format"] = "org.matrix.custom.html"
        if mentions:
            body.update(mentions.as_body())
        if override:
            body.update(override)
        async with Typing(self, room):
            response = await self.room_send(
                room,
                "m.room.message",
                body,
            )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to edit message.", response)
        # Forcefully clear typing
        await self.room_typing(room, False)
        return response

    async def delete_message(
        self,
        room: U[nio.MatrixRoom, str],
        message_id: U[nio.RoomMessage, str],
        reason: typing.Optional[str] = None,
    ) -> nio.RoomRedactResponse:
        """Delete an existing message. You must be the sender of the message.

        :param room: The room the message is in.
        :param message_id: The message to delete.
        :param reason: The reason for deleting the message.
        :raises RuntimeError: If you are not the sender of the message.
        :raises MessageException: If the message fails to delete.
        """
        room = self._get_id(room)
        message_id = self._get_id(message_id)
        response = await self.room_redact(room, message_id, reason=reason)
        if isinstance(response, nio.RoomRedactError):
            raise MessageException("Failed to delete message.", response)
        return response

    async def add_reaction(
        self,
        room: U[nio.MatrixRoom, str],
        message: U[nio.RoomMessage, str],
        emoji: str,
    ) -> nio.RoomSendResponse:
        """Adds an emoji "reaction" to a message.

        :param room: The room the message is in.
        :param message: The event ID or message object to react to.
        :param emoji: The emoji to react with (e.g. `\N{CROSS MARK}` = ❌)
        :return: The response from the server.
        :raises MessageException: If the message fails to react.
        """
        body = {
            "m.relates_to": {
                "event_id": self._get_id(message),
                "rel_type": "m.annotation",
                "key": emoji,
            },
        }
        response = await self.room_send(
            self._get_id(room),
            "m.reaction",
            body,
        )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to add reaction.", response)
        return response

    async def redact_reaction(self, room: U[nio.MatrixRoom, str], reaction: U[nio.RoomSendResponse, str]):
        """Alias for NioBot.delete_message, but more appropriately named for reactions."""
        response = await self.room_redact(
            self._get_id(room),
            self._get_id(reaction),
        )
        if isinstance(response, nio.RoomRedactError):
            raise MessageException("Failed to delete reaction.", response)
        return response

    async def close(self):
        if self.sync_store:
            await self.sync_store.close()
        await super().close()

    async def start(
        self,
        password: typing.Optional[str] = None,
        access_token: typing.Optional[str] = None,
        sso_token: typing.Optional[str] = None,
    ) -> None:
        """Starts the bot, running the sync loop."""
        self.loop = asyncio.get_event_loop()
        self.dispatch("event_loop_ready")
        if self.__key_import:
            self.log.info("Starting automatic key import")
            await self.import_keys(*map(str, self.__key_import))

        async with self.sync_store:
            if password or sso_token:
                self.log.info("Logging in with a password or SSO token")
                login_response = await self.login(password=password, token=sso_token, device_name=self.device_id)
                if isinstance(login_response, nio.LoginError):
                    raise LoginException("Failed to log in.", login_response)

                self.log.info("Logged in as %s", login_response.user_id)
                self.log.debug(f"Logged in: {login_response.access_token}, {login_response.user_id}")
                self.start_time = time.time()
            elif access_token:
                self.log.info("Logging in with existing access token.")
                if self.store_path:
                    try:
                        self.load_store()
                    except FileNotFoundError:
                        self.log.warning("Failed to load store.")
                    except nio.LocalProtocolError as e:
                        self.log.warning("No store? %r", e, exc_info=e)
                self.access_token = access_token
                self.start_time = time.time()
            else:
                raise LoginException("You must specify either a password/SSO token or an access token.")

            if self.should_upload_keys:
                self.log.info("Uploading encryption keys...")
                response = await self.keys_upload()
                if isinstance(response, nio.KeysUploadError):
                    self.log.critical("Failed to upload encryption keys. Encryption may not work. Error: %r", response)
                else:
                    self.log.info("Uploaded encryption keys.")
            self.log.info("Fetching server details...")
            response = await self.send("GET", "/_matrix/client/versions")
            if response.status != 200:
                self.log.warning("Failed to fetch server details. Status: %d", response.status)
            else:
                self.server_info = await response.json()
                self.log.debug("Server details: %r", self.server_info)

            if self.sync_store:
                self.log.info("Resuming from sync store...")
                try:
                    payload = await self.sync_store.generate_sync()
                    assert isinstance(payload, nio.SyncResponse), "Sync store did not return a SyncResponse."
                    self.log.info("Replaying sync...")
                    await self._handle_sync(payload)
                    self.log.info("Successfully resumed from store.")
                except Exception as e:
                    self.log.error("Failed to replay sync: %r. Will not resume.", e, exc_info=e)

            self.log.info("Uploading sync filter...")
            filter_response = await self.upload_filter(self.user_id, room={"lazy_load_members": True})

            self.log.info("Performing first sync...")

            def presence_getter(stage: int) -> Optional[str]:
                if self._startup_presence is False:
                    return None
                if self._startup_presence is None:
                    return ("unavailable", "online")[stage]
                return self._startup_presence

            result = await self.sync(
                timeout=0,
                full_state=self._sync_full_state,
                set_presence=presence_getter(0),
                sync_filter=filter_response.filter_id,
            )
            if not isinstance(result, nio.SyncResponse):
                raise NioBotException("Failed to perform first sync.", result)
            self.is_ready.set()
            self.dispatch("ready", result)
            self.log.info("Starting sync loop")
            try:
                await self.sync_forever(
                    timeout=30000,
                    full_state=self._sync_full_state,
                    set_presence=presence_getter(1),
                    sync_filter=filter_response.filter_id,
                )
            finally:
                self.log.info("Closing http session.")
                await self.close()

    def run(
        self,
        *,
        password: typing.Optional[str] = None,
        access_token: typing.Optional[str] = None,
        sso_token: typing.Optional[str] = None,
    ) -> None:
        """Runs the bot, blocking the program until the event loop exists.
        This should be the last function to be called in your script, as once it exits, the bot will stop running.

        Note:
            This function is literally just asyncio.run(NioBot.start(...)), so you won't have much control over the
            asyncio event loop. If you want more control, you should use await NioBot.start(...) instead.

        :param password: The password to log in with.
        :param access_token: An existing login token.
        :param sso_token: An SSO token to sign in with.
        :return:

        """
        asyncio.run(self.start(password=password, access_token=access_token, sso_token=sso_token))

    async def _resolve_room_or_user_id(self, target: U[nio.MatrixUser, nio.MatrixRoom, str]) -> str:
        """Returns either a user ID (@example:example.example) or room ID (!123ABC:example.example)"""
        if isinstance(target, nio.MatrixUser):
            return target.user_id
        if isinstance(target, nio.MatrixRoom):
            return target.room_id
        if isinstance(target, str):
            if target.startswith("@"):
                return target
            if target.startswith("#"):
                response = await self.room_resolve_alias(target)
                if isinstance(response, nio.RoomResolveAliasError):
                    raise GenericMatrixError("Unable to resolve room alias %r." % target, response=response)
                room = self.rooms.get(response.room_id)
                if not room:
                    raise ValueError("Room with ID %r is not known." % response.room_id)

                return room.room_id
            raise ValueError("target must be a room or user ID.")
        raise TypeError("target must be a MatrixUser, MatrixRoom, or string; got %r" % target)

    async def get_account_data(self, key: str, *, room_id: str = None) -> typing.Union[dict, list, None]:
        """Gets account data for the currently logged in account

        :param key: the key to get
        :param room_id: The room ID to get account data from. If not provided, defaults to user-level.
        :returns: The account data, or None if it doesn't exist
        """
        path = ["user", self.user_id, "account_data", key]
        if room_id:
            path = ["user", self.user_id, "rooms", room_id, "account_data", key]
        method, path = "GET", Api._build_path(path)
        async with self.send(method, path) as response:
            if response.status != 200:
                return None
            return await response.json()

    async def set_account_data(self, key: str, data: dict, *, room_id: str = None) -> None:
        """Sets account data for the currently logged in account

        :param key: the key to set
        :param data: the data to set
        :param room_id: The room ID to set account data in. If not provided, defaults to user-level.
        """
        path = ["user", self.user_id, "account_data", key]
        if room_id:
            path = ["user", self.user_id, "rooms", room_id, "account_data", key]
        method, path = "PUT", Api._build_path(path)
        async with self.send(method, path, data, {"Content-Type": "application/json"}) as response:
            if response.status != 200:
                return None
            return await response.json()

    async def join(self, room_id: str, reason: str = None, is_dm: bool = False) -> U[JoinResponse, JoinError]:
        """Joins a room. room_id must be a room ID, not alias

        :param room_id: The room ID or alias to join
        :param reason: The reason for joining the room, if any
        :param is_dm: Manually marks this room as a direct message.
        """
        method, path = Api.join(self.access_token, room_id)
        data = {}
        if reason is not None:
            data["reason"] = reason
        r = await self._send(JoinResponse, method, path, Api.to_json(data))
        if not isinstance(r, JoinResponse):
            return r
        return r

    async def room_leave(self, room_id: str, reason: str = None) -> U[RoomLeaveError, RoomLeaveResponse]:
        """Leaves a room. room_id must be an ID, not alias"""
        method, path = Api.room_leave(self.access_token, room_id)
        data = {}
        if reason is not None:
            data["reason"] = reason
        r = await self._send(RoomLeaveResponse, method, path, Api.to_json(data))
        if isinstance(r, RoomLeaveResponse):
            self.log.debug("Left a room successfully. Updating account data if it was a DM room.")
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
                    if room_id in dm_rooms:
                        cpy[user_id].remove(room_id)
                        self.log.debug("Removed room ID %r from DM rooms with %r", room_id, user_id)
                        updated = True
                        break
                else:
                    self.log.warning("Room %s not found in DM list. Possibly not a DM.", room_id)

            if updated:
                self.log.debug(f"Updating DM list in account data from {rooms.rooms} to {cpy}")
                # Update the DM list
                self.log.debug("Account data response: %r", await self.set_account_data("m.direct", cpy))
        return r
