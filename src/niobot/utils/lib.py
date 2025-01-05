import functools
import inspect
import logging
import os
import re
import warnings
from types import FunctionType
from typing import Optional, Union, Callable, Any, TypeVar

__all__ = ("MXID_REGEX", "deprecated", "silence_noisy_loggers", "copy_signature")

MXID_REGEX = re.compile(r"@[a-z0-9._=\-/+]+:[\w\-.]+")
# WARNING: this regex does not fully conform to the spec, nor do any validation.
# However, it will cover the majority of cases.
# Use `NioBot.parse_user_mentions` for more validation
T = TypeVar("T")


try:
    from warnings import deprecated as _deprecated

    # Python 3.13 and above
except ImportError:
    # Below python 3.13, we need to define our own deprecated decorator
    def _deprecated(message: str):
        warnings.warn(message, category=DeprecationWarning, stacklevel=2)


def deprecated(
    use_instead: Union[FunctionType, str, None] = None,
    slated_for_removal: Optional[str] = None,
):
    """
    Marks a function as deprecated and will warn users on call.

    !!! tip "Force raise an error on call"
        You can force raise an error on call by setting the environment variable `NIOBOT_DEPRECATION_ERROR` to `1`.
        In this case, `RuntimeError` will be raised when the deprecated function is called. Otherwise,
        a `DeprecationWarning` will be issued.

    :param use_instead: The function literal or string name of the function that should be used instead.
    :param slated_for_removal: A version number indicating when the function will be removed.
    :returns: A decorator that will mark the function as deprecated.
    """
    # NOTE: This function will use the python builtin warnings.deprecation if available, however, this was added in
    # python 3.13: https://docs.python.org/3/library/warnings.html#warnings.deprecated
    # See also: https://typing.readthedocs.io/en/latest/spec/directives.html#deprecated

    if use_instead is not None and not isinstance(use_instead, str):
        use_instead = use_instead.__qualname__

    def wrapper(func: T) -> T:
        @functools.wraps(func)
        def caller(*args, **kwargs):
            if use_instead:
                value = "{0} is deprecated. Please use {1} instead.".format(func.__qualname__, use_instead)
            else:
                value = "{} is deprecated.".format(
                    func.__qualname__,
                )

            if slated_for_removal:
                value += " This function is slated for removal in version %s." % slated_for_removal

            if os.getenv("NIOBOT_DEPRECATION_ERROR", "0") == "1":
                raise RuntimeError(value)

            _deprecated(value)
            return func(*args, **kwargs)

        return caller

    return wrapper


def silence_noisy_loggers(*exclude: str):
    """Silences noisy loggers so that debugging is easier, by setting their log levels to WARNING
    :param exclude: A list of loggers to exclude from silencing
    """
    silence = ["nio.rooms", "nio.crypto.log", "peewee", "nio.responses"]
    # niobot.client is pretty noisy, but given that its *us*, it'd be a bit counter-productive muting it
    for excl in exclude:
        silence.remove(excl)
    for logger in silence:
        logging.getLogger(logger).setLevel(logging.WARNING)
        logging.getLogger(logger).warning("Logger silenced to WARNING")


def copy_signature(original: Callable[..., Any]) -> Callable[[T], T]:
    """Copies the signature of a function to another function. This is similar to functools.wraps.

    This is useful for alias functions."""

    def wrapper(func: T) -> T:
        func.__doc__ = original.__doc__
        func.__signature__ = inspect.signature(original)
        return func

    return wrapper
