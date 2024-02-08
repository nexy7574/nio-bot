import pytest

from niobot.utils import unblocking


async def fake_coro(return_value=1):
    return return_value


def fake_sync(return_value=2):
    return return_value


@pytest.mark.parametrize(
    "function, kwargs, expected, _raise",
    [
        (fake_coro, {"return_value": 5}, 5, TypeError),
        (fake_sync, {"return_value": 6}, 6, None),
        (fake_coro, {}, 1, TypeError),
        (fake_sync, {}, 2, None),
    ],
)
@pytest.mark.asyncio
async def test_run_blocking(function, kwargs, expected, _raise):
    non_coro = unblocking.run_blocking(function, **kwargs)
    if _raise is not None:
        with pytest.raises(_raise):
            await non_coro
    else:
        assert (await non_coro) == expected, "Unexpected result: %r != %r" % (non_coro, expected)


@pytest.mark.parametrize(
    "function, kwargs, expected",
    [
        (fake_coro, {"return_value": 5}, 5),
        (fake_sync, {"return_value": 6}, 6),
        (fake_coro, {}, 1),
        (fake_sync, {}, 2),
    ],
)
@pytest.mark.asyncio
async def test_force_await(function, kwargs, expected):
    non_coro = unblocking.force_await(function, **kwargs)
    assert (await non_coro) == expected, "Unexpected result: %r != %r" % (non_coro, expected)
