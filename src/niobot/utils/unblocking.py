import asyncio
import functools
import inspect
import typing
from collections.abc import Callable
from typing import Any

__all__ = ("run_blocking", "force_await")

T = typing.TypeVar("T")


async def run_blocking(function: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Takes a blocking function and runs it in a thread, returning the result.

    You should use this for any long-running functions that may take a long time to respond that are not coroutines
    that you can await. For example, running a subprocess.

    ??? example
        ```py
        import asyncio
        import subprocess
        from niobot.utils import run_blocking

        async def main():
            result = await run_blocking(subprocess.run, ["find", "*.py", "-type", "f"], capture_output=True)
            print(result)

        asyncio.run(main())
        ```

    :param function: The function to call. Make sure you do not call it, just pass it.
    :param args: The arguments to pass to the function.
    :param kwargs: The keyword arguments to pass to the function.
    :returns: The result of the function.
    """
    if asyncio.iscoroutinefunction(function):
        raise TypeError("Cannot run a coroutine function in a thread.")
    obj = functools.partial(function, *args, **kwargs)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, obj)


async def force_await(function: typing.Union[typing.Callable, typing.Coroutine], *args: Any, **kwargs: Any):
    """
    Takes a function, and if it needs awaiting, it will be awaited.
    If it is a synchronous function, it runs it in the event loop, preventing it from blocking.

    This is equivalent to (pseudo):
    ```py
    if can_await(x):
        await x
    else:
        await run_blocking(x)
    ```

    :param function: The function to call. Make sure you do not call it, just pass it.
    :param args: The arguments to pass to the function.
    :param kwargs: The keyword arguments to pass to the function.
    :returns: The result of the function.
    """
    if asyncio.iscoroutinefunction(function):
        return await function(*args, **kwargs)
    elif inspect.isawaitable(function):
        return await function
    else:
        return await run_blocking(function, *args, **kwargs)
