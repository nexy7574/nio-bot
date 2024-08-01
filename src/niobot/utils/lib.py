import functools
import warnings
import logging

__all__ = ("deprecated", "silence_noisy_loggers")


def deprecated(use_instead: str = None):
    """Marks a function as deprecated and will warn users on call."""

    def wrapper(func):
        @functools.wraps(func)
        def caller(*args, **kwargs):
            value = "{} is deprecated.{}".format(
                func.__qualname__, "" if not use_instead else " Please use %r instead." % use_instead
            )
            warn = DeprecationWarning(value)
            warnings.warn(warn)
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
