#!/bin/sh

DONELIST=${1:-/tmp/donelist}

. /etc/slitaz/cook.conf
. $WOK/slitaz-toolchain/receipt
SLITAZ_TOOLCHAIN="slitaz-toolchain $DEPENDS"
touch $DONELIST
while true; do
	chmod +x $DONELIST
	for i in $WOK/*/receipt ; do
		pkg=$(basename ${i%/receipt})
		grep -q "^$pkg$" $DONELIST && continue
		grep -q "^$pkg$" $CACHE/broken && continue
		unset BUILD_DEPENDS WANTED
		HOST_ARCH="i486"
		. $i
		case " $HOST_ARCH " in
		*\ i486\ *|*\ any\ *);;
		*) continue;;
		esac
		for j in $WANTED ; do
			grep -q "^$j$" $DONELIST || continue 2
			grep -q "^$j$" $CACHE/broken && continue 2
		done
		for j in $BUILD_DEPENDS ; do
			case " $SLITAZ_TOOLCHAIN " in
			*\ $j\ *) continue ;;
			esac
			grep -q "^$j$" $DONELIST || continue 2
			grep -q "^$j$" $CACHE/broken && continue 2
		done
		cooker pkg $PACKAGE
		[ $PKGS/$PACKAGE-$VERSION*.tazpkg -nt $DONELIST ] || continue
		echo $PACKAGE >> $DONELIST
		chmod -x $DONELIST
	done
	[ -x $DONELIST ] || continue
	# try to break build dep loops...
	for pkg in gettext python udev cups libQtClucene menu-cache tzdata ; do
		grep -q "^$pkg$" $DONELIST && continue
		grep -q "^$pkg$" $CACHE/broken && continue
		. $WOK/$pkg/receipt
		cooker pkg $PACKAGE
		[ $PKGS/$PACKAGE-$VERSION*.tazpkg -nt $DONELIST ] || continue
		echo $PACKAGE >> $DONELIST
		continue 2
	done
	break
done

TODOLIST=/tmp/todolist
# list packages to build and their (build) dependancies
for i in $WOK/*/receipt ; do
	grep -q "^$(basename ${i%/receipt})$" $DONELIST && continue
	unset BUILD_DEPENDS WANTED
	HOST_ARCH="i486"
	. $i
	case " $HOST_ARCH " in
	*\ i486\ *|*\ any\ *);;
	*) continue;;
	esac
	grep -q "^$PACKAGE$" $CACHE/broken && echo -n "broken/"
	echo -n "$PACKAGE : "
	for j in $BUILD_DEPENDS $WANTED ; do
		grep -q "^$j$" $DONELIST || echo -n "$j "
		grep -q "^$j$" $CACHE/broken && echo -n "broken/$j "
	done
	echo
done > $TODOLIST
echo "$(wc -l $TODOLIST) packages unbuilt in $TODOLIST"

