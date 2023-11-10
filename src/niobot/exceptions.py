import typing
import warnings

import nio

__all__ = (
    "NioBotException",
    "MessageException",
    "LoginException",
    "MediaException",
    "MediaUploadException",
    "MediaDownloadException",
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
    "InsufficientPower",
    "GenericMatrixError",
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

    message: typing.Optional[str]
    response: typing.Optional[nio.ErrorResponse]
    exception: typing.Optional[BaseException]
    original: typing.Union[nio.ErrorResponse, BaseException, None]

    def __init__(
        self,
        message: typing.Optional[str] = None,
        response: typing.Optional[nio.ErrorResponse] = None,
        *,
        exception: typing.Optional[BaseException] = None,
        original: typing.Optional[typing.Union[nio.ErrorResponse, BaseException]] = None,
    ):
        if original:
            warnings.warn(DeprecationWarning("original is deprecated, use response or exception instead"))
        self.original = original or response or exception
        self.response = response
        self.exception: typing.Optional[typing.Union[nio.ErrorResponse, BaseException]] = exception
        self.message = message

        if self.original is None and self.message is None:
            raise ValueError("If there is no error history, at least a human readable message should be provided.")

    def bottom_of_chain(
        self, other: typing.Optional[typing.Union[Exception, nio.ErrorResponse]] = None
    ) -> typing.Union[BaseException, nio.ErrorResponse]:
        """Recursively checks the `original` attribute of the exception until it reaches the bottom of the chain.

        This function finds you the absolute first exception that was raised.

        :param other: The other exception to recurse down. If None, defaults to the exception this method is called on.
        :returns: The bottom of the chain exception."""
        other = other or self
        if hasattr(other, "original") and other.original is not None:
            try:
                return self.bottom_of_chain(other.original)
            except RecursionError:  # what a deeply nested error??
                return other
        return other

    def __str__(self) -> str:
        """Returns a human-readable version of the exception."""
        return self.message or repr(self.original)

    def __repr__(self) -> str:
        """Returns a developer-readable version of the exception."""
        return f"<{self.__class__.__name__} message={self.message!r} original={self.original!r}>"


class GenericMatrixError(NioBotException):
    """
    Exception for generic matrix errors where a valid response was expected, but got an ErrorResponse instead.
    """

    def __init__(self, message: typing.Optional[str] = None, *, response: nio.ErrorResponse):
        super().__init__(message=message, response=response)


class MessageException(NioBotException):
    """
    Exception for message-related errors.
    """


class LoginException(NioBotException):
    """
    Exception for login-related errors.
    """


class MediaException(MessageException):
    """
    Exception for media-related errors.
    """


class MediaUploadException(MediaException):
    """
    Exception for media-uploading related errors
    """


class MediaDownloadException(MediaException):
    """
    Exception for media-downloading related errors
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


class MetadataDetectionException(MediaException):
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
        check_name: typing.Optional[str] = None,
        message: typing.Optional[str] = None,
        exception: typing.Optional[BaseException] = None,
    ):
        if not message:
            message = f"Check {check_name} failed."
        super().__init__(message, exception=exception)
        self.check_name = check_name

    def __str__(self) -> str:
        return self.message or f"Check {self.check_name} failed."

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} check_name={self.check_name!r} message={self.message!r}"
            f" exception={self.exception!r}>"
        )


class NotOwner(CheckFailure):
    """
    Exception raised when the command invoker is not the owner of the bot.
    """

    def __init__(
        self,
        check_name: typing.Optional[str] = None,
        message: typing.Optional[str] = None,
        exception: typing.Optional[BaseException] = None,
    ):
        if not message:
            message = "You are not the owner of this bot."
        super().__init__(check_name, message, exception)


class InsufficientPower(CheckFailure):
    """
    Exception raised when the command invoker does not have enough power to run the command.
    """

    def __init__(
        self,
        check_name: typing.Optional[str] = None,
        message: typing.Optional[str] = None,
        exception: typing.Optional[BaseException] = None,
        *,
        needed: int,
        have: int,
    ):
        if not message:
            message = "Insufficient power level. Needed %d, have %d." % (needed, have)
        super().__init__(check_name, message, exception)


class NotADirectRoom(CheckFailure):
    """
    Exception raised when the current room is not `m.direct` (a DM room)
    """

    def __init__(
        self,
        check_name: typing.Optional[str] = None,
        message: typing.Optional[str] = None,
        exception: typing.Optional[BaseException] = None,
    ):
        if not message:
            message = "This command can only be run in a direct message room."
        super().__init__(check_name, message, exception)
