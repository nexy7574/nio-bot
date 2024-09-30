import functools
import logging
import re
import warnings
from types import FunctionType
from typing import Optional as O, Union as U

__all__ = ("deprecated", "silence_noisy_loggers", "MXID_REGEX")

MXID_REGEX = re.compile(r"@[a-z0-9._=\-/+]+:\S+")
# WARNING: this regex doe snot fully conform to the spec, nor do any validation.
# However, it will cover the majority of cases.
# Use `NioBot.parse_user_mentions` for more validation


try:
    from warnings import deprecated as _deprecated
    # Python 3.13 and above
except ImportError:
    _deprecated = None
    # Below python 3.13, we need to define our own deprecated decorator


def deprecated(use_instead: O[U[FunctionType, str]] = None):
    """Marks a function as deprecated and will warn users on call."""

    if use_instead is not None and not isinstance(use_instead, str):
        use_instead = use_instead.__qualname__

    def wrapper(func):
        @functools.wraps(func)
        def caller(*args, **kwargs):
            value = "{} is deprecated.{}".format(
                func.__qualname__, "" if not use_instead else " Please use %r instead." % use_instead
            )
            if not _deprecated:
                warnings.warn(
                    value,
                    category=DeprecationWarning,
                    stacklevel=2,
                )
            else:
                _deprecated(value)
            return func(*args, **kwargs)

        caller.__doc__ = func.__doc__
        return caller

    return wrapper


def silence_noisy_loggers(*exclude: str):
    """
    Silences noisy loggers so that debugging is easier, by setting their log levels to WARNING
    :param exclude: A list of loggers to exclude from silencing
    """
    silence = ["nio.rooms", "nio.crypto.log", "peewee", "nio.responses"]
    # niobot.client is pretty noisy, but given that its *us*, it'd be a bit counter-productive muting it
    for excl in exclude:
        silence.remove(excl)
    for logger in silence:
        logging.getLogger(logger).setLevel(logging.WARNING)
        logging.getLogger(logger).warning("Logger silenced to WARNING")
