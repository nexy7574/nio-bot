import typing
import warnings

import nio


__all__ = (
    "NioBotException",
    "MessageException",
    "LoginException",
    "MediaUploadException",
    "MediaCodecWarning",
    "MetadataDetectionException",
    "CommandError",
    "CommandParserError",
    "CommandPreparationError",
    "CommandDisabledError",
    "CommandNotFoundError",
    "CommandArgumentsError",
    "CheckFailure",
    "NotOwner",
    "InsufficientPower"
)


class NioBotException(Exception):
    """
    Base exception for NioBot.

    !!! warning
        In some rare cases, all of `exception`, `response` and `original` may be None.

    All other exceptions raised by this library will subclass this exception, so at least all the below are
    always available:

    :var message: A simple humanised explanation of the issue, if available.
    :var response: The response object from the server, if available.
    :var exception: The exception that was raised, if available.
    :var original: The original response, or exception if response was not available.
    """
    message: str | None
    response: nio.ErrorResponse | None
    exception: BaseException | None
    original: nio.ErrorResponse | BaseException | None

    def __init__(
            self,
            message: str = None,
            response: nio.ErrorResponse = None,
            *,
            exception: BaseException = None,
            original: typing.Union[nio.ErrorResponse, BaseException] = None,
    ):
        if original:
            warnings.warn(DeprecationWarning("original is deprecated, use response or exception instead"))
        self.original = original or response or exception
        self.response = response
        self.exception: typing.Union[nio.ErrorResponse, BaseException] = exception
        self.message = message

        if self.original is None and self.message is None:
            raise ValueError("If there is no error history, at least a human readable message should be provided.")

    def __str__(self) -> str:
        """Returns a human-readable version of the exception."""
        return self.message or str(self.original)

    def __repr__(self) -> str:
        """Returns a developer-readable version of the exception."""
        return f"<{self.__class__.__name__} message={self.message!r} original={self.original!r}>"


class MessageException(NioBotException):
    """
    Exception for message-related errors.
    """


class LoginException(NioBotException):
    """
    Exception for login-related errors.
    """


class MediaUploadException(MessageException):
    """
    Exception for media-uploading related errors
    """


class MediaCodecWarning(ResourceWarning):
    """
    Warning that is dispatched when a media file is not in a supported codec.

    You can filter this warning by using `warnings.filterwarnings("ignore", category=niobot.MediaCodecWarning)`

    Often times, matrix clients are web-based, so they're limited to what the browser can display.
    This is usually:

    * h264/vp8/vp9/av1/theora video
    * aac/opus/vorbis/mp3/pcm_* audio
    * jpg/png/webp/avif/gif images
    """
    def __init__(self, codec: str, *supported: str):
        super().__init__(
            f"Codec {codec} is not supported by most clients. Use with caution.\n"
            f"Suggested codecs: {', '.join(supported)}"
        )


class MetadataDetectionException(MediaUploadException):
    """
    Exception raised when metadata detection fails. Most of the time, this is an ffmpeg-related error
    """


class CommandError(NioBotException):
    """
    Exception subclass for all command invocation related errors.
    """


class CommandNotFoundError(CommandError):
    """
    Exception raised when a command is not found.
    """
    def __init__(self, command_name: str):
        super().__init__(f"Command {command_name} not found")
        self.command_name = command_name


class CommandPreparationError(CommandError):
    """
    Exception subclass for errors raised while preparing a command for execution.
    """


class CommandDisabledError(CommandPreparationError):
    """
    Exception raised when a command is disabled.
    """
    def __init__(self, command):
        super().__init__(f"Command {command} is disabled")


class CommandArgumentsError(CommandPreparationError):
    """
    Exception subclass for command argument related errors.
    """


class CommandParserError(CommandArgumentsError):
    """
    Exception raised when there is an error parsing arguments.
    """


class CheckFailure(CommandPreparationError):
    """
    Exception raised when a generic check call fails.

    You should prefer one of the subclass errors over this generic one, or a custom subclass.

    `CheckFailure` is often raised by the built-in checker when a check returns a falsy value without raising an error.
    """
    def __init__(
            self,
            check_name: str = None,
            message: str = None,
            exception: BaseException = None,
    ):
        if not message:
            message = f"Check {check_name} failed."
        super().__init__(message, exception=exception)
        self.check_name = check_name

    def __str__(self) -> str:
        return self.message or f"Check {self.check_name} failed."

    def __repr__(self):
        return f"<{self.__class__.__name__} check_name={self.check_name!r} message={self.message!r}" \
               f" exception={self.exception!r}>"


class NotOwner(CheckFailure):
    """
    Exception raised when the command invoker is not the owner of the bot.
    """
    def __init__(self, check_name: str = None, message: str = None, exception: BaseException = None):
        if not message:
            message = "You are not the owner of this bot."
        super().__init__(check_name, message, exception)


class InsufficientPower(CheckFailure):
    """
    Exception raised when the command invoker does not have enough power to run the command.
    """
    def __init__(
            self,
            check_name: str = None,
            message: str = None,
            exception: BaseException = None,
            *,
            needed: int,
            have: int
    ):
        if not message:
            message = "Insufficient power level. Needed %d, have %d." % (needed, have)
        super().__init__(check_name, message, exception)


class NotADirectRoom(CheckFailure):
    """
    Exception raised when the current room is not `m.direct` (a DM room)
    """
    def __init__(self, check_name: str = None, message: str = None, exception: BaseException = None):
        if not message:
            message = "This command can only be run in a direct message room."
        super().__init__(check_name, message, exception)
