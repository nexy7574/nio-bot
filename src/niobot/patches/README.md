# Patches

Sometimes, there's an upstream package that doesn't quite have what we need (yet).
For example, there's been a few occasions where matrix-nio has been missing a feature that we need, but it was in a
pull request.

In these cases, we can use a patch to add the feature we need.

Patch files use the following naming scheme: `src/niobot/patches/{package_name}__{path}`. For example,
`src/niobot/patches/nio__responses.py`, or `src/niobot/patches/anyio__streams__buffered.py`.

These patches should include information in comments or docstrings regarding why they're there, what they do, and when
removal is appropriate.
