#!/bin/sh
#
# Cook library - Shared configs and functions between cook, the cooker and
# cookiso. Read the README before adding or modifing any code in libcook.sh!
#
# Copyright (C) SliTaz GNU/Linux - GNU gpl v3
# Author: Christophe Lincoln <pankso@slitaz.org>
#
. /lib/libtaz.sh
. /usr/lib/slitaz/libpkg.sh
. /etc/slitaz/slitaz.conf

# System wide config can be overwriten by a cook.conf in current path.
[ -f "/etc/slitaz/cook.conf" ] && . /etc/slitaz/cook.conf
[ -f "cook.conf" ] && . ./cook.conf
