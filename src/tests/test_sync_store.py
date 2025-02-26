import json
import os
import pathlib
import sys
import tempfile
import time

import nio
import pytest

import niobot

# from .. import niobot


SYNC_FILE_DIR = pathlib.Path(__file__).parent / "assets/syncs"
SYNC_FILES = [
    SYNC_FILE_DIR / "00.json",
    SYNC_FILE_DIR / "01.json",
    SYNC_FILE_DIR / "02.json",
]


@pytest.mark.asyncio
async def test_sync_store():
    delete = os.getenv("NIOBOT_CI_PERSIST_STORE", "0") != "1"
    with tempfile.TemporaryDirectory(prefix="niobot-ci-", delete=delete) as store_dir:
        if delete is False:
            print("Sync store directory:", store_dir, file=sys.stderr)
        client = niobot.NioBot(
            "https://matrix.example",
            "@niobot-test:nexy7574.co.uk",
            store_path=store_dir,
            command_prefix="!",
        )
        async with client.sync_store as sync_manager:
            for file in SYNC_FILES:
                parsed = json.loads(file.read_text())
                sync = niobot.SyncResponse.from_dict(parsed)
                assert isinstance(sync, niobot.SyncResponse), "Failed to parse test data: %r" % sync
                await sync_manager.handle_sync(sync)
                assert await sync_manager.get_next_batch() == sync.next_batch
                await sync_manager.commit()

            replay = await sync_manager.generate_sync()
            assert isinstance(replay, nio.SyncResponse), "Failed to generate replay sync: %r" % replay
            assert replay.next_batch == "42219939"
            client.access_token = "fake"
            client.start_time = time.time()
            await client._handle_sync(replay)
            assert await sync_manager.get_next_batch() == "42219939"
            assert len(client.rooms) == 2

        # Teardown
        # await client.close()
