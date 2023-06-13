import nio


__all__ = (
    "NioBotException",
    "MessageException",
    "LoginException",
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
        return f"<{self.__class__.__name__}: {self}>"


class MessageException(NioBotException):
    """
    Exception for message-related errors.
    """


class LoginException(NioBotException):
    """
    Exception for login-related errors.
    """
