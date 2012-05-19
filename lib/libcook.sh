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

# Shared DB between Cook, the Cooker and Cookiso.
# In cookiso: repo= --> flavors
flavors="$SLITAZ/flavors"
activity="$CACHE/activity"
commits="$CACHE/commits"
cooklist="$CACHE/cooklist"
cookorder="$CACHE/cookorder"
command="$CACHE/command"
blocked="$CACHE/blocked"
broken="$CACHE/broken"
cooknotes="$CACHE/cooknotes"
crontabs="/var/spool/cron/crontabs/root"

# Lograte activity.
[ -s "$activity" ] && tail -n 60 $activity > /tmp/tail-$$ && \
	mv -f /tmp/tail-$$ $activity

# Log activities, we want first letter capitalized.
# TODO: use /lib/libtaz.sh log() but need to change all:
# echo "Message" | log --> log "Message"
log() {
	grep ^[A-Z] | \
		sed s"#^[A-Z]\([^']*\)#$(date '+%Y-%m-%d %H:%M') : \0#" >> $activity
}

# Log broken packages.
broken() {
	if ! grep -q "^$pkg$" $broken; then
		echo "$pkg" >> $broken
	fi
}
