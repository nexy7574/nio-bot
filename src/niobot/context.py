from __future__ import annotations

import logging
import time
import typing

import nio
import typing_extensions

from .utils.lib import deprecated
from .utils.string_view import ArgumentView

if typing.TYPE_CHECKING:
    from .client import NioBot
    from .commands import Command


__all__ = ("Context", "ContextualResponse")

logger = logging.getLogger(__name__)


class ContextualResponse:
    """Context class for managing replies.

    Usage of this function is not required, however it is a useful utility.
    """

    def __init__(self, ctx: Context, response: nio.RoomSendResponse):
        self.ctx = ctx
        self._response = response

    def __repr__(self):
        return f"<ContextualResponse ctx={self.ctx!r} response={self._response!r}>"

    @property
    @deprecated("original_event", "1.3.0")
    def message(self) -> typing.Optional[nio.RoomMessage]:
        result = self.ctx.client.get_cached_message(self._response.event_id)
        if result:
            return result[1]
        logger.warning("Original response for context %r was not found in cache, unable to modify.", self.ctx)

    async def original_event(self) -> typing.Optional[nio.RoomMessage]:
        """Fetches the current event for this response"""
        result = self.ctx.client.get_cached_message(self._response.event_id)
        if result:
            return result[1]
        event = await self.ctx.client.room_get_event(self.ctx.room.room_id, self._response.event_id)
        if isinstance(event, nio.RoomGetEventResponse):
            return nio.RoomMessage.parse_event(event.event.source)

    async def reply(self, *args, **kwargs) -> ContextualResponse:
        """Replies to the current response.

        This does NOT reply to the original invoking message.

        See [niobot.NioBot.send_message][] for more information. You do not need to provide the room.
        """
        kwargs.setdefault("reply_to", self._response)
        return ContextualResponse(
            self.ctx,
            await self.ctx.client.send_message(self.ctx.room, *args, **kwargs),
        )

    async def edit(self, *args, **kwargs) -> typing_extensions.Self:
        """Edits the current response.

        See [niobot.NioBot.edit_message][] for more information. You do not need to provide the room or event_id.
        """
        self._response = await self.ctx.client.edit_message(self.ctx.room, self._response.event_id, *args, **kwargs)
        return self

    async def delete(self, reason: typing.Optional[str] = None) -> None:
        """Redacts the current response.

        :param reason: An optional reason for the redaction
        :return: None, as there will be no more response.
        """
        await self.ctx.client.delete_message(self.ctx.room, self._response.event_id, reason=reason)


class Context:
    """Event-based context for a command callback"""

    def __init__(
        self,
        _client: NioBot,
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
        command: Command,
        *,
        invoking_prefix: typing.Optional[str] = None,
        invoking_string: typing.Optional[str] = None,
    ):
        self._init_ts = time.time()
        self._client = _client
        self._room = room
        self._event = event
        self._command = command
        self.invoking_prefix = invoking_prefix
        self._invoking_string = invoking_string
        to_parse = event.body

        if invoking_string:
            try:
                to_parse = event.body[len(invoking_string) :]
            except IndexError:
                to_parse = ""
        self._args = ArgumentView(to_parse)
        self._args.parse_arguments()
        self._original_response = None

        # property aliases
        self.bot = self.client
        self.msg = self.event = self.message
        self.arguments = self.args

    def __repr__(self):
        return f"<Context room={self.room!r} event={self.event!r} command={self.command!r}>"

    def __eq__(self, other):
        if not isinstance(other, Context):
            return False
        return self.room == other.room and self.event == other.event and self.command == other.command

    @property
    def room(self) -> nio.MatrixRoom:
        """The room that the event was dispatched in"""
        return self._room

    @property
    def client(self) -> NioBot:
        """The current instance of the client"""
        return self._client

    @property
    def command(self) -> Command:
        """The current command being invoked"""
        return self._command

    @property
    def args(self) -> list[str]:
        """Each argument given to this command"""
        return self._args.arguments

    @property
    def message(self) -> nio.RoomMessageText:
        """The current message"""
        return self._event

    @property
    def original_response(self) -> typing.Optional[nio.RoomSendResponse]:
        """The result of Context.reply(), if it exists."""
        return self._original_response

    @property
    def latency(self) -> float:
        """Returns the current event's latency in milliseconds."""
        return self.client.latency(self.event, received_at=self._init_ts)

    async def respond(self, *args, **kwargs) -> ContextualResponse:
        """Responds to the current event.

        See [niobot.NioBot.send_message][] for more information.
        """
        kwargs.setdefault("reply_to", self.event)
        result = await self.client.send_message(self.room, *args, **kwargs)
        return ContextualResponse(self, result)
