import typing
import warnings

import nio


__all__ = (
    "NioBotException",
    "MessageException",
    "LoginException",
    "MediaUploadException",
    "CommandError",
    "CommandDisabledError",
    "CommandArgumentsError"
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
    exception: Exception | None
    original: nio.ErrorResponse | Exception | None

    def __init__(
            self,
            message: str = None,
            response: nio.ErrorResponse = None,
            *,
            exception: Exception = None,
            original: typing.Union[nio.ErrorResponse, Exception] = None,
    ):
        if original:
            warnings.warn(DeprecationWarning("original is deprecated, use response or exception instead"))
        self.original = original or response or exception
        self.response = response
        self.exception: typing.Union[nio.ErrorResponse, Exception] = exception
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


class MediaUploadException(NioBotException):
    """
    Exception for media-uploading related errors
    """


class CommandError(NioBotException):
    """
    Exception subclass for all command invocation related errors.
    """


class CommandDisabledError(CommandError):
    """
    Exception raised when a command is disabled.
    """
    def __init__(self, command):
        super().__init__(f"Command {command} is disabled")


class CommandArgumentsError(CommandError):
    """
    Exception subclass for command argument related errors.
    """


class CommandParserError(CommandArgumentsError):
    """
    Exception raised when there is an error parsing arguments.
    """
