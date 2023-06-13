import asyncio
import logging
import os
import time

import nio
import marko

from .attachment import MediaAttachment
from .exceptions import MessageException, LoginException
from .utils import run_blocking, Typing
from .utils.help_command import help_command
from .commands import Command


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
            store_path: str = "./store",
            *,
            command_prefix: str,
            case_insensitive: bool = True,
            owner_id: str = None,
            **kwargs
    ):
        super().__init__(
            homeserver,
            user_id,
            device_id,
            store_path=store_path,
            config=kwargs.pop("config", None),
            ssl=kwargs.pop("ssl", True),
            proxy=kwargs.pop("proxy", None),
        )

        self.log = logging.getLogger(__name__)
        self.case_insensitive = case_insensitive
        self.command_prefix = command_prefix
        self.owner_id = owner_id

        if command_prefix == "/":
            self.log.warning("The prefix '/' may interfere with client-side commands.")
        if " " in command_prefix:
            raise RuntimeError("Command prefix cannot contain spaces.")

        self.start_time: float | None = None
        self._commands = {
            "help": Command("help", help_command, aliases=["h"], description="Shows a list of commands for this bot")
        }
        self._events = {}
        self._event_tasks = []
        self.global_message_type = kwargs.pop(
            "global_message_type",
            "m.notice"
        )
        self.ignore_old_events = kwargs.pop("ignore_old_events", True)
        # NOTE: `m.notice` prevents bot messages sending off room notifications, and shows darker text
        # (In element at least).

        # noinspection PyTypeChecker
        self.add_event_callback(self.process_message, nio.RoomMessageText)
        self.add_event_callback(
            self.update_read_receipts,
            nio.RoomMessage
        )

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
                task.add_done_callback(lambda: self._event_tasks.remove(task))

    async def update_read_receipts(self, room, event):
        """part of spec module 11.6"""
        self.log.debug("Updating read receipts for %s", room.room_id)
        await self.room_read_markers(room, event.event_id, event.event_id)

    async def process_message(self, room: nio.MatrixRoom, event: nio.RoomMessageText):
        """Processes a message and runs the command it is trying to invoke if any."""
        self.dispatch("message", room, event)
        if event.sender == self.user:
            self.log.debug("Ignoring message sent by self.")
            return
        if self.ignore_old_events and self.start_time is not None:
            server_timestamp_s = event.server_timestamp * 1000
            if (self.start_time - server_timestamp_s) > 0:
                age = self.start_time - server_timestamp_s
                self.log.debug("Ignoring message sent {:.0f} seconds before startup.".format(age))

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
                    result = await command.callback(context)
                except Exception as e:
                    self.dispatch("command_error", context, e)
                    self.log.exception("Error running command %s: %s", command.name, e, exc_info=e)
                else:
                    self.dispatch("command_complete", context, result)
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

    def get_command(self, name: str) -> Command | None:
        """Attempts to retrieve an internal command

        :param name: The name of the command to retrieve
        :return: The command, if found. None otherwise.
        """
        return self._commands.get(name)

    def command(self, name: str = None, **kwargs):
        """Registers a command with the bot."""
        def decorator(func):
            nonlocal name
            name = name or func.__name__
            command = Command(name, func, **kwargs)
            if self.get_command(name):
                raise ValueError(f"Command or alias {name} is already registered.")

            self._commands[name] = command
            for alias in command.aliases:
                if self.get_command(alias):
                    raise ValueError(f"Command or alias {alias} is already registered.")
                self._commands[alias] = command
            return func
        return decorator

    def on_event(self, event_type: str = None):
        if event_type.startswith("on_"):
            self.log.warning("No events start with 'on_' - stripping prefix")
            event_type = event_type[3:]

        def wrapper(func):
            nonlocal event_type
            event_type = event_type or func.__name__
            self._events.setdefault(event_type, [])
            self._events[event_type].append(func)
            return func
        return wrapper

    async def wait_for(self, event_name: str, timeout: float = None, checks=None):
        """
        Waits for an event and returns its result

        :param event_name: The name of the event to listen to
        :param timeout: A timeout, in seconds. Defaults to None for no timeout
        :param checks: A list of check functions to run. Each check function should take a single parameter, the event.
        :return:
        """
        raise NotImplementedError

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

    @staticmethod
    async def _markdown_to_html(text: str) -> str:
        parsed = await run_blocking(marko.parse, text)
        if parsed.children:
            rendered = await run_blocking(marko.render, parsed)
        else:
            rendered = text
        return rendered

    async def send_message(
            self,
            room: nio.MatrixRoom,
            content: str = None,
            file: MediaAttachment = None,
            reply_to: nio.RoomMessageText = None,
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
        :raises ValueError: You specified both file and content, or neither.
        """
        if all((content, file)):
            raise ValueError("You cannot specify both content and file.")
        elif not any((content, file)):
            raise ValueError("You must specify either content or file.")

        body = {
            "msgtype": message_type or self.global_message_type,
            "body": content,
        }

        if reply_to:
            body["m.relates_to"] = {
                "m.in_reply_to": {
                    "event_id": reply_to.event_id
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
                room.room_id,
                "m.room.message",
                body,
            )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to send message.", response)
        await self.room_typing(room.room_id, False)
        return response

    async def edit_message(
            self,
            room: nio.MatrixRoom,
            event_id: str,
            content: str
    ) -> nio.RoomSendResponse:
        """
        Edit an existing message. You must be the sender of the message.

        You also cannot edit messages that are attachments.

        :param room: The room the message is in.
        :param event_id: The message to edit.
        :param content: The new content of the message.
        :raises RuntimeError: If you are not the sender of the message.
        :raises TypeError: If the message is not text.
        """

        content = {
            "msgtype": self.global_message_type,
            "body": content,
            "format": "org.matrix.custom.html",
            "formatted_body": await self._markdown_to_html(content),
        }

        body = {
            "msgtype": "m.text",
            "body": " * %s" % content,
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
                room.room_id,
                "m.room.message",
                body,
            )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to edit message.", response)
        self.log.debug("edit_message: %r" % response)
        return response

    async def delete_message(self, room: nio.MatrixRoom, message_id: str, reason: str = None) -> nio.RoomRedactResponse:
        """
        Delete an existing message. You must be the sender of the message.

        :param room: The room the message is in.
        :param message_id: The message to delete.
        :param reason: The reason for deleting the message.
        :raises RuntimeError: If you are not the sender of the message.
        """
        # TODO: Check power level
        # if message.sender != self.user_id:
        #     raise RuntimeError("You cannot delete a message you did not send.")
        response = await self.room_redact(room.room_id, message_id, reason=reason)
        if isinstance(response, nio.RoomRedactError):
            raise MessageException("Failed to delete message.", response)
        self.log.debug("delete_message: %r", response)
        return response

    async def start(self, password: str = None, access_token: str = None, sso_token: str = None) -> None:
        """Starts the bot, running the sync loop."""
        if password or sso_token:
            self.log.info("Logging in with a password or SSO token")
            login_response = await self.login(password=password, token=sso_token)
            if isinstance(login_response, nio.LoginError):
                raise LoginException("Failed to log in.", login_response)
            else:
                self.log.info("Logged in as %s", login_response.user_id)
                self.log.debug("Logged in: {0.access_token}, {0.user_id}".format(login_response))
                self.start_time = time.time()
        elif access_token:
            self.log.info("Logging in with existing access token.")
            self.access_token = access_token
            self.start_time = time.time()
        else:
            raise LoginException("You must specify either a password/SSO token or an access token.")

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
