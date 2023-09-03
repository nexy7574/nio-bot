# The help command
`NioBot` comes with a built-in help command, which can be used to display information about other commands.

This built-in command is simple, slick, and most importantly, helpful.
It takes one optional argument, `command`, which changes the output to display information about a specific command.
Without this, the help command will list every enabled command, their aliases, a short help string, and a short
description about the command (by default, the first line of the docstring).

This allows for you to easily just add commands and not have to worry about documenting them outside of simply defining
their usage in the command decorator, and a short description in the docstring.

??? abstract "An example of the help command with no arguments"
    ??? quote "Source of this sample"
        This is the output of the help command from 
        [nexy7574/niobot-test](https://github.com/nexy7574/niobot-test/tree/f99160/)
    ```
    ?[help|h]: Shows a list of commands for this bot
    ?[ytdl|yt|dl|yl-dl|yt-dlp] <url> [format]: Downloads a video from YouTube
    ?[quote|q]: Generate a random quote.
    ?ping: Shows the roundtrip latency
    ?info: Shows information about the bot
    ?cud: Creates, updates, and deletes a message
    ?upload <type: image|video|audio|file>: Uploads an image
    ?hello: Asks for an input
    ?version: Shows the version of nio
    ?[pretty-print|pp]: Pretty prints given JSON
    ?eval: Evaluates Python code
    ```

    ??? info
        There is markdown formatting in the output, but it is not shown here.

??? abstract "An example of the help command with a specified command name"
    ??? quote "Source of this sample"
        This is the output of the help command from 
        [nexy7574/niobot-test](https://github.com/nexy7574/niobot-test/tree/f99160/)

    ```
    ?[help|h]:
    Shows a list of commands for this bot
    ```
    ??? info
        There is markdown formatting in the output, but it is not shown here.

-------------------------------------------

## Registering your own help command
If you would like to register your own help command, you need to be aware of the following:

* The help command is a command, much like any other command, and is registered as such. You should be aware of 
aliases, case sensitivity, command states (e.g. disabled/enabled), etc.
* A help command is almost always a user's first impression of your bot. You should make sure that it works 100% of the
time, is insanely simple to use, and is very helpful. A help command that just says "You can use command like ?info"
is not helpful at all, and will likely turn many users away.

???+ question Are there any dangers to these help commands?

## Help Command functions:

::: niobot.utils.help_command
