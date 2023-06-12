import nio
import marko

from .attachment import MediaAttachment
from .exceptions import MessageException
from .utils import run_blocking


class NioBot(nio.AsyncClient):
    """
    The main client for NioBot.
    """
    def __init__(
            self,
            homeserver: str,
    ):
        super().__init__(homeserver)

        self._commands = {}

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
    ) -> nio.RoomSendResponse:
        """
        Sends a message.

        :param room: The room to send this message to
        :param content: The content to send. Cannot be used with file.
        :param file: A file to send, if any. Cannot be used with content.
        :param reply_to: A message to reply to.
        :return: The response from the server.
        :raises MessageException: If the message fails to send, or if the file fails to upload.
        :raises ValueError: You specified both file and content, or neither.
        """
        if all((content, file)):
            raise ValueError("You cannot specify both content and file.")
        elif not any((content, file)):
            raise ValueError("You must specify either content or file.")

        body = {
            "msgtype": "m.text",
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

        response = await self.room_send(
            room.room_id,
            "m.room.message",
            body,
        )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to send message.", response)
        return response

    async def edit_message(
            self,
            room: nio.MatrixRoom,
            message: nio.RoomMessageText,
            content: str
    ):
        """
        Edit an existing message. You must be the sender of the message.

        You also cannot edit messages that are attachments.

        :param room: The room the message is in.
        :param message: The message to edit.
        :param content: The new content of the message.
        :raises RuntimeError: If you are not the sender of the message.
        :raises TypeError: If the message is not text.
        """
        if message.sender != self.user_id:
            raise RuntimeError("You cannot edit a message you did not send.")

        if not isinstance(message, nio.RoomMessageText):
            raise TypeError("You cannot edit a non-text message.")

        content = {
            "msgtype": "m.text",
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
                "event_id": message.event_id,
            },
            "format": "org.matrix.custom.html",
            "formatted_body": content["formatted_body"]
        }
        response = await self.room_send(
            room.room_id,
            "m.room.message",
            body,
        )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to edit message.", response)
        return response

    async def delete_message(self, room: nio.MatrixRoom, message: nio.RoomMessage, reason: str = None):
        """
        Delete an existing message. You must be the sender of the message.

        :param room: The room the message is in.
        :param message: The message to delete.
        :param reason: The reason for deleting the message.
        :raises RuntimeError: If you are not the sender of the message.
        """
        # TODO: Check power level
        if message.sender != self.user_id:
            raise RuntimeError("You cannot delete a message you did not send.")

        body = {
            "reason": reason,
            "m.relates_to": {
                "rel_type": "m.replace",
                "event_id": message.event_id,
            },
        }
        response = await self.room_send(
            room.room_id,
            "m.room.redaction",
            body,
        )
        if isinstance(response, nio.RoomSendError):
            raise MessageException("Failed to delete message.", response)
        return response
