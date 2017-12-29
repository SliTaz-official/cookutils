Brief info about SliTaz receipts v2
===================================

Version 2 was developed as an extension of the receipts in order to facilitate
the maintenance of packages by small forces.

In order to switch to version 2, you must specify 'v2' in the first line of the
receipt:

```bash
# SliTaz package receipt v2.
```

You can write the single receipt v2 to compile, for example `attr` sources and
then make two packages: `attr` and `attr-dev` using compiled files. Next we will
call `attr` the *main package*, while `attr-dev` -- the *split package*.

You must specify all the names of *split packages* that must be created after
the compilation in the SPLIT variable. Example for our `attr` receipt:

```bash
SPLIT="attr-dev"
```

You must specify rules to generate each package inside the genpkg_rules().
Example for package `attr`:

```bash
genpkg_rules() {
    case $PACKAGE in
        attr) copy @std ;;
        attr-dev) copy @dev ;;
    esac
}
```

Here, in every rule you can:

  * use the `copy()` function or other methods to copy specified files from
    $install to $fs.
  * define the DEPENDS variable for specified packages; you may omit this
    definition, then it will mean the following:
    * for the *main package*: it doesn't depend on any package;
    * for the *split packages*: it depends exclusively on a *main package*.
    Note, a receipt is the shell script with all its restrictions: there's no
    difference if you define an empty DEPENDS variable or do not define it at all.
    Here's the small trick: if you really want to define empty dependencies,
    put single spaces between the quotes: `DEPENDS=" "`.
  * define the two-in-one CAT variable for *split packages*. Variable format:
 
    ```bash
    CAT="category|addition"
    ```

    Where `category` is just the chosen category for the specified *split
    package*. And `addition` you will find in the brackets at the end of a
    short description of the specified *split package*. You may omit this
    definition for the "dev" packages. In this case it will be implicitly
    defined as:

    ```bash
    CAT="development|development files"
    ```
  * define some other variables, like COOKOPTS.


Long descriptions
-----------------

You may provide a `description.txt` for the *main package* and/or
`description.package-name.txt` for any of the *split packages*.


`post_install()` and friends
----------------------------

You may define one of the following functions:

  * `pre_install()`;
  * `post_install()`;
  * `pre_remove()`;
  * `post_remove()`.

These functions may be defined for every one of *main* or *split packages*, so
you need to extend function names with underscores (`_`) and the package name.
Like this for the `cookutils` package:

    post_install_cookutils()

Attention! You should know that some characters that are valid in package names
are not allowed in function names. Please, substitute each symbol that doesn't
belong to the intervals `A-Z, a-z, 0-9` by yet another underscore (`_`).
Example for `coreutils-disk`:

    post_install_coreutils_disk()


Function `copy()`
-----------------

It's the flexible tool allowing you to copy files and folders from `$install` to
`$fs` using patterns. All files are copied with the folder structure preserved:

    $install/my/folder/       ->   $fs/my/folder/
    $install/my/system/file   ->   $fs/my/system/file

Now `copy()` understands 4 main forms of patterns:

  * `@std`    - all the "standard" files;
  * `@dev`    - all the "developer" files;
  * `folder/` - append folder name in question by slash;
  * `file`    - file name without the slash at the end.

Both patterns `@std` and `@dev` are meta-patterns making the most common actions
extremely simple. Here all files are divided into three types: standard,
development and all the others (documentation, translations, etc). You may put
`@std` into "standard" package, `@dev` into "developer" package, not packaging
any documentation, man pages, translations, BASH completion, etc...

In the `folder/` and `file` forms of the patterns you can use the asterisk (`*`)
symbol meaning any number of any characters.

Some examples (executed in the chroot with the "busybox" package installed):

  Pattern  | Result
