# General questions

## `sed` or patches?

Sometimes I come across cases where `sed` is used to change some values in the
source code or to add / remove / change some parts of the source code.
It may look like a good idea for a one-time job, but you will encounter
problems in the future when you upgrade the package.

`sed` works quietly and it is impossible to understand whether it found what
was needed to be found, whether it replaced what we wanted? Maybe this change
is already in the new sources and we no longer need `sed` command?

If we consider only the updated sources, sometimes it is impossible
to understand the essence of the `sed` changes. And then you have to download
and analyze the old sources.

Feel free to use patches. The `patch` is smart enough to find the necessary
lines in the new sources and also it will signal to you if your changes have
already been made in the sources or if the sources has changed so much that
your intervention is required.

Go from `sed` to `patch` is easy. You must use the `-o.backup` option (value
after the `-o` you can change). For example, you used this code:

```bash
sed -i '/debug/ s|true|false|' config
```

Now apply the changes saving the original file:

```bash
sed -i.orig '/debug/ s|true|false|' config
```

Create a patch using the original and modified files:

```bash
diff ./config.orig ./config > ../../stuff/patches/config.patch
```

Now you can use the created patch and remove the `sed` command.

