import functools
import logging
import warnings

__all__ = ("deprecated", "silence_noisy_loggers")


try:
    from warnings import deprecated
    # Python 3.13 and above
except ImportError:
    # Below python 3.13, we need to define our own deprecated decorator
    def deprecated(use_instead: str = None):
        """Marks a function as deprecated and will warn users on call."""

        def wrapper(func):
            @functools.wraps(func)
            def caller(*args, **kwargs):
                value = "{} is deprecated.{}".format(
                    func.__qualname__, "" if not use_instead else " Please use %r instead." % use_instead
                )
                warnings.warn(
                    value,
                    category=DeprecationWarning,
                    stacklevel=2,
                )
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
