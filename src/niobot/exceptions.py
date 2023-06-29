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

    Attributes:
        message: A simple humanised explanation of the issue, if available.
        response: The response object from the server, if available.
        exception: The exception that was raised, if available.
        original: The original response, or exception if response was not available.
    """
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

    def __str__(self):
        return self.message or str(self.original)

    def __repr__(self):
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
