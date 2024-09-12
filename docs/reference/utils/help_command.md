# The help command
`NioBot` comes with a built-in help command, which can be used to display information about other commands.

This built-in command is simple, slick, and most importantly, helpful.
It takes one optional argument, `command`, which changes the output to display information about a specific command.

## The command list

If a command name is not passed to the help command, it will instead display a list of all available commands.
The information that will be displayed will be:

* The command's name
* Any aliases the command has
* The command's short description (usually first 100 characters of first line of the command's callback docstring)
* Any arguments that're required or optional (required are encased in `<brackets>`, optional in `[brackets]`)

The command is only listed if:

* The command is not disabled (i.e. `disabled=True` is passed, or omitted entirely)
* The command is not hidden (i.e. `hidden=True` is **not** passed (or is ommitted entirely))
* The user passes all of the [checks](checks.md) for the command

The command list is sorted alphabetically by command name, and is not paginated or seperated at all.
If you want a pretty help command, you should write your own - the default one is just meant to be a happy middle ground
between pretty and functional. See the next section for more information on how to do this.

-------------------------------------------

## Registering your own help command
If you would like to register your own help command, you need to be aware of the following:

* The help command is a command, much like any other command, and is registered as such. You should be aware of 
aliases, case sensitivity, command states (e.g. disabled/enabled) and visibility (hidden/shown), checks, etc.
* A help command is almost always a user's first impression of your bot. You should make sure that it works 100% of the
time, is insanely simple to use, and is very helpful. A help command that just says "You can use command like ?info"
is not helpful at all, and will likely turn many users away.

As of v1.2.0, the help command is now a class that you can easily subclass. This is the recommended way of doing this.

The only function that you NEED to change is `respond`, which is the function that is called when the help command is run.
The rest is, quite literally, just dectoration.

Here's an example of a custom help command:

```python
from niobot import DefaultHelpCommand, NioBot


class MyHelpCommand(DefaultHelpCommand):
    async def respond(self, ctx, command=None):
        if command is None:
            # No argument was given to !help
            await ctx.respond("This is a custom help command!")
        else:
            # a command name was given to !help
            await ctx.respond(f"Help for command {command} goes here!")


client = NioBot(help_command=MyHelpCommand().respond)
```

Now, when someone runs `!help`, they will get a custom response from the `MyHelpCommand` class.

??? danger "`help_command` *should* be a full Command instance."
    While the above code gives the `response` function to the `help_command` parameter, it is not the ideal way to do this.
    You should pass a [niobot.Command][] instance to the help command instead, as this gives you a more
    consistent experience, with fine-grained control over the command's state, aliases, etc.

    For the sake of berevity, the above code is used to demonstrate the concept of a custom help command.


## The DefaultHelpCommand class
::: niobot.utils.help_command.DefaultHelpCommand
