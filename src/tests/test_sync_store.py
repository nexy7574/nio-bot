import json
import tempfile

import nio
import pytest
import pathlib
import niobot
# from .. import niobot


SYNC_FILE_DIR = pathlib.Path(__file__).parent / "assets/syncs"
SYNC_FILES = [
    SYNC_FILE_DIR / "00.json",
    SYNC_FILE_DIR / "01.json",
    SYNC_FILE_DIR / "02.json",
]


@pytest.mark.parametrize("resolve_state", [True, False])
@pytest.mark.asyncio
async def test_sync_store(resolve_state):
    with tempfile.TemporaryDirectory() as store_dir:
        client = niobot.NioBot(
            "https://matrix.example", "@example:matrix.example", store_path=store_dir, command_prefix="!"
        )
        sync_manager = niobot.SyncStore(client, store_dir + "/sync.db", resolve_state=resolve_state)
        for file in SYNC_FILES:
            parsed = json.loads(file.read_text())
            sync = niobot.SyncResponse.from_dict(parsed)
            assert isinstance(sync, niobot.SyncResponse), "Failed to parse test data: %r" % sync
            await sync_manager.handle_sync(sync)
            await sync_manager.commit()

        replay = await sync_manager.generate_sync()
        assert isinstance(replay, nio.SyncResponse), "Failed to generate replay sync: %r" % replay
        await client._handle_sync(replay)

        assert await sync_manager.get_next_batch("@example:matrix.example") == "42219939"
        assert len(client.rooms) == 2
