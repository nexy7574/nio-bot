# Index

Welcome to the Nio-Bot Documentation

## What is NioBot?

NioBot (also referred to as nio-bot, or niobot) is a python library built on the 
[matrix-nio](https://pypi.org/project/matrix-nio) matrix sdk library (guess where we got
our name from), which builds on an already powerful, extensive framework, to provide
a super simple, easy-to-use matrix bot client.

Traditionally, making bots with `matrix-nio` isn't massively difficult - it was just time
consuming, with a lot of boiler plate, and often times a rushed lack of redundancy.
In turn, making your own bot in base nio would end up with you making your own little
in-house specialised framework, which not only is a lot of work to make and maintain, but
usually ends up not being very flexible.

NioBot aims to solve this problem by providing a framework that is both easy to use, and
flexible enough to be used in a variety of situations.

Also, Matrix and Matrix clients can be daunting to new users, and NioBot aims to make
it easier for new users to get into Matrix, and to make it easier for them to make their
own bots.

??? quote "Creation background and motivations"
    I ([nex](https://github.com/nexy7574)) personally come from a discord bot development background, and am used to using discord.py (now [py-cord](https://pypi.org/project/py-cord)),
    and jumping over to matrix gave me a strong whiplash feeling.
    In fact, it felt so different that I gave up twice making bots.
    This is actually my second public matrix bot framework, with the predecessor being called `matrix.py`
    (which is no longer available, and was never really finished).

    I decided to make this framework because I wanted to be able to have a single central framework that I could
    use for automating my account and also making some bots in, and thus NioBot was born.

    NioBot actually first started off as a fork of my now dead in-house framework I made ad-hoc for a bot
    at the time, borrowing a *lot* of code from it.
    However, as time has gone on, I've added so much more, including encryption support, images, and more.

    ---

    NioBot is designed to have a similar feel to `py-cord`, while still being true to the `matrix-nio`` library.

    As a matter of fact, I've personally contributed to both `py-cord` and `matrix-nio`, so you can rest assured
    that I know how both of these libraries work, and can get the most out of their feature set.

**Interested?** Carry on reading!

### Features

- A powerful commands framework (Modules, aliases, checks, easy extensibility)
- A flexible event system
- Simple end-to-end encryption
- Automatic markdown rendering when sending/editing messages
- Super simple to use Attachments system
- Very customisable monolithic client instance
- A simple, easy-to-use CLI tool for some on-the-go tasks
- And more to come

## Support

You can join our [Matrix room](https://matrix.to/#/#niobot:nexy7574.co.uk) for support if 
you are unable to find your answer in these docs.

Don't forget to look at the guides!

## Installing

### From PyPi

The package is [nio-bot](https://pypi.org/project/nio-bot/), and can be installed with
`pip install nio-bot[e2ee,cli]`.

### From github releases

If you are unable to use PyPi for whatever reason, python wheels and source distributions are available in all github releases.

Just go to [the releases page](https://github.com/nexy7574/niobot/releases), and download the latest release.

You can then `pip install <wheel file>`.

### From source

If you want to get bleeding edge features, or simply build from source, you can use git.
For example:

```bash
pip install git+https://github.com/nexy7574/niobot.git@master#egg=nio-bot[e2ee,cli]
```

(replace @master with @branch-name or @tag-name for a specific branch or tag.)

## CLI

The `niobot` package comes with a CLI tool, which can be used to create templates, get access tokens, resolve
homeservers, and more (in the future).

You can install the cli tool with the `cli` extra. The command itself is `niocli`.

## Version information

Version information is found in the `__version__.py` file, which is created while installing the package.

```python
from niobot.__version__ import __version__
print(__version__)
```

## Logging

Logging is done using the `logging` module. The logger is named `niobot.<module>`. For example:

```python
import logging
import niobot

logging.basicConfig(level=logging.INFO)
bot = niobot.NioBot(...)

bot.run(...)
```

This will now output a bunch of logs to your console, which you can use to debug your bot.
