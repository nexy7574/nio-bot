# WARNING
# This is INSECURE
# This code will store your USER ACCESS TOKEN in PLAIN TEXT JSON.
# This means that if someone were to get access to the file, they would have full access to whatever account you're
# using with niobot. They would not need your password, and would have full control.
# Please consider alternative forms of storage, such as a database, or a more secure file format.

import nio  # remember, Nio is the underlying library that niobot uses.
import niobot
from pathlib import Path
import json

CREDENTIALS = Path("./credentials.json")
if CREDENTIALS.exists():
    print("Loading existing credentials...")
    with CREDENTIALS.open() as f:
        credentials = json.load(f)
    homeserver = credentials["homeserver"]
    user_id = credentials["user_id"]
    access_token = credentials["access_token"]
    password = None
else:
    import getpass
    access_token = None
    print("No existing credentials. Please enter:")
    homeserver = input("Homeserver URL: ")
    user_id = input("User ID: ")
    password = getpass.getpass("Password (no echo): ")

bot = niobot.NioBot(homeserver, user_id, command_prefix="$")


@bot.on_event("ready")
async def on_ready(first_sync_result: nio.SyncResponse):
    print("Logged in as %r!" % bot.user_id)
    print("Saving credentials...")
    creds = {
        "homeserver": homeserver,
        "user_id": user_id,
        "access_token": bot.access_token
    }
    with CREDENTIALS.open("w") as file:
        json.dump(creds, file)
    print("Dumped!")

bot.run(access_token=access_token, password=password)
# If password is None, it will use access_token, and vice versa.