-----------|--------------------------------------------------------------------
`  bin/   `|`/bin`<br>`/usr/bin`
` *bin/   `|`/bin`<br>`/sbin`<br>`/usr/bin`<br>`/usr/sbin`<br>`/var/www/cgi-bin`
`/usr/bin/`|`/usr/bin`
` usr/bin/`|`/usr/bin`
`   r/bin/`|` `
`   cat   `|`/bin/cat`
`  *.sh   `|`/lib/libtaz.sh`<br>`/sbin/mktazdevs.sh`<br>`/usr/bin/gettext.sh`<br>`/usr/bin/httpd_helper.sh`<br>`/usr/lib/slitaz/httphelper.sh`<br>`/usr/lib/slitaz/libpkg.sh`<br>`/var/www/cgi-bin/cgi-env.sh`
`   pt*   `|`/dev/pts`<br>`/usr/share/locale/pt_BR`<br>`/usr/share/locale/pt_BR/LC_MESSAGES`
`/bin/*.sh`|`/usr/bin/gettext.sh`<br>`/usr/bin/httpd_helper.sh`
`/lib/*.sh`|`/lib/libtaz.sh`<br>`/usr/lib/slitaz/httphelper.sh`<br>`/usr/lib/slitaz/libpkg.sh`

Additional patterns for the `copy()`:

  * `@rm`  - quick alias for the `remove_already_packed` function:
    remove from the current package already copied files that was already
    packed in any of previously packed packages (within current receipt);
  * `@ico` - remove all the copied *hicolor* icons (if any) and copy only 16px
    and 48px variants of *hicolor* icons.


### Some more examples of using `copy()`

If your packages are used only for development purposes (like automake, flex, vala
and some others), you may use the next command to put all the files you want
to pack into one package:

```bash
copy @std @dev
```

In most cases, the package breaks up into "main" and "dev" packages. In this
case, your code might look like this:

```bash
PACKAGE="my-package"
SPLIT="my-package-dev"

genpkg_rules() {
    case $PACKAGE in
        my-package)
            copy @std
            DEPENDS="your-package"
            ;;
        *-dev)
            copy @dev
            ;;
    esac
}
```

In the following example, a package can contain libraries (which can be used by
other programs) and executables that use these libraries. We need to split
`@std` into two parts: libraries and executable files. This can be done in a few
ways.

```bash
PACKAGE="my-pkg" 
# We omit "my-pkg" in the $SPLIT, then it is implicit in the first place
SPLIT="my-pkg-bin my-pkg-dev"
genpkg_rules() {
    case $PACKAGE in
        my-pkg) copy *.so*;; # (1) copy all the libs
        *-bin)  copy bin/;;  # (2) copy all the execs from /usr/bin/
        *-dev)  copy @dev;;  # (3) copy development files
    esac
}
```

```bash
# If a package contains some more files outside of the /bin/ (for example, configs),
# that we want to pack with the "bin" package:
PACKAGE="my-pkg"
SPLIT="my-pkg-bin my-pkg-dev"
genpkg_rules() {
    case $PACKAGE in
        my-pkg) copy *.so*;;    # (1) copy all the libs
        *-bin)  copy @std @rm;; # (2) copy standard (binaries and configs, etc),
                                #     then remove already packed (libs)
        *-dev)  copy @dev;;     # (3) copy development files
    esac
}
```

```bash
# Pack two different libraries into two packages, and the rest into a third
# package:
PACKAGE="my-pkg"
# We explicitly specify all the packages, therefore they will be processed
# in the specified order
SPLIT="my-pkg-lib1 my-pkg-lib2 my-pkg my-pkg-dev"
genpkg_rules() {
    case $PACKAGE in
        *-lib1) copy lib-cli.so*;; # (1) copy first libraries
        *-lib2) copy lib-gui.so*;; # (2) copy second libraries
        my-pkg) copy @std @rm;;    # (3) copy all the standard files,
                                   #     then remove already packed (libs)
        *-dev)  copy @dev;;        # (4) copy development files
    esac
}
```


Compiling sets
--------------

Sometimes you may need to compile the same source code of the same version,
but with different options. For example, without PAM support and with PAM
support. Or with support for GTK+2 or GTK+3. Or a complete package with all
the rich features and a small limited package. You can not limit yourself
in the number of options.

Compiling set is a pair of separate `$src` and `$install` folders. You can
still compile the sources using the `$src` variable and install compiled files
into folder defined by `$install` variable, but these values will be different
for the different compiling sets.

Set defined by the name which is simple mnemonic made up of one or more letters
or numbers. It may be "1", "2", "z", or something more meaningful like "pam",
"gtk2", or "gtk3".

Also you should know that default set with the empty name always exists
for the backward compatibility and for the cases when you don't want to use
the sets.

