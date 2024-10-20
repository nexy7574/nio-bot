# Making NioBot better

Issues and pull requests are the lifeblood of nio-bot. Opening issues is one of the most helpful things you can do,
and pull requests are even better. This document will guide you through the process of contributing to nio-bot.
From hereon, the term "contributing" will refer to both opening issues and pull requests, picking which is applicable.

Here's a few things to keep in mind when contributing:

## Scope

Please keep in mind that nio-bot is a bot *library* - not a bot itself. This package is designed to be the framework
for quickly and easily making great bots, and you should hold that in mind when considering new features.

If you're unsure whether a feature is in scope, feel free to open an issue and ask.
You should consider the following questions too:

<details>
<summary>A list of questions to ask yourself before contributing new features.</summary>

### 1. Is this feature useful for more than me?

A common scope problem seen when contributing to frameworks such as nio-bot is asking for or trying to implement
functionality that simply isn't useful for more than a handful of users.
Think - will someone with a specific type of bot find this useful? or will an everything-bot find this useful?
If you only answered yes to the former, then it is likely not something that needs implementing into nio-bot.

> don't forget - you are welcome to create community plugins. If you feel your feature is useful, but is not enough to
> be implemented into the core library, you can take a look at [community plugin information](#community).

### 2. Is this feature relevant?

Another common scope problem is asking for or trying to implement functionality that simply isn't relevant to the
core library. For example, integrating something like youtube-dl into nio-bot would be a bad idea, as it is not
relevant to the core library, which is focused around Matrix and bots.

### 3. Is this feature complicated?

If you think a feature may be too complicated to either be implemented or used, it may be a good idea to reconsider
whether it should be implemented. If you're unsure, feel free to ask.

Remember - technical debt exists. If you add something to nio-bot, it has to be maintained. If you add something
that is too complicated, it may be difficult to maintain, and may be removed in the future.

## Code style

NioBot now makes use of `ruff` for code formatting, and this is automatically enforced by the CI.
You should run `ruff format` in the root directory of the project to format your code before submitting a pull request.
The rules that are used for formatting are already pre-created in the pyproject.toml file, so you do not need to worry
about arguments.
If you just want to check that your code is following the code style without making any changes, run `ruff check`.

Pre-commit is available if you desire, and there are CI checks to ensure that your code is formatted correctly.

### Versions

NioBot very loosely uses [Semantic Versioning](https://semver.org/).
You've probably heard of semver before, but if you haven't there's 3 parts to a version number: `MAJOR.MINOR.PATCH`.
These are incremented with MAJOR (API incompatible) changes, MINOR (backwards-compatible) changes,
and PATCH (backwards-compatible bug fixes) changes.

When "loosely uses" is used, it means that nio-bot will try to follow semver as closely as possible, however,
the MAJOR segment does not get bumped with every breaking change, only if there are several.
For example, if a non-core function signature changes incompatibly, it will not bump the major version. However, if
several functions change incompatibly, it will bump the major version.

Major changes may be pushed into their own branches for "feature previews". These branches will be prefixed with
`feature/`, and will be merged into `master` when they are ready for release. For example, `feature/my-thing`,
which means you can install it using `nio-bot @ git+https://github.com/nexy7574/niobot.git@feature/my-thing`.
This minimises the number of breaking releases.
</details>

### Backwards compatibility for python

While nio-bot aims to support the most recent stable releases of python, it must also support up to two previous
stable releases of python.

For example, nio-bot was originally developed in python 3.11. In order to give developers time to catch up,
nio-bot also supports python 3.9 and 3.10 at the time of writing.

This means, when you're contributing, you should make sure you don't use any brand-new language features. Always check
that a language feature you have is available two versions ago. For example, using `typing.Union` instead of
the ` | ` union type that was introduced in python 3.10.

There is no guaranteed support for newer than specified python versions. This includes alpha, beta and
release candidates.
Furthermore, in the interest of backward compatibility, it may take a while until nio-bot supports the latest
language features. Keep this in mind.

**End of life versions are never actively supported**. See [EOL.date](https://endoflife.date/python) for more
information.

# Community

The great thing about open source software is the ability for anyone to read, understand, and contribute to it.
NioBot, with our strong copy-left [LGPLv3](/LICENSE) license, is no exception.

If you think there's something that could benefit nio-bot users, however don't think it's in scope or relevant to the
core library, you are welcome to create a community plugin. Community plugins are plugins that are not part of the
core library, however can still be installed and used by nio-bot users.

Plugins can take a multitude of forms:

* A package that takes advantage of the `niobot.utils` namespace to create additions to the existing library
* A package with its own namespace, which can be imported by users, and may be more relevant for a specific use case
or one outside of matrix and nio-bot itself.
* A module that users can load at runtime.

Here's a few guidelines to help you get started with designing your plugin:

## `niobot.utils` namespace

In niobot, there's two namespaces: the parent `niobot` (`import niobot`) namespace, and the `niobot.utils` namespace.

The `niobot.utils` namespace is designed for utility functions that are either very specific, or are simply just helpers.
An example of this is [niobot.utils.typing](/src/niobot/utils/typing.py). This function houses a simple context wrapper,
`Typing`, which (while core to the library for sending & editing events), is highly specific, and is a helper. 
As such, it resides in the `niobot.utils` namespace.

If you wanted to create a plugin that resided in the `niobot.utils` namespace, you should make your project with
the following file structure:

```
root/
| pyproject.toml
| src/
| | niobot/
| | | utils/
| | | | - my_plugin.py
```

Then, users (after running `pip install my-plugin-name`), can import your plugin using `import niobot.utils.my_plugin`.
This allows for simple integration with the core library, and allows for users to easily install and use your plugin,
all without modifying any native files in the library.

This is the preferred way to create community plugins that are not interactive.

## External namespace

If you want to create a plugin that is rather out of scope, you should avoid using the niobot namespace at all.

For example, if you wanted to create a plugin that was designed for a specific use case, such as a bot that is designed
to be a music bot, you should create a package with its own namespace, such as `my-music-bot`. This makes sure that
your plugin is not confused with the core library, and also allows for you to create a package that is more relevant
to your use case.

If you wanted to create a plugin that resided in its own namespace, you should make your project with the following
file structure:

```
root/
| pyproject.toml
| src/
| | my_plugin/
| | | - __init__.py
| | | - my_plugin_code.py
```

Then, users (after running `pip install my-plugin-name`), can import your plugin using `import my_plugin.my_plugin_code`.

## Module

If you want to create a plugin that is mainly interactive (i.e. does not provide many functions for developers to use),
you should create a module.

For example, to include a suite of commands for the bot developer to use (such as eval, shell, git, etc), you should
make it a module and allow for it to be [loaded later on](https://nexy7574.github.io/niobot/reference/client/#niobot.client.NioBot.mount_module).

Take a look at [the guide for making a module](https://nexy7574.github.io/niobot/guides/getting-started/#making-funpy) if 
you're not sure how to get started.
