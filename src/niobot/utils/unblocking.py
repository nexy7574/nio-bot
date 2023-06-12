import asyncio
import typing
import functools


__all__ = ("run_blocking",)


async def run_blocking(function: typing.Callable, *args, **kwargs):
    """
    Takes a blocking function and runs it in a thread, returning the result.

    You should use this for any long-running functions that may take a long time to respond that are not coroutines
    that you can await. For example, running a subprocess.
    """
    obj = functools.partial(function, *args, **kwargs)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, obj)
