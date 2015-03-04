#!/bin/sh

DONELIST=${1:-/tmp/donelist}

. /home/slitaz/wok/slitaz-toolchain/receipt
SLITAZ_TOOLCHAIN="slitaz-toolchain $DEPENDS"
touch $DONELIST
while true; do
	chmod +x $DONELIST
	for i in /home/slitaz/wok/*/receipt ; do
		pkg=$(basename ${i%/receipt})
		grep -q "^$pkg$" $DONELIST && continue
		grep -q "^$pkg$" /home/slitaz/cache/broken && continue
		unset BUILD_DEPENDS WANTED
		. $i
		for j in $BUILD_DEPENDS $WANTED ; do
			case " $SLITAZ_TOOLCHAIN " in
			*\ $j\ *) continue ;;
			esac
			grep -q "^$j$" $DONELIST || continue 2
		done
		cooker pkg $PACKAGE
		[ /home/slitaz/packages/$PACKAGE-$VERSION*.tazpkg -nt $DONELIST ] || continue
		echo $PACKAGE >> $DONELIST
		chmod -x $DONELIST
	done
	[ -x $DONELIST ] || continue
	# try to break build dep loops...
	for pkg in gettext python udev cups libQtClucene menu-cache ; do
		grep -q "^$pkg$" $DONELIST && continue
		grep -q "^$pkg$" /home/slitaz/cache/broken && continue
		. /home/slitaz/wok/$pkg/receipt
		cooker pkg $PACKAGE
		[ /home/slitaz/packages/$PACKAGE-$VERSION*.tazpkg -nt $DONELIST ] || continue
		echo $PACKAGE >> $DONELIST
		continue 2
	done
	break
done

TODOLIST=/tmp/todolist
# list packages to build and their (build) dependancies
for i in /home/slitaz/wok/*/receipt ; do
	grep -q "^$(basename ${i%/receipt})$" $DONELIST && continue
	unset BUILD_DEPENDS WANTED
	. $i
	echo -n "$PACKAGE : "
	for j in $BUILD_DEPENDS $WANTED ; do
		grep -q "^$j$" $DONELIST || echo -n "$j "
	done
	echo
done > $TODOLIST
echo "$(wc -l $TODOLIST) packages unbuilt in $TODOLIST"

