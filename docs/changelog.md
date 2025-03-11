# Changelog

## Unreleased

??? example "These changes are not in a stable release."
    You can only get these changes by installing the library from GitHub. This is not recommended in production, as these changes
    are often not properly battle-tested.

    However, if you encounter an issue with these changes, you should open an issue on GitHub so that we can release them sooner!

!!! danger "Potentially breaking changes since the last release"
    The following changes may be potentially breaking if you use some lower-level features of the library:

    * Attachments have been massively reworked, please check your code to see if there are any intellisense errors, or if you are using any of the removed methods.
    * Argument detection has been massively reworked - while it should be a massive improvement, please check to make sure your arguments are still parsed as expected.
    * The sync store has been completely rewritten - any code previously using helper functions will likely break.

* Added the sync filter "lazy load members" - should hopefully improve performance in large rooms.
* Removed temporary lock on `niobot.NioBot.process_message`, which should allow parallel command execution again.
* Removed faulty fallback reply parser, it is no-longer needed. Clients should not be sending fallback replies anymore.
* Overhauled argument parsing
  * `*args` no longer works - please use `list[str]` (`typing.List[str]` on python 3.9) instead.
  * Arguments are no-longer given `None` (I am not sure what even caused this, but it's fixed now)
  * Greedy arguments are now correctly greedy.
  * Extra arguments passed to commands once again correctly raise an error.
  * Added support for `list[TYPE]`
* Added python 3.13 to the CI matrix
* Updated the pre-commit hooks (they were ANCIENT)
* Set `__license__` in `__init__.py` to `LGPLv3` (it was previously still `GPLv3`)
* Completely overhauled how attachments are handled
  * the monolithic `niobot.attachments` module has been split into its own package
  * `detect_mime_type` no-longer requires `magic` to be installed (but still REALLY prefers it, and will be noisy if it's not)
  * `niobot.AudioAttachment` is now located in `niobot/attachments/audio.py`
  * `niobot.VideoAttachment` is now located in `niobot/attachments/video.py`
  * `niobot.ImageAttachment` is now located in `niobot/attachments/image.py`
  * `niobot.FileAttachment` is now located in `niobot/attachments/file.py`
  * The extensible `niobot.BaseAttachment` is now located in `niobot/attachments/base.py`
* Added task names to the asyncio background tasks for commands dispatched by the bot using the format:
`COMMAND_{event.sender}_{room.room_id}_{command.name}_{monotonic_nanoseconds}`. This allows you to see what tasks are
running by calling `asyncio.all_tasks()`, and means you can precisely cancel running commands.
* Fixed [niobot.NioBot.add_event_listener][] not accepting `nio.Event` types, again.
* Fixed [niobot.NioBot.remove_event_listener][] not accepting `nio.Event` types.
* Added [niobot.NioBot.wait_for_event][], a generic evolution of [niobot.NioBot.wait_for_message][].
* Removed `niobot.NioBot._recursively_upload_attachments`, attachments should now properly be uploaded by the
`send_message` function.
* Remove the archaic deprecated behaviour that permitted non-[niobot.Parser][] objects to be used as parsers in commands.
* As mentioned above, overhauled argument parsing, in the process making [niobot.Argument.autodetect_args][]
less complex and more reliable.
* Fixed `repr(ContextualResponse)` raising an AttributeError
* Fixed [niobot.ContextualResponse][] being broken after [niobot.ContextualResponse.edit][] was called.
* Added `NIOBOT_DEPRECATION_ERROR` environment variable, which when set, causes deprecation warnings to become
errors instead. Intended for CI testing, but useful for local development too.
* Fixed [niobot.NioBot.get_account_data][] and [niobot.NioBot.set_account_data][] not working
  ([#40](https://github.com/nexy7574/nio-bot/issues/40))
* Added `process_message_edits` argument to [niobot.NioBot][], enabled by default, which will treat edited messages as
  new messages when checking for commands (meaning editing a message to invoke a command will invoke that command).
* Added [niobot.SimpleNioBot][] as a simplified version of [niobot.NioBot][].
* Fixed a bug that caused thumbnail bodies to duplicate
* Removed the storage of left rooms in the sync store (has DRASTICALLY sped up startup times)
* Duplicate events (compared via event ID and body) are no longer added to the sync store (reducing space taken)
* Limited the number of timeline events that are stored in the sync store
* Added SQL indexes for the sync store
* Limited the sync payload to only include 100 timeline & state events per room
* Implemented [niobot.NioBot.global_command_check][] to allow for global command checks
* Added [niobot.utils.HTMLTable][] to help with generating tables in HTML and plaintext
* Fixed incremental syncs having a hard timeout of 30 seconds, disrespecting the configured timeout
* Fixed filter uploads on startup not being fatal (later causing an exception)
* Fixed file uploads not respecting room encryption
* Fixed command argument detection not working with py 3.10 type syntaxes, and greedy not being detected correctly
* Removed python 3.9 from the testing matrix (and consequently support)
* Rewrote the sync store to actually store state rather than just sync payloads
* `user_id` and `device_id` are both fetched from the access token on startup. As a result, you can no-longer
accidentally specify the incorrect user ID or device ID.
* Removed the option to specify a custom device ID in `niocli get-access-token`

## v1.2.0

There are a lot of changes in v1.2.0, so in this release you'll see a lot of performance improvements and some fancy new features for you to
take advantage of!

!!! danger "Major update"
    This release has had a lot of changes in it since v1.1.0, so please make sure you test your bot when updating to make sure that everything still works.
    If you encounter an error you believe is due to broken backwards compatiblity, please open an issue on GitHub so that we can
    patch it.

### Added

* Allowed `command_prefix` to be an iterable, converting single-strings into a single-item iterable too.
* Added beautifulsoup4 as a hard dependency. Backwards compatibility is still kept in case bs4 is not installed.
* Added support for passing raw [`nio.Event`][nio.events.room_events.Event] types to event listeners
* Added proper support for [`typing.Optional`][] in automatic argument detection
* Added support for `*args` in automatic argument detection
* Added [`niobot.utils.Mentions`][] to handle intentional mentions in messages
* Added [`Command.can_run(ctx)`][niobot.Command.can_run], which runs through and makes sure that all of the command checks pass.
* Added backwards compatibility support for legacy media endpoints (servers that don't support matrix v1.11 yet). Authenticated media will still be used by default.
* Python 3.13 is now supported
* niobot attachment types now support os.PathLike, as well as str, BytesIO, and Pathlib, in case you had some freaky custom path type
* [`niobot.NioBot`][] now allows you to pass a static presence (`online`, `unavailable`, `offline`), `False` to outright disable presence, and `None` (default) to set it automatically based on the startup stage (recommended for slower connections)
* You can now, if you needed to for some reason, disable full state sync via `sync_full_state=False`.
* Added the `reason` parameter to [`niobot.NioBot.join`][] and [`niobot.NioBot.room_leave`][] as optional strings
* NioBot's auto-join feature now includes a reason when automatically joining rooms
* Added `force_initial_sync` to [`niobot.NioBot`][], which will force the bot to sync all rooms before starting the event loop.
* Added a real sync store (**huge** optimisation, especially for larger accounts)

### Changes

* Changed the event type of the `message` event to be any [nio.RoomMessage][nio.events.room_events.RoomMessage], not just `Text`.
* Merged `xyzamorganblurhash` into [`ImageAttachment`][niobot.ImageAttachment]
* (Typing) send_message can now reply to any [RoomMessage][nio.events.room_events.RoomMessage], not just [RoomMessageText][nio.events.room_events.RoomMessageText].
* [niobot.NioBot.start][] will now query `/_matrix/client/versions` to fetch server version metadata.
* Updated the documentation index page and added documentation for Mentions
* Unified all of the help functions into a single class, [`niobot.utils.help_command.DefaultHelpCommand`][], to make subclassing easier.
* `default_help_command` was replaced with [`DefaultHelpCommand().respond`][niobot.utils.help_command.DefaultHelpCommand.respond].
* Help command will no longer display commands in the command list that the current user cannot run
* [`niobot.NioBot.send_message`][] will now automatically parse mentions if not explicitly provided, to take full advantage of intentional mentions.

### Removed

* Removed `force_write` properly
* Removed deprecated `automatic_markdown_parser` option and functionality in NioBot
* Removed the deprecated `name` parameter from niobot checks
* `niobot.util.help_command.help_command_callback` was removed, in line with deprecation.
* Removed the password login critical log in favour of simply documenting the dangers of using a password
* Removed fallback replies in messages (see: [MSC2781](https://github.com/matrix-org/matrix-spec-proposals/pull/2781))
* Removed the legacy function-based argument parsers in favour of the class-based system

### Bug fixes

* Fix `<instance> has no attribute 'mro'` error when initialising auto-detected arguments
* Fixed `niocli get-access-token` crashing on windows
* Fixed `NioBot` throwing a warning about failing key uploads without logging the actual error
* Fixed [`niobot.utils.parsers.EventParser`][] raising an error when used
* Fixed some typing dotted around the client
* Fixed niobot attachments (Image/Video/Audio) sending `null` for metadata, which may cause incorrect client behaviours
* Fix RuntimeError due to concurrent typing in send_message
* Fixed the versioned docs deployment
* Overlapping typing events in anything using room_send (e.g. send_message, edit_message) will no-longer
throw an error if there is a mid-air collision. Instead, a warning will be logged to the stream, and
the operation will be a no-op. This may cause some inconsistencies in the typing indicators sent by nio-bot,
however that is preferrable to errors.
* Fixed [`niobot.NioBot.join`][] throwing a JSON EOF in some cases
* Fixed module event handlers, in debug logs, being named as anonymous functions, rather than their true names. This will make debugging issues with your event handlers easier.
* DM rooms are now removed properly from account data when leaving.
* Fixed [niobot.NioBot.on_event][] not properly accepting raw [nio.Event][nio.events.room_events.Event] types
* Fixed some faulty sync responses triggering commands twice
* Fixed a bug in the default help command that would display hidden commands regardless.

## v1.1.1 (2024-06-26)

* Heavy CI improvements (2024-05-08 -> 2024-06-15)
* Deprecated unimplemented `force_write` parameter in some `BaseAttachment` (and subclass) methods. (2024-06-15)

## v1.1.0.post3 (2024-04-16)

### New features

* Added `CHANGELOG.md` (and consequently, this page) to documentation. (2024-02-08)
* `NioBot._get_id` now tells you what object it couldn't identify in the raised exception. (2024-02-11)
* `NioBot.mount_module` now warns you if you define a custom `setup()` that doesn't update the command or event register. (2024-02-11)

## v1.1.0.post2 (2024-02-08)

### New features

* Added `auto_read_messages` key word argument to `NioBot` to automatically read messages from rooms. Defaults to `True`.
Disabling this (`False`) will prevent read reciepts from automatically being sent.

### Bug fixes

* Fixed `NioBot.get_dm_rooms` raising a 401 Unauthorised error regardless of any state.
* Fixed `NioBot.get_dm_rooms` raising a `GenericMatrixError` whenever there were no DM rooms, instead of gracefully returning an empty object.
* Fixed `NioBot.get_dm_rooms` using outdated code from before `matrix-nio==0.24.0`.

## v1.1.0 (2024-01-30)

!!! danger "The license changed in this release."
    With release v1.1.0 (specifically commit [421414d](https://github.com/nexy7574/nio-bot/commit/421414d)), the license for nio-bot was
    changed from GPLv3 to LGPLv3. In short, this means you do not have to open source your code, and you are able to commercialise your project
    if you use nio-bot.

??? note "This version's changelog includes changes made in its pre-release versions"
    This changelog includes all changes made since the last stable release, including those made in pre-release versions.
    If you scroll down, you will see duplicate feature changelogs where the feature was changed in a pre-release version.

### New features

* Added `niobot.Context.invoking_prefix`.
* Python 3.12 is now supported.
* Added `niobot.NioBot.is_ready`, which is an `asyncio.Event`.
* Added command-level checks (`@niobot.check`)
* Added sparse DM room support.
* Added additional exception types, such as `GenericMatrixError`.
* Additional type-hinting for the entire library.

### Changes

* License changed from `GPLv3` to `LGPLv3`.
* Improved existing type-hinting.
* `event_id` is prioritised over `room_id` in `niobot.NioBot._get_id`.
* `niobot` was changed to `nio-bot` (for consistency) throughout documentation and the pip installation guide.

## v1.1.0b1.post1 (and v1.1.0b1) (2023-10-16)

### New features

* Added CI testing to the library.
* Rewrote argument parsers to use a class-based ABC system, rather than a function-based system. See [documentation](guides/004-creating-custom-parsers.md).
* Added the `ignore_self` flag to `niobot.NioBot`, allowing you to choose whether the client will ignore its own messages.
* Added support for `typing.Annotated` in commands.

### Deprecations & Removals

* The property `niobot.Module.log` was fully removed - it was never fully functional and often tripped up users as it was unsettable.
* The property `niobot.Module.client` was deprecated - you should use `niobot.Module.client` instead.

## v1.1.0a3 (2023-10-06)

### Changes

* Prioritise `event_id` over `room_id` for the `_get_id` function
* Add `Context.invoking_prefix`
* Type hinting and code refactor

## v1.1.0a2 (2023-08-21)

### New features

* Backported support to Python 3.9 and Python 3.10.

### Bug fixes

* Fixed a bug where disabled commands could crash the command parser.

### Documentation changes

* Replaced `niobot` with `nio-bot` for pip install guide.
* Fixed PyPi link in README.
* Cleaned up documentation issues.
* Removed the examples on GitHub (until the package is more stable in terms of design).

## v1.1.0a1 (2023-07-31)

### New features

* Added documentation for events.
* Added `niobot.attachments.which` function.
* Added very early DM room support.
* Added easier ways to customise the help command.
* Added more specific exception types.
* Added `event_parser` and `room_parser`

### Changes

* `force_await` now just awaits coroutines rather than casting them to a task
* Command arguments now properly raise the correct errors

## v1.0.2 (2023-07-16)

!!! bug "This is an urgent security release - denial of service vulnerability."
    This release fixes a vulnerability where a potentially accidentally crafted message payload could cause the bot to completely crash.
    If you had disabled ignoring old messages, this could cause a crash loop if your bot automatically restarted.

    If you cannot update to v1.0.2 from a previous release, you should implement the following workaround:

    ```python
    import niobot


    class PatchedClient(niobot.NioBot):
        async def process_message(self, *args):
            try:
                await super().process_message(*args)
            except IndexError:  # IndexError is the only error thrown during parsing
                pass  # or print, whatever

    # bot = niobot.NioBot(...)
    bot = PatchedClient(...)  # use your patched version
    ```

### New features

* Added `niobot.attachments.get_image_metadata` (depends on `imagemagick`)
* `niocli version` now shows the OS and CPU architecture.
* `niobot.attachment.*` now always imports all attachment types into the `niobot` namespace, regardless of installed external dependencies.

### Bug fixes

* Fixed `niobot.ImageAttachment` being unable to detect image streams.
* Fixed `niobot.BaseAttachment` setting incorrect file properties
* `niobot.ImageAttachment` no longer explicitly fails upon encountering an unknown format, it simply emits a warning, in line with `niobot.VideoAttachment`.
* Fixed an unexpected input causing the entire process to crash.

## v1.0.1 (2023-07-12)

* Added stub `setup.py` for really old pip versions.
* Updated the README.

## v1.0.0 (2023-07-12)

The first stable release! This version has many breaking changes since v0.1.0, and as such is not very backwards compatible.

* `MediaAttachment` and `Thumbnail` were split up into `ImageAttachment`, `VideoAttachment`, `AudioAttachment`, and `FileAttachment`.
* Attachments now automatically detect metadata.
* Thumbnailing was massively improved.
* Blurhashes are automatically generated for images.
* Attachments now fully support end-to-end encryption.
* Attachments will now emit warnings when a non web-safe codec is used.
* Automatic command parameter parsing, so you no longer have to manually specify `Command(arguments=[...])`.
* Automatic help command sanitisation.
* Added additional requirements.
* Added the ability to add and remove reactions.
* Added `__repr__` to most objects in the library.
* Added more helper/utility functions.
* Added documentation (tada!).
* Added more customisation options to `niobot.NioBot`.

-----

You've reached the end! There are no previously documented releases before the big 1.0.0.
If you want to expand this list, you can contribute on GitHub! Open issues, or even better, make some pull requests.
We love new contributors!
