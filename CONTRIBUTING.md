# Making NioBot better
Pull requests and issues are always welcome for niobot! Here's a few things to keep in mind when contributing:

## Code style
NioBot uses a very loose code style, however generally, make sure your code is readable, and that the max line length
of your code is 120 characters at a max, preferably less than 119.

If you are unsure about the style of your code, you should run `black ./src` and `isort` in the root directory of the
project. In `pyproject.toml`, all the configuration for those tools is already set up, so you don't need to worry about
command line flags.

### Versions
NioBot uses SemVer (semantic versioning) for versioning. This means that the version number is split into three parts:
`Major`, `Minor` and `Patch`. As per the versioning, `Major` versions are not guaranteed to be backwards compatible,
however `Minor` and `Patch` versions are.

This means that there will always be a new `Major` increment when a backwards incompatible change is made, and a new
`Minor` increment when a backwards compatible change is made. `Patch` versions are almost always bug fixes, and are
always backwards compatible. If a bug fix is not backwards compatible, a new `Major` version will be released.

Major changes may be pushed into their own branches for "feature previews". These branches will be prefixed with
`feature/`, and will be merged into `master` when they are ready for release. For example, `feature/my-thing`,
which means you can install it using `niobot @ git+https://github.com/EEKIM10/niobot.git@feature/my-thing`.
This minimises the number of breaking releases.
