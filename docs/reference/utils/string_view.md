# String View

!!! note "This is mostly an internal utility."
    The ArgumentView is mostly used by the internal command parser to parse arguments.
    While you will be able to use this yourself, its very unlikely that you'll ever actually need it.

!!! warning "This is a work in progress."
    The string view does a lot of complicated maths and logic to determine arguments. It's not as simple as just
    splitting the string on every whitespace and calling it an argument, the ArgumentView parser has to check for
    quotes, escape characters, and more.

    Due to the complexity of the parser, it's very likely that there are still bugs in the parser. Fixes welcome!

::: niobot.utils.string_view