How to use the sets?

First, you should define which set you want to use for each package appending
package names in the `$SPLIT` variable. You may not make it for the default set
with empty name. Few examples:

```bash
PACKAGE="fuse-emulator"
SPLIT="fuse-emulator-gtk3:gtk3"
```

```bash
PACKAGE="yad"
SPLIT="yad-html:html yad-gtk3:gtk3"
```

```bash
PACKAGE="urxvt"
SPLIT="urxvt-full:full"
```

Second, function `compile_rules()` will be executed sequently for default set
and then for all the sets you mention in the `$SPLIT` variable on the previous
step. You should make the business logic inside the `compile_rules()` function
to compile and install different variants based on the value of the `$SET`
variable. This variable has an empty value for the default set and the set
name in other cases. Few examples how you make the job:

```bash
PACKAGE="fuse-emulator"
SPLIT="fuse-emulator-gtk3:gtk3"

compile_rules() {
    SET_ARGS=''; [ -z "$SET" ] && SET_ARGS='--disable-gtk3'

    ./configure \
        --enable-desktop-integration \
        $SET_ARGS \
        $CONFIGURE_ARGS &&
    make && make install
}
```

```bash
PACKAGE="urxvt"
SPLIT="urxvt-full:full"

compile_rules() {
    case $SET in
        '')
            ./configure \
                --disable-everything \
                $CONFIGURE_ARGS &&
            make && make install
            ;;
        full)
            ./configure \
                --enable-everything \
                --enable-256-color \
                --with-terminfo=/usr/share/terminfo \
                $CONFIGURE_ARGS &&
            make && make install || return 1

            R="$install/usr/share/terminfo"
            mkdir -p $R
            tic -s -o $R $src/doc/etc/rxvt-unicode.terminfo
            ;;
    esac
}
```

```bash
PACKAGE="yad"
SPLIT="yad-html:html yad-gtk3:gtk3"

compile_rules() {
    case $SET in
        '')   Gtk=gtk2; Html=disable;;
        html) Gtk=gtk2; Html=enable ;;
        gtk3) Gtk=gtk3; Html=disable;;
    esac

    ./configure \
        --enable-icon-browser \
        --with-gtk=$Gtk \
        --$Html-html \
        $CONFIGURE_ARGS &&
    make &&
    make install
}
```

Thirdly, make `genpkg_rules()` as usual. *Cook* will switch to the required
set automatically based on conformity between packages and sets that you
described in the `$SPLIT` variable on the first step. That's all.


Dependency tracking
-------------------

