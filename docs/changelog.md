# Changelog

!!! note "This changelog is new"
    Previously, all changelogs were only available in the [GitHub releases](https://github.com/nexy7574/nio-bot/releases).
    Now, they will be additionally available in the documentation.

    However, as the changelog was only started in version v1.1.0.post2, the changelog for the previous versions will not be available here.

## v1.1.0.post2 (2023-02-08)

### Bug fixes

* Fixed `NioBot.get_dm_rooms` raising a 401 Unauthorised error regardless of any state.
* Fixed `NioBot.get_dm_rooms` raising a `GenericMatrixError` whenever there were no DM rooms, instead of gracefully returning an empty object.
* Fixed `NioBot.get_dm_rooms` using outdated code from before `matrix-nio==0.24.0`.

### New features

* Added `auto_read_messages` key word argument to `NioBot` to automatically read messages from rooms. Defaults to `True`.
Disabling this (`False`) will prevent read reciepts from automatically being sent.
