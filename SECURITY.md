# Security Policy

## Supported Versions

All versions under the current and previous major release are supported for security updates. If a version is tagged with ESR, it will be supported for at least 5 more major releases.

## Reporting a Vulnerability

You should first attempt to contact a maintainer ([@nex:nexy7574.co.uk](https://matrix.to/#/@nex:nexy7574.co.uk)) directly on matrix, reporting as much detail on the vulnerability and how it affects users
of the library.
Should you not get a reply within a couple of days, you should open a pull request (without an issue) with a fix or at least a workaround, ensuring the vulnerability is 100% no-longer present in your fork
***before*** opening the pull request.

## How vulnerabilities are handled

Vulnerability reports are handled with the utmost urgency, and patches are usually released within a couple hours after discovery (where applicable).
However, patches are not applied linearly. Only the major releases affected by the vulnerability will get a patch bump, not individual minor releases.

This means that if a vulnerability was found in `v5.6.0`, and it affected `v5.2.7` too, only `v5.6.1` would be released. If it affected previous major releases, only their most recent `minor`
release would get a patch, so in this example, `v4.7.13` would be patched to `v4.7.14`, but `v4.6.3` would remain `v4.6.3`.
This is because breaking changes are only supposed to be released in major changes - 9 times out of 10, upgrading the minor version *shouldn't* cause any breaks in existing code, so making
patches for each individual version just a waste of effort.

### Releases

Patched releases will then be uploaded to their own [GitHub releases](//github.com/nexy7574/niobot/releases), which then propagates to
[PyPi](https://pypi.org/project/nio-bot). Security releases will be *tagged* with `[URGENT] v<version>`, for example, `[URGENT] v4.7.13`. This means that anyone who happens to visit
the github page will see that there's a new urgent release, and will upgrade.

### Disclosure

Disclosure of the vulnerability will only be done after it has been patched and said patch has been released. Users who reported and/or helped to fix the vulnerability will be mentioned in the
github releases, and an @room announcement will go out in the [support room](https://matrix.to/#/#niobot:nexy7574.co.uk).
