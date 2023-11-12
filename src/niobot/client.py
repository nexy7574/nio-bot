import asyncio
import getpass
import importlib
import inspect
import logging
import os
import pathlib
import re
import sys
import time
import typing
import warnings
from collections import deque
from typing import Union as U

import marko
import nio
from nio.crypto import ENCRYPTION_ENABLED

from .attachment import BaseAttachment
from .commands import Command, Module
from .exceptions import *
from .patches.nio__responses import DirectRoomsErrorResponse, DirectRoomsResponse
from .utils import Typing, force_await, run_blocking
from .utils.help_command import default_help_command

if typing.TYPE_CHECKING:
    from .context import Context

__all__ = ("NioBot",)


class NioBot(nio.AsyncClient):
    """
    The main client for NioBot.

    :param homeserver: The homeserver to connect to. e.g. https://matrix-client.matrix.org
    :param user_id: The user ID to log in as. e.g. @user:matrix.org
    :param device_id: The device ID to log in as. e.g. nio-bot
    :param store_path: The path to the store file. Defaults to ./store. Must be a directory.
    :param command_prefix: The prefix to use for commands. e.g. !
    :param case_insensitive: Whether to ignore case when checking for commands. If True, this casefold()s
     incoming messages for parsing.
    :param global_message_type: The message type to default to. Defaults to m.notice
    :param ignore_old_events: Whether to simply discard events before the bot's login.
    :param auto_join_rooms: Whether to automatically join rooms the bot is invited to.
    :param automatic_markdown_renderer: Whether to automatically render markdown in messages when sending/editing.
    :param owner_id: The user ID of the bot owner. If set, only this user can run owner-only commands, etc.
    :param max_message_cache: The maximum number of messages to cache. Defaults to 1000.
    :param ignore_self: Whether to ignore messages sent by the bot itself. Defaults to False. Useful for self-bots.
    :param import_keys: A key export file and password tuple. These keys will be imported at startup.
    """

    def __init__(
        self,
        homeserver: str,
        user_id: str,
        device_id: str = "nio-bot",
        store_path: typing.Optional[str] = None,
        *,
        command_prefix: typing.Union[str, re.Pattern],
        case_insensitive: bool = True,
        owner_id: typing.Optional[str] = None,
        config: typing.Optional[nio.AsyncClientConfig] = None,
        ssl: bool = True,
        proxy: typing.Optional[str] = None,
        help_command: typing.Optional[typing.Union[Command, typing.Callable[["Context"], typing.Any]]] = None,
        global_message_type: typing.Literal["m.text", "m.notice"] = "m.notice",
        ignore_old_events: bool = True,
        auto_join_rooms: bool = True,
        automatic_markdown_renderer: bool = True,
        max_message_cache: int = 1000,
        ignore_self: bool = True,
        import_keys: typing.Tuple[os.PathLike, typing.Optional[str]] = None,
    ):
        if user_id == owner_id and ignore_self is True:
            warnings.warn(
                UserWarning(
                    "User ID and owner ID are the same, but ignore_self is True, meaning no owner systems can be used."
                    " This is probably not what you want."
                )
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
                config = nio.AsyncClientConfig(encryption_enabled=True, store_sync_tokens=True)
                self.log.info("Encryption support enabled automatically.")
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
        self.command_prefix = command_prefix
        self.owner_id = owner_id
        self.ignore_self = ignore_self

        if not isinstance(command_prefix, (str, re.Pattern)):
            raise TypeError("Command prefix must be a string or a regex pattern.")
        if command_prefix == "/":
            self.log.warning("The prefix '/' may interfere with client-side commands on some clients, such as Element.")
        if isinstance(command_prefix, str) and re.search(r"\s", command_prefix):
            raise RuntimeError("Command prefix cannot contain whitespace.")

        self.start_time: typing.Optional[float] = None
        help_cmd = Command(
            "help", default_help_command, aliases=["h"], description="Shows a list of commands for this bot"
        )
        if help_command:
            cmd = help_command
            if isinstance(cmd, Command):
                help_cmd = cmd
            elif asyncio.iscoroutinefunction(cmd) or inspect.isfunction(cmd):
                self.log.warning(
                    "Manually changing default help command callback to %r. Please consider passing your own"
                    " Command instance instead."
                )
                help_cmd.callback = cmd
            else:
                raise TypeError("help_command must be a Command instance or a coroutine/function.")
        self._commands = {"help": help_cmd, "h": help_cmd}
        self._modules = {}
        self._events = {}
        self._event_tasks = []
        self.global_message_type = global_message_type
        self.ignore_old_events = ignore_old_events
        self.auto_join_rooms = auto_join_rooms
        self.automatic_markdown_renderer = automatic_markdown_renderer

        self.add_event_callback(self.process_message, nio.RoomMessageText)  # type: ignore
        self.add_event_callback(self.update_read_receipts, nio.RoomMessage)
        self.direct_rooms: dict[str, nio.MatrixRoom] = {}

        self.message_cache: typing.Deque[typing.Tuple[nio.MatrixRoom, nio.RoomMessageText]] = deque(
            maxlen=max_message_cache
        )
        self.is_ready = asyncio.Event()
        self._waiting_events = {}

        if self.auto_join_rooms:
            self.log.info("Auto-joining rooms enabled.")
            self.add_event_callback(self._auto_join_room_backlog_callback, nio.InviteMemberEvent)  # type: ignore

        if import_keys:
            keys_path, keys_password = import_keys
            if not keys_password:
                if sys.stdin.isatty():
                    keys_password = getpass.getpass(f"Password for key import ({keys_path}): ")
                else:
                    raise ValueError(
                        "No password was provided for automatic key import and cannot interactively get password."
                    )

            self.__key_import = pathlib.Path(keys_path), keys_password
        else:
            self.__key_import = None

    async def sync(self, *args, **kwargs) -> U[nio.SyncResponse, nio.SyncError]:
        sync = await super().sync(*args, **kwargs)
        if isinstance(sync, nio.SyncResponse):
            self._populate_dm_rooms(sync)
        return sync

    def _populate_dm_rooms(self, sync: nio.SyncResponse):
        # This function is a workaround until a solution is implemented upstream.
        # This function is unreliable (see: `is_direct` below, not always provided, optional in spec)
        # See: https://github.com/poljar/matrix-nio/issues/421
        for room_id, room_info in sync.rooms.join.items():
            for event in room_info.state:
                if isinstance(event, nio.RoomMemberEvent):
                    prev = event.prev_content or {}
                    if event.content.get("is_direct", prev.get("is_direct", False)):
                        self.log.debug("Found DM room in sync: %s", room_id)
                        self.direct_rooms[event.state_key] = self.rooms[room_id]

    async def _auto_join_room_callback(self, room: nio.MatrixRoom, _: nio.InviteMemberEvent):
        """Callback for auto-joining rooms"""
        if self.auto_join_rooms:
            self.log.info("Joining room %s", room.room_id)
            result = await self.join(room.room_id)
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
        :return: The latency in milliseconds"""
        now = received_at or time.time()
        return (now - event.server_timestamp / 1000) * 1000

    def dispatch(self, event_name: str, *args, **kwargs):
        """Dispatches an event to listeners"""
        if event_name in self._events:
            for handler in self._events[event_name]:
                self.log.debug("Dispatching %s to %r" % (event_name, handler))
                try:
                    task = asyncio.create_task(
                        handler(*args, **kwargs), name="DISPATCH_%s_%s" % (handler.__qualname__, os.urandom(3).hex())
                    )
                    self._event_tasks.append(task)
                    task.add_done_callback(
                        lambda *_, **__: self._event_tasks.remove(task) if task in self._event_tasks else None
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
        """
        Moves the read indicator to the given event in the room.

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

    async def process_message(self, room: nio.MatrixRoom, event: nio.RoomMessageText) -> None:
        """Processes a message and runs the command it is trying to invoke if any."""
        if self.start_time is None:
            raise RuntimeError("Bot has not started yet!")

        self.message_cache.append((room, event))
        self.dispatch("message", room, event)
        if event.sender == self.user and self.ignore_self is True:
            self.log.debug("Ignoring message sent by self.")
            return
        if self.is_old(event):
            age = self.start_time - event.server_timestamp / 1000
            self.log.debug("Ignoring message sent {:.0f} seconds before startup.".format(age))
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
                if c.startswith(self.command_prefix):
                    return self.command_prefix

        matched_prefix = get_prefix(content)
        if matched_prefix:
            try:
                command = original_command = content[len(matched_prefix) :].splitlines()[0].split(" ")[0]
            except IndexError:
                self.log.info(
                    "Failed to parse message %r - message terminated early (was the content *just* the prefix?)",
                    event.body,
                )
                return
            command = self.get_command(command)
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
                self.dispatch("command", context)

                def _task_callback(t: asyncio.Task):
                    try:
                        exc = t.exception()
                    except asyncio.CancelledError:
                        self.dispatch("command_cancelled", context, t)
                    else:
                        if exc:
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
                    self.log.exception("Failed to invoke command %s", command.name)
                    self.dispatch("command_error", context, CommandError(exception=e))
                else:
                    task.add_done_callback(_task_callback)
            else:
                self.log.debug(f"Command {original_command!r} not found.")

    def is_owner(self, user_id: str) -> bool:
        """
        Checks whether a user is the owner of the bot.

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

            You can get around this by deferring mounting your modules until the `bot.on_ready` event is fired,
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
            module.setup(self)
            return

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
        """
        Does the opposite of mounting the module.
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
    def modules(self) -> dict[typing.Type[Module], Module]:
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
        Otherwise, it returns None."""
        if self.get_command(command.name):
            raise ValueError(f"Command or alias {command.name} is already registered.")
        if any((self.get_command(alias) for alias in command.aliases)):
            raise ValueError(f"Command or alias for {command.name} is already registered.")

        self._commands[command.name] = command
        self.log.debug("Registered command %r into %s", command, command.name)
        for alias in command.aliases:
            self._commands[alias] = command
            self.log.debug("Registered command %r into %s", command, alias)

    def remove_command(self, command: Command) -> None:
        """Removes a command from the internal register.

        If the command is not registered, this is a no-op."""
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

    def add_event_listener(self, event_type: str, func):
        self._events.setdefault(event_type, [])
        self._events[event_type].append(func)
        self.log.debug("Added event listener %r for %r", func, event_type)

    def on_event(self, event_type: typing.Optional[str] = None):
        """Wrapper that allows you to register an event handler"""

        def wrapper(func):
            nonlocal event_type
            event_type = event_type or func.__name__
            if event_type.startswith("on_"):
                self.log.warning("No events start with 'on_' - stripping prefix")
                event_type = event_type[3:]
            self.add_event_listener(event_type, func)
            return func

        return wrapper

    def remove_event_listener(self, function):
        for event_type, functions in self._events.items():
            if function in functions:
                self._events[event_type].remove(function)
                self.log.debug("Removed %r from event %r", function, event_type)

    async def set_room_nickname(
        self,
        room: U[str, nio.MatrixRoom],
        new_nickname: str = None,
        user: typing.Optional[U[str, nio.MatrixUser]] = None,
    ) -> nio.RoomPutStateResponse:
        """
        Changes the user's nickname in the given room.

        :param room: The room to change the nickname in.
        :param new_nickname: The new nickname. If None, defaults to the user's display name.
        :param user: The user to update. Defaults to the bot's user.
        :return: The response from the server.
        :raises: GenericMatrixError - The request failed.
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

    def get_cached_message(self, event_id: str) -> typing.Optional[typing.Tuple[nio.MatrixRoom, nio.RoomMessageText]]:
        """Fetches a message from the cache.

        This returns both the room the message was sent in, and the event itself.

        If the message is not in the cache, this returns None."""
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
    ) -> typing.Optional[typing.Tuple[nio.MatrixRoom, nio.RoomMessageText]]:
        """Waits for a message, optionally with a filter.

        If this function times out, asyncio.TimeoutError is raised."""
        event = asyncio.Event()
        value = None

        async def event_handler(_room, _event):
            if room_id and _room.room_id != room_id:
                self.log.debug("Ignoring bubbling message from %r (vs %r)", _room.room_id, room_id)
                return False
            if sender and _event.sender != sender:
                self.log.debug("Ignoring bubbling message from %r (vs %r)", _event.sender, sender)
                return False
            if check:
                try:
                    result = await force_await(check, _room, _event)
                except Exception as e:
                    self.log.error("Error in check function: %r", e, exc_info=e)
                    return False
                if not result:
                    self.log.debug("Ignoring bubbling message, check was false")
                    return False
            event.set()
            nonlocal value
            value = _room, _event

        self.on_event("message")(event_handler)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        finally:
            self.remove_event_listener(event_handler)
        return value

    @staticmethod
    async def _markdown_to_html(text: str) -> str:
        parsed = await run_blocking(marko.parse, text)
        if parsed.children:
            rendered = await run_blocking(marko.render, parsed)
        else:
            rendered = text
        return rendered

    @staticmethod
    def _get_id(obj: typing.Union[nio.Event, nio.MatrixRoom, nio.MatrixUser, str, typing.Any]) -> str:
        """Gets the id of most objects as a string.
        :param obj: The object who's ID to get, or the ID itself.
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
        raise ValueError("Unable to determine ID")

    @staticmethod
    def generate_mx_reply(room: nio.MatrixRoom, event: nio.RoomMessageText) -> str:
        """Generates a reply string for a given event."""
        return (
            "<mx-reply>"
            "<blockquote>"
            '<a href="{reply_url}">{reply}</a> '
            '<a href="{user_url}">{user}</a><br/>'
            "</blockquote>"
            "</mx-reply>".format(
                reply_url="https://matrix.to/#/{}:{}/{}".format(
                    room.room_id, room.machine_name.split(":")[1], event.event_id
                ),
                reply=event.body,
                user_url="https://matrix.to/#/{}".format(event.sender),
                user=event.sender,
            )
        )

    async def _recursively_upload_attachments(
        self, base: "BaseAttachment", encrypted: bool = False, __previous: typing.Optional[list] = None
    ) -> list[typing.Union[nio.UploadResponse, nio.UploadError, None]]:
        """Recursively uploads attachments."""
        previous = (__previous or []).copy()
        if not base.url:
            self.log.info("Uploading attachment %r (encrypted: %r)", base, encrypted)
            previous.append(await base.upload(self, encrypted))
        if hasattr(base, "thumbnail") and base.thumbnail and not base.url:
            self.log.info("Uploading thumbnail %r (encrypted: %r)", base.thumbnail, encrypted)
            previous += await self._recursively_upload_attachments(base.thumbnail, encrypted, previous)
        return previous

    @typing.overload
    async def get_dm_rooms(self) -> typing.Dict[str, typing.List[str]]:
        """
        Gets all DM rooms stored in account data.

        :return: A dictionary containing user IDs as keys, and lists of room IDs as values.
        """
        ...

    @typing.overload
    async def get_dm_rooms(self, user: U[nio.MatrixUser, str]) -> typing.List[str]:
        """
        Gets DM rooms for a specific user.

        :param user: The user to fetch DM rooms for.
        :return: A list of room IDs
        """
        ...

    async def get_dm_rooms(
        self,
        user: typing.Optional[U[nio.MatrixUser, str]] = None,
    ) -> typing.Union[typing.Dict[str, typing.List[str]], typing.List[str]]:
        """
        Gets DM rooms, optionally for a specific user.

        If no user is given, this returns a dictionary of user IDs to lists of rooms.

        :param user: The user ID or object to get DM rooms for.
        :return: A dictionary of user IDs to lists of rooms, or a list of rooms.
        """
        # When https://github.com/poljar/matrix-nio/pull/451/ is merged in the next version of matrix-nio,
        # this function should be changed to use Api.list_direct_rooms.
        # For now, I'll just pull the code from the PR and whack it in here.
        # It's ugly, but it's better than what we had before:
        # https://github.com/nexy7574/niobot/blob/216509/src/niobot/client.py#L668-L701

        result = await self._send(
            DirectRoomsResponse,
            "GET",
            nio.Api._build_path(["user", self.user_id, "account_data", "m.direct"]),
        )
        if isinstance(result, DirectRoomsErrorResponse):
            raise GenericMatrixError("Failed to get DM rooms", response=result)
        if user:
            user_id = self._get_id(user)
            return result.rooms.get(user_id, [])
        return result.rooms

    async def create_dm_room(
        self,
        user: U[nio.MatrixUser, str],
    ) -> nio.RoomCreateResponse:
        """
        Creates a DM room with a given user.

        :param user: The user to create a DM room with.
        :return: The response from the server.
        """
        user_id = self._get_id(user)
        result = await self.room_create(
            is_direct=True,
            invitees=[user_id],
        )
        if isinstance(result, nio.RoomCreateError):
            raise GenericMatrixError("Failed to create DM room", response=result)
        return result

    async def send_message(
        self,
        room: U[nio.MatrixRoom, nio.MatrixUser, str],
        content: typing.Optional[str] = None,
        file: typing.Optional[BaseAttachment] = None,
        reply_to: typing.Optional[U[nio.RoomMessageText, str]] = None,
        message_type: typing.Optional[str] = None,
        clean_mentions: typing.Optional[bool] = False,
        *,
        override: typing.Optional[dict] = None,
    ) -> nio.RoomSendResponse:
        """
        Sends a message.

        !!! tip "New! DMs!"
            As of v1.1.0, you can now send messages to users (either a [nio.MatrixUser][] or a user ID string),
            and a direct message room will automatically be created for you if one does not exist, using an existing
            one if it does.

        :param room: The room or to send this message to
        :param content: The content to send. Cannot be used with file.
        :param file: A file to send, if any. Cannot be used with content.
        :param reply_to: A message to reply to.
        :param message_type: The message type to send. If none, defaults to NioBot.global_message_type,
        which itself is `m.notice` by default.
        :param clean_mentions: Whether to escape all mentions
        :param override: A dictionary containing additional properties to pass to the body.
        Overrides existing properties.
        :return: The response from the server.
        :raises MessageException: If the message fails to send, or if the file fails to upload.
        :raises ValueError: You specified neither file nor content.
        """
        if file and BaseAttachment is None:
            raise ValueError("You are missing required libraries to use attachments.")
        if not any((content, file)):
            raise ValueError("You must specify either content or file.")

        if isinstance(room, nio.MatrixUser) or (isinstance(room, str) and room.startswith("@")):
            _user = room
            rooms = await self.get_dm_rooms(_user)
            if rooms:
                room = rooms[0]
            else:
                room = await self.create_dm_room(_user)

        self.log.debug("Send message resolved room to %r", room)

        body: dict[str, typing.Any] = {
            "msgtype": message_type or self.global_message_type,
        }

        if file is not None:
            self.log.info("Recursively uploading %r.", file)
            # We need to upload the file first.
            responses = await self._recursively_upload_attachments(file, encrypted=getattr(file, "encrypted", False))
            if any((isinstance(response, nio.UploadError) for response in responses)):
                raise MessageException(
                    "Failed to upload media.", tuple(filter(lambda x: isinstance(x, nio.UploadError), responses))[0]
                )

            body = file.as_body(content)
        else:
            if clean_mentions and content:
                content = content.replace("@", "@\u200b")
            body["body"] = content
            if self.automatic_markdown_renderer:
                parsed = await run_blocking(marko.parse, content)
                if parsed.children:
                    rendered = await run_blocking(marko.render, parsed)
                    body["formatted_body"] = rendered
                    body["format"] = "org.matrix.custom.html"

                if reply_to and isinstance(reply_to, nio.RoomMessageText) and isinstance(room, nio.MatrixRoom):
                    body["formatted_body"] = "{}{}".format(
                        self.generate_mx_reply(room, reply_to), body.get("formatted_body", body["body"])
                    )
                    body["format"] = "org.matrix.custom.html"

        if reply_to:
            body["m.relates_to"] = {"m.in_reply_to": {"event_id": self._get_id(reply_to)}}

        if override:
            body.update(override)
        async with Typing(self, self._get_id(room)):
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
        clean_mentions: bool = False,
        override: typing.Optional[dict] = None,
    ) -> nio.RoomSendResponse:
        """
        Edit an existing message. You must be the sender of the message.

        You also cannot edit messages that are attachments.

        :param room: The room the message is in.
        :param message: The message to edit.
        :param content: The new content of the message.
        :param message_type: The new type of the message (i.e. m.text, m.notice. Defaults to client.global_message_type)
        :param clean_mentions: Whether to escape all mentions
        :param override: A dictionary containing additional properties to pass to the body.
        Overrides existing properties.
        :raises RuntimeError: If you are not the sender of the message.
        :raises TypeError: If the message is not text.
        """
        room = self._get_id(room)

        if clean_mentions:
            content = content.replace("@", "@\u200b")
        event_id = self._get_id(message)
        message_type = message_type or self.global_message_type
        content_dict = {
            "msgtype": message_type,
            "body": content,
            "format": "org.matrix.custom.html",
            "formatted_body": await self._markdown_to_html(content),
        }

        body = {
            "msgtype": message_type,
            "body": " * %s" % content_dict["body"],
            "m.new_content": {**content_dict},
            "m.relates_to": {
                "rel_type": "m.replace",
                "event_id": event_id,
            },
        }
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
        self, room: U[nio.MatrixRoom, str], message_id: U[nio.RoomMessage, str], reason: typing.Optional[str] = None
    ) -> nio.RoomRedactResponse:
        """
        Delete an existing message. You must be the sender of the message.

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
        self, room: U[nio.MatrixRoom, str], message: U[nio.RoomMessage, str], emoji: str
    ) -> nio.RoomSendResponse:
        """
        Adds an emoji "reaction" to a message.

        :param room: The room the message is in.
        :param message: The event ID or message object to react to.
        :param emoji: The emoji to react with (e.g. `\N{cross mark}` = ❌)
        :return: The response from the server.
        :raises MessageException: If the message fails to react.
        """
        body = {
            "m.relates_to": {
                "event_id": self._get_id(message),
                "rel_type": "m.annotation",
                "key": emoji,
            }
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

        if password or sso_token:
            if password:
                self.log.critical(
                    "Logging in with a password is insecure, slow, and clunky. "
                    "An access token will be issued after logging in, please use that. For more information, see:"
                    "https://nexy7574.github.io/niobot/guides/faq.html#why-is-logging-in-with-a-password-so-bad"
                )
            self.log.info("Logging in with a password or SSO token")
            login_response = await self.login(password=password, token=sso_token, device_name=self.device_id)
            if isinstance(login_response, nio.LoginError):
                raise LoginException("Failed to log in.", login_response)

            self.log.info("Logged in as %s", login_response.user_id)
            self.log.debug("Logged in: {0.access_token}, {0.user_id}".format(login_response))
            self.start_time = time.time()
        elif access_token:
            self.log.info("Logging in with existing access token.")
            if self.store_path:
                try:
                    self.load_store()
                except FileNotFoundError:
                    self.log.warning("Failed to load store.")
                except nio.LocalProtocolError as e:
                    self.log.warning("No store?? %r", e, exc_info=e)
            self.access_token = access_token
            self.start_time = time.time()
        else:
            raise LoginException("You must specify either a password/SSO token or an access token.")

        if self.should_upload_keys:
            self.log.info("Uploading encryption keys...")
            response = await self.keys_upload()
            if isinstance(response, nio.KeysUploadError):
                self.log.critical("Failed to upload encryption keys. Encryption may not work.")
            self.log.info("Uploaded encryption keys.")
        self.log.info("Performing first sync...")
        result = await self.sync(timeout=30000, full_state=True, set_presence="unavailable")
        if not isinstance(result, nio.SyncResponse):
            raise NioBotException("Failed to perform first sync.", result)
        self.is_ready.set()
        self.dispatch("ready", result)
        self.log.info("Starting sync loop")
        try:
            await self.sync_forever(
                timeout=30000,
                full_state=True,
                set_presence="online",
            )
        finally:
            self.log.info("Closing http session and logging out.")
            await self.close()

    def run(
        self,
        *,
        password: typing.Optional[str] = None,
        access_token: typing.Optional[str] = None,
        sso_token: typing.Optional[str] = None,
    ) -> None:
        """
        Runs the bot, blocking the program until the event loop exists.
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
