import logging
import time
import typing

import nio

from .utils.string_view import ArgumentView

if typing.TYPE_CHECKING:
    from .attachment import BaseAttachment
    from .client import NioBot
    from .commands import Command


__all__ = ("Context", "ContextualResponse")

logger = logging.getLogger(__name__)


class ContextualResponse:
    """Context class for managing replies.

    Usage of this function is not required, however it is a useful utility."""

    def __init__(self, ctx: "Context", response: nio.RoomSendResponse):
        self.ctx = ctx
        self._response = response

    def __repr__(self):
        return "<ContextualResponse ctx={0.ctx!r} response={0.response!r}>".format(self)

    @property
    def message(self) -> typing.Optional[nio.RoomMessageText]:
        """Fetches the current message for this response"""
        result = self.ctx.client.get_cached_message(self._response.event_id)
        if result:
            return result[1]
        else:
            logger.warning("Original response for context %r was not found in cache, unable to modify.", self.ctx)

    async def reply(self, *args) -> "ContextualResponse":
        """
        Replies to the current response.

        This does NOT reply to the original invoking message.

        :param args: args to pass to send_message
        :return: a new ContextualResponse object.
        """

        return ContextualResponse(
            self.ctx, await self.ctx.client.send_message(self.ctx.room, *args, reply_to=self._response.event_id)
        )

    async def edit(self, content: str, **kwargs) -> "ContextualResponse":
        """
        Edits the current response.

        :param content: The new content to edit with
        :param kwargs: Any extra arguments to pass to Client.edit_message
        :return: self
        """
        await self.ctx.client.edit_message(self.ctx.room, self._response.event_id, content, **kwargs)
        return self

    async def delete(self, reason: typing.Optional[str] = None) -> None:
        """
        Redacts the current response.

        :param reason: An optional reason for the redaction
        :return: None, as there will be no more response.
        """
        await self.ctx.client.delete_message(self.ctx.room, self._response.event_id, reason=reason)


class Context:
    """Event-based context for a command callback"""

    def __init__(
        self,
        _client: "NioBot",
        room: nio.MatrixRoom,
        event: nio.RoomMessageText,
        command: "Command",
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
        return "<Context room={0.room!r} event={0.event!r} command={0.command!r}>".format(self)

    def __eq__(self, other):
        if not isinstance(other, Context):
            return False
        return self.room == other.room and self.event == other.event and self.command == other.command

    @property
    def room(self) -> nio.MatrixRoom:
        """The room that the event was dispatched in"""
        return self._room

    @property
    def client(self) -> "NioBot":
        """The current instance of the client"""
        return self._client

    @property
    def command(self) -> "Command":
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

    async def respond(
        self, content: typing.Optional[str] = None, file: typing.Optional["BaseAttachment"] = None
    ) -> ContextualResponse:
        """
        Responds to the current event.

        :param content: The text to reply with
        :param file: A file to reply with
        :return:
        """
        result = await self.client.send_message(self.room, content, file, self.message)
        return ContextualResponse(self, result)
