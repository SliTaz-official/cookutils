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
if [ "$(basename $0)" = "cookiso" ]; then
	cache="$CACHE/cookiso"
	#cookiso variables
	repo="$SLITAZ/flavors"
	iso="$SLITAZ/iso"
	rollog="$cache/rolling.log"
	synclog="$cache/rsync.log"
else
	cache="$CACHE"
fi

flavors="$SLITAZ/flavors"
activity="$cache/activity"
commits="$cache/commits"
cooklist="$cache/cooklist"
cookorder="$cache/cookorder"
command="$cache/command"
blocked="$cache/blocked"
broken="$cache/broken"
unbuild="$cache/unbuild"
wokrev="$cache/wokrev"
cooknotes="$cache/cooknotes"
crontabs="/var/spool/cron/crontabs/root"

wan_db="$INCOMING/wanted.txt"
dep_db="$INCOMING/depends.txt"
lib_db="$INCOMING/libraries.txt"
# full cookorder
fullco="$PKGS/fullco.txt"

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

# Remove blocked (faster this way than grepping before).
strip_blocked() {
	local pkg
	for pkg in $(cat $blocked)
	do
		sed -i /^${pkg}$/d $cooklist
		PACKAGE="$pkg"
		for i in $(look_for_rwanted); do
			sed -i /^${i}$/d $cooklist
		done
	done && sed -i /^$/d $cooklist
}
