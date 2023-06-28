import asyncio
import logging
import os
import importlib
import time
import inspect
import typing
from collections import deque

import nio
from nio.crypto import ENCRYPTION_ENABLED
import marko

from .attachment import MediaAttachment
from .exceptions import *
from .utils import run_blocking, Typing, force_await
from .utils.help_command import help_command
from .commands import Command, Module


__all__ = (
    "NioBot",
)


class NioBot(nio.AsyncClient):
    """
    The main client for NioBot.

    :param homeserver: The homeserver to connect to. e.g. https://matrix-client.matrix.org
    :param user_id: The user ID to log in as. e.g. @user:matrix.org
    :param device_id: The device ID to log in as. e.g. nio-bot
    :param store_path: The path to the store file. Defaults to ./store. Must be a directory.
    :param command_prefix: The prefix to use for commands. e.g. !
    :param case_insensitive: Whether to ignore case when checking for commands. If True, this lower()s
     incoming messages for parsing.
    :param global_message_type: The message type to default to. Defaults to m.notice
    :param ignore_old_events: Whether to simply discard events before the bot's login.
    :param owner_id: The user ID of the bot owner. If set, only this user can run owner-only commands, etc.
    """
    def __init__(
            self,
            homeserver: str,
            user_id: str,
            device_id: str = "nio-bot",
            store_path: str = None,
            *,
            command_prefix: str,
            case_insensitive: bool = True,
            owner_id: str = None,
            **kwargs
    ):
        self.log = logging.getLogger(__name__)
        if store_path:
            if not os.path.exists(store_path):
                self.log.warning("Store path %s does not exist, creating...", store_path)
                os.makedirs(store_path, mode=0o755, exist_ok=True)
            elif not os.path.isdir(store_path):
                raise RuntimeError("Store path %s is not a directory!" % store_path)

        if ENCRYPTION_ENABLED:
            if not kwargs.get("config"):
                kwargs.setdefault(
                    "config",
                    nio.AsyncClientConfig(
                        encryption_enabled=True,
                        store_sync_tokens=True
                    )
                )
                self.log.info("Encryption support enabled automatically.")

        super().__init__(
            homeserver,
            user_id,
            device_id,
            store_path=store_path,
            config=kwargs.pop("config", None),
            ssl=kwargs.pop("ssl", True),
            proxy=kwargs.pop("proxy", None),
        )
        self.user_id = user_id
        self.device_id = device_id
        self.store_path = store_path
        self.case_insensitive = case_insensitive
        self.command_prefix = command_prefix
        self.owner_id = owner_id

        if command_prefix == "/":
            self.log.warning("The prefix '/' may interfere with client-side commands.")
        if " " in command_prefix:
            raise RuntimeError("Command prefix cannot contain spaces.")

        self.start_time: float | None = None
        help_cmd = Command("help", help_command, aliases=["h"], description="Shows a list of commands for this bot")
        self._commands = {
            "help": help_cmd,
            "h": help_cmd
        }
        self._modules = {}
        self._events = {}
        self._event_tasks = []
        self.global_message_type = kwargs.pop(
            "global_message_type",
            "m.notice"
        )
        self.ignore_old_events = kwargs.pop("ignore_old_events", True)
        self.auto_join_rooms = kwargs.pop("auto_join_rooms", True)
        # NOTE: `m.notice` prevents bot messages sending off room notifications, and shows darker text
        # (In element at least).

        # noinspection PyTypeChecker
        self.add_event_callback(self.process_message, nio.RoomMessageText)
        self.add_event_callback(
            self.update_read_receipts,
            nio.RoomMessage
        )

        self.message_cache: typing.Deque[typing.Tuple[nio.MatrixRoom, nio.RoomMessageText]] = deque(
            maxlen=kwargs.pop("max_message_cache", 1000)
        )
        self._waiting_events = {}

        # noinspection PyTypeChecker
        self.add_event_callback(self.auto_join_room_backlog_callback, nio.InviteMemberEvent)

    async def auto_join_room_callback(self, room: nio.MatrixRoom, _: nio.InviteMemberEvent):
        """Callback for auto-joining rooms"""
        if self.auto_join_rooms:
            self.log.info("Joining room %s", room.room_id)
            result = await self.join(room.room_id)
            if isinstance(result, nio.JoinError):
                self.log.error("Failed to join room %s: %s", room.room_id, result.message)
            else:
                self.log.info("Joined room %s", room.room_id)

    async def auto_join_room_backlog_callback(self, room: nio.MatrixRoom, event: nio.InviteMemberEvent):
        """Callback for auto-joining rooms that are backlogged on startup"""
        if event.state_key == self.user_id:
            await self.auto_join_room_callback(room, event)

    @staticmethod
    def latency(event: nio.Event, *, received_at: float = None) -> float:
        """Returns the latency for a given event in milliseconds

        :param event: The event to measure latency with
        :param received_at: The optional time the event was received at. If not given, uses the current time.
        :return: The latency in milliseconds"""
        now = received_at or time.time()
        return (now - event.server_timestamp / 1000) * 1000

    @property
    def commands(self):
        """A copy of the commands register"""
        return self._commands.copy()

    @property
    def modules(self):
        """A copy of the modules register"""
        return self._modules.copy()

    def dispatch(self, event_name: str, *args, **kwargs):
        """Dispatches an event to listeners"""
        if event_name in self._events:
            for handler in self._events[event_name]:
                self.log.debug("Dispatching %s to %r" % (event_name, handler))
                task = asyncio.create_task(
                    handler(*args, **kwargs),
                    name="DISPATCH_%s_%s" % (handler.__qualname__, os.urandom(3).hex())
                )
                self._event_tasks.append(task)
                task.add_done_callback(lambda *_, **__: self._event_tasks.remove(task))
        else:
            self.log.debug("%r is not in registered events: %s", event_name, self._events)

    def is_old(self, event: nio.Event) -> bool:
        """Checks if an event was sent before the bot started. Always returns False when ignore_old_evens is False"""
        if not self.start_time:
            self.log.warning("have not started yet, using relative age comparison")
            start_time = time.time() - 30  # relative
        else:
            start_time = self.start_time
        if self.ignore_old_events is False:
            return False
        return start_time - event.server_timestamp / 1000 > 0

    async def update_read_receipts(self, room, event):
        """part of spec module 11.6"""
        if self.is_old(event):
            self.log.debug("Ignoring event %s, sent before bot started.", event.event_id)
            return
        self.log.debug("Updating read receipts for %s", room.room_id)
        await self.room_read_markers(room, event.event_id, event.event_id)

    async def process_message(self, room: nio.MatrixRoom, event: nio.RoomMessageText):
        """Processes a message and runs the command it is trying to invoke if any."""
        self.message_cache.append((room, event))
        self.dispatch("message", room, event)
        if event.sender == self.user:
            self.log.debug("Ignoring message sent by self.")
            return
        if self.is_old(event):
            age = self.start_time - event.server_timestamp / 1000
            self.log.debug("Ignoring message sent {:.0f} seconds before startup.".format(age))
            return

        if self.case_insensitive:
            content = event.body.lower()
        else:
            content = event.body

        if content.startswith(self.command_prefix):
            command = original_command = content[len(self.command_prefix):].split(" ")[0]
            command = self.get_command(command)
            if command:
                context = command.construct_context(self, room, event, self.command_prefix + original_command)
                self.dispatch("command", context)
                self.log.debug(f"Running command {command.name} with context {context!r}")
                try:
                    task = asyncio.create_task(command.invoke(context))
                except Exception as e:
                    self.log.exception("Failed to invoke command %s", command.name)
                    self.dispatch("command_error", context, CommandError(exception=e))
                else:
                    task.add_done_callback(
                        lambda _res: self.dispatch("command_complete", context, _res)
                    )
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

        :param import_path: The import path (such as modules.file), which would be ./modules/file.py in a file tree.
        :returns: Optional[List[Command]] - A list of commands mounted. None if the module's setup() was called.
        :raises: ImportError - The module path is incorrect of there was another error while importing
        :raises: TypeError - The module was not a subclass of Module.
        :raises: ValueError - There was an error registering a command (e.g. name conflict)
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
                        instance.__class__.__qualname__
                    )
                else:
                    self.log.debug("%r does not appear to be a niobot module", item)
        return added

    def get_command(self, name: str) -> Command | None:
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

    def command(self, name: str = None, **kwargs):
        """Registers a command with the bot."""
        cls = kwargs.pop("cls", Command)

        def decorator(func):
            nonlocal name
            name = name or func.__name__
            command = cls(name, func, **kwargs)
            self.add_command(command)
            return func
        return decorator

    def add_event(self, event_type: str, func):
        self._events.setdefault(event_type, [])
        self._events[event_type].append(func)
        self.log.debug("Added event listener %r for %r", func, event_type)

    def on_event(self, event_type: str = None):
        if event_type.startswith("on_"):
            self.log.warning("No events start with 'on_' - stripping prefix")
            event_type = event_type[3:]

        def wrapper(func):
            nonlocal event_type
            event_type = event_type or func.__name__
            self.add_event(event_type, func)
            return func
        return wrapper

    def remove_event_listener(self, function):
        for event_type, functions in self._events.items():
            if function in functions:
                self._events[event_type].remove(function)
                self.log.debug("Removed %r from event %r", function, event_type)

    async def room_send(
        self,
        room_id: str,
        message_type: str,
        content: dict,
        tx_id: str | None = None,
        ignore_unverified_devices: bool = True,
    ) -> nio.RoomSendResponse | nio.RoomSendError:
        """
        Send a message to a room.
        """
        return await super().room_send(
            room_id,
            message_type,
            content,
            tx_id,
            ignore_unverified_devices,
        )

    def get_cached_message(self, event_id: str) -> typing.Optional[
        typing.Tuple[nio.MatrixRoom, nio.RoomMessageText]
    ]:
        """Fetches a message from the cache.

        This returns both the room the message was sent in, and the event itself.

        If the message is not in the cache, this returns None."""
        for room, event in self.message_cache:
            if event_id == event.event_id:
                return room, event

    async def wait_for_message(
            self,
            room_id: str = None,
            sender: str = None,
            check: typing.Callable[[nio.MatrixRoom, nio.RoomMessageText], typing.Any] = None,
            *,
            timeout: float = None
    ) -> typing.Optional[typing.Tuple[nio.MatrixRoom, nio.RoomMessageText]]:
        """Waits for a message, optionally with a filter.

        If this function times out, asyncio.TimeoutError is raised."""
        event = asyncio.Event()
        value = None

        async def event_handler(_room, _event):
            if room_id:
                if _room.room_id != room_id:
                    self.log.debug("Ignoring bubbling message from %r (vs %r)", _room.room_id, room_id)
                    return False
            if sender:
                if _event.sender != sender:
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
    def _get_id(obj) -> str:
        if hasattr(obj, "room_id"):
            return obj.room_id
        if hasattr(obj, "event_id"):
            return obj.event_id
        if isinstance(obj, str):
            return obj
        raise ValueError("Unable to determine ID")

    async def send_message(
            self,
            room: nio.MatrixRoom | str,
            content: str = None,
            file: MediaAttachment = None,
            reply_to: nio.RoomMessageText | str = None,
            message_type: str = None
    ) -> nio.RoomSendResponse:
        """
        Sends a message.

        :param room: The room to send this message to
        :param content: The content to send. Cannot be used with file.
        :param file: A file to send, if any. Cannot be used with content.
        :param reply_to: A message to reply to.
        :param message_type: The message type to send. If none, defaults to NioBot.global_message_type, which itself
        is `m.notice` by default.
        :return: The response from the server.
        :raises MessageException: If the message fails to send, or if the file fails to upload.
        :raises ValueError: You specified neither file nor content.
        """
        if not any((content, file)):
            raise ValueError("You must specify either content or file.")
        elif file and not content:
            raise ValueError("You must specify content (a textual description of the media) while using file.")

        body = {
            "msgtype": message_type or self.global_message_type,
            "body": content,
        }

        if reply_to:
            body["m.relates_to"] = {
                "m.in_reply_to": {
                    "event_id": self._get_id(reply_to)
                }
            }

        if file:
            # We need to upload the file first.
            response = await file.upload(self)
            if isinstance(response, nio.UploadError):
                raise MessageException("Failed to upload media.", response)

            body["msgtype"] = file.media_type
            body["info"] = file.to_dict()
            body["url"] = file.url
        else:
            parsed = await run_blocking(marko.parse, content)
            if parsed.children:
                rendered = await run_blocking(marko.render, parsed)
                body["formatted_body"] = rendered
                body["format"] = "org.matrix.custom.html"
        async with Typing(self, room.room_id):
            response = await self.room_send(
                self._get_id(room),
                "m.room.message",
                body,
            )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to send message.", response)
        await self.room_typing(room.room_id, False)
        return response

    async def edit_message(
            self,
            room: nio.MatrixRoom | str,
            event_id: nio.Event | str,
            content: str,
            *,
            message_type: str = None,
    ) -> nio.RoomSendResponse:
        """
        Edit an existing message. You must be the sender of the message.

        You also cannot edit messages that are attachments.

        :param room: The room the message is in.
        :param event_id: The message to edit.
        :param content: The new content of the message.
        :param message_type: The new type of the message (i.e. m.text, m.notice. Defaults to client.global_message_type)
        :raises RuntimeError: If you are not the sender of the message.
        :raises TypeError: If the message is not text.
        """
        event_id = self._get_id(event_id)
        message_type = message_type or self.global_message_type
        content = {
            "msgtype": message_type,
            "body": content,
            "format": "org.matrix.custom.html",
            "formatted_body": await self._markdown_to_html(content),
        }

        body = {
            "msgtype": message_type,
            "body": " * %s" % content["body"],
            "m.new_content": {
                **content
            },
            "m.relates_to": {
                "rel_type": "m.replace",
                "event_id": event_id,
            },
            "format": "org.matrix.custom.html",
            "formatted_body": content["formatted_body"]
        }
        async with Typing(self, room.room_id):
            response = await self.room_send(
                self._get_id(room),
                "m.room.message",
                body,
            )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to edit message.", response)
        return response

    async def delete_message(
            self,
            room: nio.MatrixRoom | str,
            message_id: nio.RoomMessage | str,
            reason: str = None
    ) -> nio.RoomRedactResponse:
        """
        Delete an existing message. You must be the sender of the message.

        :param room: The room the message is in.
        :param message_id: The message to delete.
        :param reason: The reason for deleting the message.
        :raises RuntimeError: If you are not the sender of the message.
        """
        room = self._get_id(room)
        message_id = self._get_id(message_id)
        response = await self.room_redact(room, message_id, reason=reason)
        if isinstance(response, nio.RoomRedactError):
            raise MessageException("Failed to delete message.", response)
        self.log.debug("delete_message: %r", response)
        return response

    async def start(self, password: str = None, access_token: str = None, sso_token: str = None) -> None:
        """Starts the bot, running the sync loop."""
        if password or sso_token:
            self.log.info("Logging in with a password or SSO token")
            login_response = await self.login(password=password, token=sso_token, device_name=self.device_id)
            if isinstance(login_response, nio.LoginError):
                raise LoginException("Failed to log in.", login_response)
            else:
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

    def run(self, *, password: str = None, access_token: str = None, sso_token: str = None) -> None:
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
