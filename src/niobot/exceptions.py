import nio


__all__ = (
    "NioBotException",
    "MessageException"
)


class NioBotException(Exception):
    """
    Base exception for NioBot.
    """
    def __init__(self, message: str = None, original: nio.ErrorResponse):
        self.original = original


class MessageException(NioBotException):
    """
    Exception for message-related errors.
    """