Many packages use `libtool`, created during the `configure` processing.
This `libtool` contains one old and well-known (in narrow circles) “feature”
that is expressed in the fact that unnecessary dependencies are added to
libraries and executable files. Read about it:

  * [Bug 655517 - using --as-needed in LDFLAGS is not respected and it links
    on unneeded libs](https://bugzilla.gnome.org/show_bug.cgi?id=655517)
  * [Project:Quality Assurance/As-needed](https://wiki.gentoo.org/wiki/Project:Quality_Assurance/As-needed)

Links above recommend to add `-Wl,--as-needed` to the LDFLAGS variable. You can
use short statement `fix ld` in the beginning (to add `-Wl,--as-needed` to the
LDFLAGS) and `fix libtool` just after the `configure` invocation (to
additionally fix just created `libtool`). Example of using:

```bash
compile_rules() {
    fix ld
    ./configure \
        --sysconfdir=/etc \
        $CONFIGURE_ARGS &&
    fix libtool &&
    make && make install
}
```

You should not use `fix libtool` if you do not see a file named `libtool` in the root
of the sources tree after the `configure` is done. It will not lead to an error,
although there will be no sense in it.

You can check dependencies of separate files using one of the next methods:

```bash
ldd /path/to/file

readelf -d /path/to/file | grep NEEDED
```

You can check dependencies of an entire package using the command:

```bash
cook package_name --deps
```

You can note a significant decrease in the number of dependencies. For example:

  * for **fontconfig**:
    * before: bzlib freetype liblzma libpng16 libxml2 zlib
    * after: freetype libxml2
  * for **at-spi2-core**:
    * before: dbus glib libffi pcre util-linux-blkid util-linux-mount
      util-linux-uuid xorg-libICE xorg-libSM xorg-libX11 xorg-libXau
      xorg-libXdmcp xorg-libXext xorg-libXi xorg-libXtst xorg-libxcb zlib
    * after: dbus glib xorg-libX11 xorg-libXtst

For some packages nothing will change.


### Dependency tracking for development packages

This is a separate and complex issue.

Dependency info may be extracted from `.pc`, `.la` and `.h` files. Extracting
dependencies from the header files (`.h`) is a non-trivial task due to conditional
branching and can not be realized using simple tools.

As for `.la` files — Gentoo
[recommend](https://wiki.gentoo.org/wiki/Project:Quality_Assurance/Handling_Libtool_Archives)
to remove them in most cases. As they stated, `.la` files may be useful only
for static libraries (`.a` files). Currently, the dependency tracking tool doesn't
use `.la` files unless you a provide special argument `--la`:

```bash
cook fontconfig --deps --la
```

It turns out that `.pc` files are the only development files that describe
dependencies of development packages. Usually the `configure` script checks
dependencies using something like this:

```bash
pkg-config --exists --print-errors "gtk-doc >= 1.15"
pkg-config --exists --print-errors "xrender >= 0.6"
```

Dependency tracking tools try to find the package that contains required
libraries, then determine a `*-dev` package that corresponds to the found package.

For example, file `/usr/lib/pkgconfig/cairo.pc` contains the line:

```
Requires.private:   gobject-2.0   glib-2.0 >= 2.14   pixman-1 >= 0.30.0
    fontconfig >= 2.2.95   freetype2 >= 9.7.3   libpng    xcb-shm    x11-xcb
    xcb >= 1.6   xcb-render >= 1.6   xrender >= 0.6   x11   xext
```

Finding the next files shows the dependencies:

```
gobject-2.0.pc   glib-2.0.pc   pixman-1.pc   fontconfig.pc   freetype2.pc
    libpng.pc   xcb-shm.pc   x11-xcb.pc   xcb.pc   xcb-render.pc   xrender.pc
    x11.pc   xext.pc
```

Next example using file `/usr/lib/pkgconfig/apr-1.pc`:

```
prefix=/usr
exec_prefix=${prefix}
libdir=${exec_prefix}/lib
APR_MAJOR_VERSION=1

Libs: -L${libdir} -lapr-${APR_MAJOR_VERSION} -luuid -lrt -lcrypt  -lpthread -ldl
```

Finding the next files shows the runtime dependencies and then full dependencies;
`*-dev` packages are the full packages.

```
libapr-1.so    libuuid.so      librt.so   libcrypt.so   libpthread.so   libdl.so
     |             |               |           |              |            |    
     v             v               v           v              v            v    
    apr     util-linux-uuid   glibc-base  glibc-base     glibc-base   glibc-base
     |             |               |           |              |            |    
     v             v               v           v              v            v
  apr-dev  util-linux-uuid-dev glibc-dev   glibc-dev      glibc-dev    glibc-dev

```

Note, sometimes required files may be found in two or more packages, for
example, `libdl.so` exists within packages:

  * `glibc-base`
  * `uclibc-armv4eb`
  * `uclibc-armv4l`
  * `uclibc-armv4tl`
  * `uclibc-armv5l`
  * `uclibc-armv6l`
  * `uclibc-cross-compiler-armv4eb`
  * `uclibc-cross-compiler-armv4l`
  * `uclibc-cross-compiler-armv4tl`
  * `uclibc-cross-compiler-armv5l`
  * `uclibc-cross-compiler-armv6l`
  * `uclibc-cross-compiler-i486`
  * `uclibc-cross-compiler-mips`
  * `uclibc-cross-compiler-mips64`
  * `uclibc-cross-compiler-mipsel`
  * `uclibc-cross-compiler-powerpc`
  * `uclibc-cross-compiler-sh4`
  * `uclibc-cross-compiler-sparc`
  * `uclibc-cross-compiler-x86_64`
  * `uclibc-i486`
  * `uclibc-mips`
  * `uclibc-mips64`
  * `uclibc-mipsel`
  * `uclibc-powerpc`
  * `uclibc-sh4`
  * `uclibc-sparc`
  * `uclibc-x86_64`

