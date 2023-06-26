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
    """
    def __init__(self, message: str = None, original: nio.ErrorResponse = None):
        self.original = original
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
