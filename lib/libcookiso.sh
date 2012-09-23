#!/bin/sh

# libcookiso functions

. /usr/lib/slitaz/libcook.sh
. /usr/lib/slitaz/libmodular.sh

TOP_DIR="$(pwd)"
TMP_DIR=/tmp/cookiso-$$-$RANDOM
TMP_MNT=/media/cookiso-$$-$RANDOM
INITRAMFS=rootfs.gz
MIRROR=$DB/mirror
[ -f "/etc/slitaz/cookiso.conf" ] && CONFIG_FILE="/etc/slitaz/cookiso.conf"
[ -f "$TOP_DIR/cookiso.conf" ] && CONFIG_FILE="$TOP_DIR/cookiso.conf"
DEFAULT_MIRROR="$MIRROR_URL/packages/$SLITAZ_VERSION/"

log=/var/log/cookiso.log
if check_root; then
	newline > $log
fi

if [ ! "$CONFIG_FILE" = "" ] ; then
	. $CONFIG_FILE
else
	if [ "$COMMAND" = "gen-config" ] ; then
		continue
	else
		echo "Unable to find any configuration file. Please read the docs"
		echo "or run '`basename $0` gen-config' to get an empty config file."
		exit 0
	fi
fi

# While Tazpkg is not used the default mirror url file does not exist
# and user can't recharge the list of flavors.
if test $(id -u) = 0 ; then
	if [ ! -f "$MIRROR" ]; then
		echo "$DEFAULT_MIRROR" > $MIRROR
	fi
fi


yesorno()
{
	echo -n "$1"
	case "$DEFAULT_ANSWER" in
	Y|y) answer="y";;
	N|n) answer="n";;
	*) read answer;;
	esac
}

field()
{
	grep "^$1" "$2" | sed 's/.*: \([0-9KMG\.]*\).*/\1/'
}

todomsg()
{
	echo -e "\\033[70G[ \\033[1;31mTODO\\033[0;39m ]"
}

# Download a file from this mirror
download_from()
{
	local i
	local mirrors
	mirrors="$1"
	shift
	for i in $mirrors; do
		case "$i" in
		http://*|ftp://*) wget -c $i$@ && break;;
		*) cp $i/$1 . && break;;
		esac
	done
}

# Download a file trying all mirrors
download()
{
	local i
	for i in $(cat $MIRROR $DB/undigest/*/mirror 2> /dev/null); do
		download_from "$i" "$@" && break
	done
}

# Execute hooks provided by some packages
genisohooks()
{
	local here=$(pwd)
	for i in $(ls $ROOTFS/etc/slitaz/*.$1 2> /dev/null); do
		cd $ROOTFS
		. $i $ROOTCD
	done
	cd $here
}

cleanup()
{
	if [ -d $TMP_MNT ]; then
		umount $TMP_MNT
		rmdir $TMP_MNT
		rm -f /boot
	fi
}

# Echo the package name if the tazpkg is already installed
installed_package_name()
{
	local tazpkg
	local package
	local VERSION
	local EXTRAVERSION
	tazpkg=$1
	# Try to find package name and version to be able
	# to repack it from installation
	# A dash (-) can exist in name *and* in version
	package=${tazpkg%-*}
	i=$package
	while true; do
		VERSION=""
		eval $(grep -s ^VERSION= $INSTALLED/$i/receipt)
		unset EXTRAVERSION
		eval $(grep -s ^EXTRAVERSION= $INSTALLED/$i/receipt)
		if [ "$i-$VERSION$EXTRAVERSION" = "$tazpkg" ]; then
			echo $i
			break
		fi
		case "$i" in
		*-*);;
		*) break;;
		esac
		i=${i%-*}
	done
}


# Check for the rootfs tree.
check_rootfs()
{
	if [ ! -d "$ROOTFS/etc" ] ; then
		echo -e "\nUnable to find a distro rootfs...\n"
		exit 0
	fi
}

# Check for the boot dir into the root CD tree.
verify_rootcd()
{
	if [ ! -d "$ROOTCD/boot" ] ; then
		echo -e "\nUnable to find the rootcd boot directory...\n"
		exit 0
	fi
}

create_iso()
{
	cd $2
	echo -n "Computing $SUM..."
	find * -type f ! -name $CHECKSUM -exec $CHECKSUM {} \; > $CHECKSUM
	sed -i  -e '/  boot\/isolinux\/isolinux.bin$/d' \
		-e '/  boot\/isolinux\/boot.cat$/d' $CHECKSUM
	status
	cd - > /dev/null
	newline
	echo -e "\033[1mGenerating ISO image\033[0m"
	separator
	echo "Generating $1"
	if [ $(ls $2/boot/vmlinuz* $2/boot/bzImage | wc -l) -eq 2 ]; then
		if cmp $2/boot/vmlinuz* $2/boot/bzImage > /dev/null; then
			rm -f $2/boot/bzImage
			ln $2/boot/vmlinuz* $2/boot/bzImage
		fi
	fi
	genisoimage -R -o $1 -b boot/isolinux/isolinux.bin \
 		-c boot/isolinux/boot.cat -no-emul-boot -boot-load-size 4 \
		-V "$VOLUM_NAME" -p "$PREPARED" -input-charset iso8859-1 \
		-boot-info-table $2
	if [ -x /usr/bin/isohybrid ]; then
		echo -n "Creating hybrid ISO..."
		/usr/bin/isohybrid $1 -entry 2 2> /dev/null
		status
	fi
	if [ -s /etc/slitaz/info ]; then
		if [ $(stat -c %s /etc/slitaz/info) -lt $(( 31*1024 )) ]; then
			echo -n "Storing ISO info..."
			dd if=/etc/slitaz/info bs=1k seek=1 of=$1 \
				conv=notrunc 2> /dev/null
			status
		fi
	fi
}

# Generate a new ISO image using isolinux.
gen_livecd_isolinux()
{
	# Some packages may want to alter iso
	genisohooks iso
	if [ ! -f "$ROOTCD/boot/isolinux/isolinux.bin" ]; then
		echo -e "\nUnable to find isolinux binary.\n"
		cleanup
		exit 0
	fi
	# Set date for boot msg.
	if grep -q 'XXXXXXXX' $ROOTCD/boot/isolinux/isolinux.*g; then
		DATE=`date +%Y%m%d`
		echo -n "Setting build date to: $DATE..."
		sed -i "s/XXXXXXXX/$DATE/" $ROOTCD/boot/isolinux/isolinux.*g
		status
	fi
	cd $DISTRO
	create_iso $ISO_NAME.iso $ROOTCD
	echo -n "Creating the ISO $CHECKSUM..."
	$CHECKSUM $ISO_NAME.iso > $ISO_NAME.$SUM
	status
	separator
	# Some packages may want to alter final iso
	genisohooks final
}

lzma_history_bits()
{
	#
	# This generates an ISO which boots with Qemu but gives
	# rootfs errors in frugal or liveUSB mode.
	#
	#local n
	#local sz
	#n=20	# 1Mb
	#sz=$(du -sk $1 | cut -f1)
	#while [ $sz -gt 1024 -a $n -lt 28 ]; do
		#n=$(( $n + 1 ))
		#sz=$(( $sz / 2 ))
	#done
	#echo $n
	echo 24
}

lzma_switches()
{
	local proc=$(grep -s '^processor' < /proc/cpuinfo | wc -l)
	echo "-d$(lzma_history_bits $1) -mt${proc:-1}"
}
lzma_set_size()
{
	# Update size field for lzma'd file packed using -si switch
	local n
	local i
	return # Need to fix kernel code ?
	n=$(unlzma -c $1 | wc -c)
	for i in $(seq 1 8); do
		printf '\\\\x%02X' $(($n & 255))
		n=$(($n >> 8))
	done | xargs echo -en | dd of=$1 conv=notrunc bs=1 seek=5 2> /dev/null
}

# Pack rootfs
pack_rootfs()
{
	( cd $1 ; find . -print | cpio -o -H newc ) | \
	if [ "$COMPRESSION" = "none" ]; then
		echo "Generating uncompressed initramfs... "
		cat > $2
	elif [ -x /usr/bin/lzma -a "$COMPRESSION" != "gzip" ]; then
		echo -n "Generating lzma'ed initramfs... "
		lzma e -si -so $(lzma_switches $1) > $2
		lzma_set_size $2
	else
		echo "Generating gziped initramfs... "
		gzip -9 > $2
	fi
	echo 1 > /tmp/rootfs
}

# Compression functions for writeiso.
write_initramfs()
{
	if [ "$COMPRESSION" = "lzma" ]; then
		echo -n "Creating $INITRAMFS with lzma compression... "
		cat /tmp/list | cpio -o -H newc | lzma e -si -so > /$INITRAMFS
		lzma_set_size /$INITRAMFS
	elif [ "$COMPRESSION" = "gzip" ]; then
		echo "Creating $INITRAMFS with gzip compression... "
		cat /tmp/list | cpio -o -H newc | gzip -9 > /$INITRAMFS
	else
		echo "Creating $INITRAMFS without compression... "
		cat /tmp/list | cpio -o -H newc > /$INITRAMFS
	fi
	echo 1 > /tmp/rootfs
}


# Deduplicate files (MUST be on the same filesystem).
deduplicate()
{
	find "$@" -type f -size +0c -exec stat -c '%s-%a-%u-%g %i %h %n' {} \; | \
	   sort | ( save=0; old_attr=""; old_inode=""; old_link=""; old_file=""
	   while read attr inode link file; do
	   	   [ -L "$file" ] && continue
		   if [ "$attr" = "$old_attr" -a "$inode" != "$old_inode" ]; then
			   if cmp "$file" "$old_file" >/dev/null 2>&1 ; then
				   rm -f "$file"
				   ln "$old_file" "$file"
				   inode="$old_inode"
				   [ "$link" = "1" ] && save="$(expr $save + ${attr%%-*})"
			   fi
		   fi
		   old_attr="$attr" ; old_inode="$inode" ; old_file="$file"
	   done
	   echo "$save bytes saved in duplicate files."
	)
}

# Generate a new initramfs from the root filesystem.
gen_initramfs()
{
	# Just in case CTRL+c
	rm -f $DISTRO/gen

	# Some packages may want to alter rootfs
	genisohooks rootfs
	cd $1

	# Link duplicate files
	deduplicate .

	# Use lzma if installed. Display rootfs size in realtime.
	rm -f /tmp/rootfs
	if [ "$MODULAR" ]; then
		pack_rootfs $INIT $DISTRO/$INITRAMFS &
	else
		pack_rootfs . $DISTRO/$(basename $1).gz &
	fi
	sleep 2
	echo -en "\nFilesystem size:"
	while [ ! -f /tmp/rootfs ]
	do
		sleep 1
		if [ "$MODULAR" ]; then
			echo -en "\\033[18G`du -sh $DISTRO/$INITRAMFS | awk '{print $1}'`    "
		else
			echo -en "\\033[18G`du -sh $DISTRO/$(basename $1).gz | awk '{print $1}'`    "
		fi
	done
	echo -e "\n"
	cd $DISTRO
	if [ $MODULAR ]; then
		mv $INITRAMFS $ROOTCD/boot
	else
		mv $(basename $1).gz $ROOTCD/boot
	fi
	if [ $MODULAR ]; then
		if [ $(mount | grep "tmpfs on $ROOTFS" 2>/dev/null) ]; then
			umount $ROOTFS
		fi
	fi
	
}

distro_sizes()
{
	if [ "$time" ]; then
		time=$(($(date +%s) - $time))
		sec=$time
		div=$(( ($time + 30) / 60))
		[ "$div" != 0 ] && min="~ ${div}m"
		echo "Build time      : ${sec}s $min"
	fi
	if [ "$MODULAR" ]; then
		PKGS_NUM=$(ls -1 $ROOTFS/modules/*$INSTALLED/*/receipt | wc -l)
	else
		PKGS_NUM=$(ls -1 $ROOTFS*$INSTALLED/*/receipt | wc -l)
	fi
	
echo "Build date       : $(date +%Y%m%d)"
if [ "$MODULAR" ]; then
	echo "Modular Packages : $PKGS_NUM"
	echo "Init Packages    : $(ls -1 $INIT*$INSTALLED/*/receipt | wc -l)"
	echo "Rootfs size      : $(du -csh $ROOTFS*/ | awk '{ s=$1 } END { print s }')"
else
	echo "Packages         : $PKGS_NUM"
	echo "Rootfs size      : $(du -csh $ROOTFS*/ | awk '{ s=$1 } END { print s }')"
fi

echo "Initramfs size   : $(du -csh $ROOTCD/boot/rootfs*.gz | awk '{ s=$1 } END { print s }')"
echo "ISO image size   : $(du -sh $ISO_NAME.iso | awk '{ print $1 }')"
echo "================================================================================"
echo "Image is ready: $ISO_NAME.iso"
}

# Print ISO and rootfs size.
distro_stats()
{
	newline
	echo -e "\033[1mDistro statistics\033[0m ($DISTRO)"
	separator
	distro_sizes
}

# Create an empty configuration file.
empty_config_file()
{
	cat >> cookiso.conf << "EOF"
# cookiso.conf: cookiso (SliTaz Live Tool)
# configuration file.
#

# Name of the ISO image to generate.
ISO_NAME=""

# ISO image volume name.
VOLUM_NAME="SliTaz"

# Name of the preparer.
PREPARED="$USER"

# Path to the packages repository and the packages.list.
PACKAGES_REPOSITORY=""

# Path to the distro tree to gen-distro from a
# list of packages.
DISTRO=""

# Path to the directory containing additional files
# to copy into the rootfs and rootcd of the LiveCD.
ADDFILES="$DISTRO/addfiles"

# Default answer for binary question (Y or N)
DEFAULT_ANSWER="ASK"

# Compression utility (lzma, gzip or none)
COMPRESSION="lzma"
EOF
}

# Display package list with version, set packed_size and unpacked_size
get_pkglist()
{
packed_size=0; unpacked_size=0
grep -v ^#  $FLAVORS_REPOSITORY/$1/packages.list > $TMP_DIR/flavor.pkg
while read pkg; do
	set -- $(get_size $pkg)
	packed_size=$(( $packed_size + $1 ))
	unpacked_size=$(( $unpacked_size + $2 ))
	for i in $(grep -hs ^$pkg $LOCALSTATE/packages.list \
				  $TMP_DIR/packages.list); do
		echo $i
		break
	done
done < $TMP_DIR/flavor.pkg
rm -f $TMP_DIR/flavor.pkg
}

human2cent()
{
case "$1" in
*k) echo $1 | sed 's/\(.*\).\(.\)k/\1\2/';;
*M) echo $(( $(echo $1 | sed 's/\(.*\).\(.\)M/\1\2/') * 1024));;
*G) echo $(( $(echo $1 | sed 's/\(.*\).\(.\)G/\1\2/') * 1024 * 1024));;
esac
}

cent2human()
{
if [ $1 -lt 10000 ]; then
  echo "$(($1 / 10)).$(($1 % 10))k"
elif [ $1 -lt 10000000 ]; then
  echo "$(($1 / 10240)).$(( ($1/1024) % 10))M"
else
  echo "$(($1 / 10485760)).$(( ($1/1048576) % 10))G"
fi
}

get_size()
{
cat $LOCALSTATE/packages.list $TMP_DIR/packages.list 2>/dev/null | awk "{ \
if (/^$(echo $1 | sed 's/[$+.\]/\\&/g')$/) get=1; \
if (/installed/ && get == 1) { print ; get++ } \
}
END { if (get < 2) print \" 0.0k  (0.0k installed)\" }" | \
sed 's/ *\(.*\) .\(.*\) installed./\1 \2/' | while read packed unpacked; do
  echo "$(human2cent $packed) $(human2cent $unpacked)"
done
}

# extract rootfs.gz somewhere
extract_rootfs()
{
	(zcat $1 || unlzma -c $1 || cat $1) 2>/dev/null | \
		(cd $2; cpio -idm > /dev/null)
}

# Remove duplicate files
mergefs()
{
	echo -n "Merge $(basename $1) ($(du -hs $1 | awk '{ print $1}')) into "
	echo -n       "$(basename $2) ($(du -hs $2 | awk '{ print $1}'))"
	# merge symlinks files and devices
	( cd $1; find ) | while read file; do
		if [ -L $1/$file ]; then
			[ -L $2/$file ] &&
			[ "$(readlink $1/$file)" == "$(readlink $2/$file)" ] &&
			rm -f $2/$file
		elif [ -f $1/$file ]; then
			[ -f $2/$file ] &&
			cmp $1/$file $2/$file > /dev/null 2>&1 && rm -f $2/$file
			[ -f $2/$file ] &&
			[ "$(basename $file)" == "volatile.cpio.gz" ] &&
			[ "$(dirname $(dirname $file))" == \
			  ".$INSTALLED" ] && rm -f $2/$file
		elif [ -b $1/$file ]; then
			[ -b $2/$file ] &&
			[ "$(stat -c '%a:%u:%g:%t:%T' $1/$file)" == \
			  "$(stat -c '%a:%u:%g:%t:%T' $2/$file)" ] &&
			rm -f $2/$file
		elif [ -c $1/$file ]; then
			[ -c $2/$file ] &&
			[ "$(stat -c '%a:%u:%g:%t:%T' $1/$file)" == \
			  "$(stat -c '%a:%u:%g:%t:%T' $2/$file)" ] &&
			rm -f $2/$file
		fi
	done

	# cleanup directories
	( cd $1; find -type d ) | sed '1!G;h;$!d' | while read file; do
		[ -d $2/$file ] && rmdir $2/$file 2> /dev/null
	done
	true
	status
}

cleanup_merge()
{
	rm -rf $TMP_DIR
	exit 1
}

# tazlito gen-distro
gen_distro()
{
	check_root
	time=$(date +%s)

	# Check if a package list was specified on cmdline.
	DISTRO_LIST="distro-packages.list"
	LIST_NAME="$DISTRO_LIST"
	unset CDROM
	while [ -n "$1" ]; do
		case "$1" in
		--iso=*)
			CDROM="-o loop ${2#--iso=}"
			;;
		--cdrom)
			CDROM="/dev/cdrom"
			;;
		--force)
			DELETE_ROOTFS="true"
			;;
		*)	if [ ! -f "$1" ] ; then
				echo -e "\nUnable to find the specified packages list."
				echo -e "List name : $1\n"
				exit 1
			fi
			LIST_NAME=$1
			;;
		esac
		shift
	done

	if [ -d $ROOTFS ] ; then
		# Delete $ROOTFS if --force is set on command line
		if [ ! -z $DELETE_ROOTFS ]; then
			rm -rf $ROOTFS
			unset $DELETE_ROOTFS
		else
			echo -e "\nA rootfs exists in : $DISTRO"
			echo -e "Please clean the distro tree or change directory path.\n"
			exit 0
		fi
	fi
	if [ ! -f "$LIST_NAME" -a -d $INSTALLED ] ; then
		# Build list with installed packages
		for i in $(ls $INSTALLED); do
			eval $(grep ^VERSION= $INSTALLED/$i/receipt)
			EXTRAVERSION=""
			eval $(grep ^EXTRAVERSION= $INSTALLED/$i/receipt)
			echo "$i-$VERSION$EXTRAVERSION" >> $LIST_NAME
		done
	fi
	# Exit if no list name.
	if [ ! -f "$LIST_NAME" ]; then
		echo -e "\nNo packages list found or specified. Please read the docs.\n"
		exit 0
	fi
	# Start generation.
	newline
	echo -e "\033[1mGenerating a distro\033[0m"
	separator
	# Misc checks
	[ -n "$PACKAGES_REPOSITORY" ] || PACKAGES_REPOSITORY="."
	[ -d $PACKAGES_REPOSITORY ] || mkdir -p $PACKAGES_REPOSITORY
	# Get the list of packages using cat for a file list.
	LIST=$(cat $LIST_NAME)
	# Verify if all packages in list are present in $PACKAGES_REPOSITORY.
	unset REPACK DOWNLOAD
	for pkg in $LIST
	do
		[ "$pkg" = "" ] && continue
		pkg=${pkg%.tazpkg}
		[ -f $PACKAGES_REPOSITORY/$pkg.tazpkg ] && continue
		PACKAGE=$(installed_package_name $pkg)
		[ -n "$PACKAGE" -a "$REPACK" = "y" ] && continue
		[ -z "$PACKAGE" -a -n "$DOWNLOAD" ] && continue
		echo -e "\nUnable to find $pkg in the repository."
		echo -e "Path : $PACKAGES_REPOSITORY\n"
		if [ -n "$PACKAGE" -a -z "$REPACK" ]; then
			yesorno "Repack packages from rootfs (y/N) ? "
			REPACK="$answer"
			[ "$answer" = "y" ] || REPACK="n"
			[ "$DOWNLOAD" = "y" ] && break
		fi
		if [ -f $MIRROR -a -z "$DOWNLOAD" ]; then
			yesorno "Download packages from mirror (Y/n) ? "
			DOWNLOAD="$answer"
			if [ "$answer" = "n" ]; then
				[ -z "$PACKAGE" ] && exit 1
			else
				DOWNLOAD="y"
				[ -n "$REPACK" ] && break
			fi
		fi
		[ "$REPACK" = "n" -a "$DOWNLOAD" = "n" ] && exit 1
	done

	# Mount cdrom to be able to repack boot-loader packages
	if [ ! -e /boot -a -n "$CDROM" ]; then
		mkdir $TMP_MNT
		if mount -r $CDROM $TMP_MNT 2> /dev/null; then
			ln -s $TMP_MNT/boot /
			if [ ! -d "$ADDFILES/rootcd" ] ; then
				mkdir -p $ADDFILES/rootcd
				for i in $(ls $TMP_MNT); do
					[ "$i" = "boot" ] && continue
					cp -a $TMP_MNT/$i $ADDFILES/rootcd
				done
			fi
		else
			rmdir $TMP_MNT
		fi
	fi

	# Root fs stuff.
	echo "Preparing the rootfs directory..."
	mkdir -p $ROOTFS
	for pkg in $LIST
	do
		[ "$pkg" = "" ] && continue
		# First copy and extract the package in tmp dir.
		pkg=${pkg%.tazpkg}
		PACKAGE=$(installed_package_name $pkg)
		mkdir -p $TMP_DIR
		if [ ! -f $PACKAGES_REPOSITORY/$pkg.tazpkg ]; then
			# Look for package in cache
			if [ -f $CACHE_DIR/$pkg.tazpkg ]; then
				ln -s $CACHE_DIR/$pkg.tazpkg $PACKAGES_REPOSITORY
			# Look for package in running distribution
			elif [ -n "$PACKAGE" -a "$REPACK" = "y" ]; then
				tazpkg repack $PACKAGE && \
				  mv $pkg.tazpkg $PACKAGES_REPOSITORY
			fi
		fi
		if [ ! -f $PACKAGES_REPOSITORY/$pkg.tazpkg ]; then
			# Get package from mirror
			[ "$DOWNLOAD" = "y" ] && \
			download $pkg.tazpkg && \
			mv $pkg.tazpkg $PACKAGES_REPOSITORY
		fi
		if [ ! -f $PACKAGES_REPOSITORY/$pkg.tazpkg ]; then
			echo "Missing package $pkg."
			cleanup
			exit 1
		fi
	done
	if [ -f non-free.list ]; then
		echo "Preparing non-free packages..."
		cp non-free.list $ROOTFS/etc/slitaz/non-free.list
		for pkg in $(cat non-free.list); do
			if [ ! -d $INSTALLED/$pkg ]; then
				if [ ! -d $INSTALLED/get-$pkg ]; then
					tazpkg get-install get-$pkg
				fi
				get-$pkg
			fi
			tazpkg repack $pkg
			pkg=$(ls $pkg*.tazpkg)
			grep -q "^$pkg$" $LIST_NAME || \
				echo $pkg >>$LIST_NAME
			mv $pkg $PACKAGES_REPOSITORY
			done
	fi
	cp $LIST_NAME $DISTRO/$DISTRO_LIST
	if [ "$MODULAR" ]; then
		union
	else
		sed 's/\(.*\)/\1.tazpkg/' < $DISTRO/$DISTRO_LIST > $DISTRO/list-packages
		cd $PACKAGES_REPOSITORY
		for pkg in $(cat $DISTRO/list-packages)
		do
			echo -n "Installing package: $pkg"
			yes y | tazpkg install $pkg --root=$ROOTFS 2>/dev/null >> $log || exit 1
			status
		done
		rm -f $ROOTFS/$DB/packages.*
	fi

	cd $DISTRO
	if [ "$MODULAR" ]; then
		cp $DISTRO_LIST $INIT/etc/slitaz
	else
		cp $DISTRO_LIST $ROOTFS/etc/slitaz
	fi
	# Copy all files from $ADDFILES/rootfs to the rootfs.
	if [ -d "$ADDFILES/rootfs" ] ; then
		echo -n "Copying addfiles content to the rootfs... "
		cp -a $ADDFILES/rootfs/* $ROOTFS
		status
	fi
	echo -n "Root filesystem is generated..." && status
	# Root CD part.
	echo -n "Preparing the rootcd directory..."
	mkdir -p $ROOTCD
	status
	# Move the boot dir with the Linux kernel from rootfs.
	# The boot dir goes directly on the CD.
	if [ $MODULAR ]; then
		if [ -d "$INIT/boot" ]; then
			echo -n "Moving the boot directory..."
			mv $INIT/boot $ROOTCD
			cd $ROOTCD/boot
			ln vmlinuz-* bzImage
			status
		elif [ -d "$ROOTFS/boot" ] ; then
			echo -n "Moving the boot directory..."
			mv $ROOTFS/boot $ROOTCD
			cd $ROOTCD/boot
			ln vmlinuz-* bzImage
			status
		fi
	fi
	cd $DISTRO
	# Copy all files from $ADDFILES/rootcd to the rootcd.
	if [ -d "$ADDFILES/rootcd" ] ; then
		echo -n "Copying addfiles content to the rootcd... "
		cp -a $ADDFILES/rootcd/* $ROOTCD
		status
	fi
	# Execute the distro script used to perform tasks in the rootfs
	# before compression. Give rootfs path in arg
	[ -z $DISTRO_SCRIPT ] && DISTRO_SCRIPT=$TOP_DIR/distro.sh
	if [ -x $DISTRO_SCRIPT ]; then
		echo "Executing distro script..."
		sh $DISTRO_SCRIPT $DISTRO
	fi
	if [ -s /etc/slitaz/rootfs.list ]; then
		FLAVOR_LIST="$(awk '{ for (i = 2; i <= NF; i+=2) \
		  printf("%s ",$i) }' < /etc/slitaz/rootfs.list)"
		sed -i "s/ *//;s/)/), flavors $FLAVOR_LIST/" \
		  $ROOTCD/boot/isolinux/isolinux.msg 2> /dev/null
		[ -f $ROOTCD/boot/isolinux/ifmem.c32 ] ||
		cp /boot/isolinux/ifmem.c32 $ROOTCD/boot/isolinux
		n=0
		last=$ROOTFS
		while read flavor; do
			n=$(($n+1))
			echo "Building $flavor rootfs..."
			if [ -d $flavors/$flavor ]; then
				cp -a $flavors
				[ -s $TOP_DIR/$flavor.flavor ] &&
					cp $TOP_DIR/$flavor.flavor .
				[ -s $flavor.flavor ] || download $flavor.flavor
				zcat $flavor.flavor | cpio -i \
					$flavor.pkglist $flavor.rootfs
				sed 's/.*/&.tazpkg/' < $flavor.pkglist \
					> $DISTRO/list-packages0$n
				mkdir ${ROOTFS}0$n
				cd $PACKAGES_REPOSITORY
				yes y | tazpkg install-list \
					$DISTRO/list-packages0$n --root=${ROOTFS}0$n 2>/dev/null
				rm -rf ${ROOTFS}0$n/boot ${ROOTFS}0$n/$DB/packages.*
				status
				cd $DISTRO
				if [ -s $flavor.rootfs ]; then
					echo "Adding $flavor rootfs extra files..."
					zcat $flavor.rootfs | \
					( cd ${ROOTFS}0$n ; cpio -idmu )
				fi
				mv $flavor.pkglist ${ROOTFS}0$n/etc/slitaz/$DISTRO_LIST
				rm -f $flavor.flavor install-list
				mergefs ${ROOTFS}0$n $last
				last=${ROOTFS}0$n
			fi
		done <<EOT
$(awk '{ for (i = 4; i <= NF; i+=2) print $i; }' < /etc/slitaz/rootfs.list)
EOT
		i=$(($n+1))
		while [ $n -gt 0 ]; do
			mv ${ROOTFS}0$n ${ROOTFS}$i
			echo "Compression ${ROOTFS}0$n ($(du -hs ${ROOTFS}$i | awk '{ print $1 }')) ..."
			gen_initramfs ${ROOTFS}$i
			n=$(($n-1))
			i=$(($i-1))
		done
		mv $ROOTFS ${ROOTFS}$i
		gen_initramfs ${ROOTFS}$i
		update_bootconfig $ROOTCD/boot/isolinux \
			"$(cat /etc/slitaz/rootfs.list)"
	else
		# Initramfs and ISO image stuff.
		gen_initramfs $ROOTFS
	fi
	gen_livecd_isolinux
	distro_stats
	cleanup
}

# tazlito gen-flavor
gen_flavor()
{
	# Generate a new flavor from the last iso image generated.
	FLAVOR=${1%.flavor}
	newline
	echo -e "\033[1mFlavor generation\033[0m"
	separator
	if [ -z "$FLAVOR" ]; then
		echo -n "Flavor name : "
		read FLAVOR
		[ -z "$FLAVOR" ] && exit 1
	fi
	check_rootfs
	FILES="$FLAVOR.pkglist"
	echo -n "Creating file $FLAVOR.flavor..."
	for i in rootcd rootfs; do
		if [ -d "$ADDFILES/$i" ] ; then
			FILES="$FILES\n$FLAVOR.$i"
			( cd "$ADDFILES/$i"; find . | \
			  cpio -o -H newc 2> /dev/null | gzip -9 ) > $FLAVOR.$i
		fi
	done
	status
	answer=`grep -s ^Description $FLAVOR.desc`
	answer=${answer#Description     : }
	if [ -z "$answer" ]; then
		echo -n "Description : "
		read answer
	fi
	echo -n "Compressing flavor $FLAVOR..."
	echo "Flavor          : $FLAVOR" > $FLAVOR.desc
	echo "Description     : $answer" >> $FLAVOR.desc
	( cd $DISTRO; distro_sizes) >> $FLAVOR.desc
	\rm -f $FLAVOR.pkglist $FLAVOR.nonfree 2> /dev/null
	for i in $(ls $ROOTFS$INSTALLED); do
		eval $(grep ^VERSION= $ROOTFS$INSTALLED/$i/receipt)
		EXTRAVERSION=""
		eval $(grep ^EXTRAVERSION= $ROOTFS$INSTALLED/$i/receipt)
		eval $(grep ^CATEGORY= $ROOTFS$INSTALLED/$i/receipt)
		if [ "$CATEGORY" = "non-free" -a "${i%%-*}" != "get" ]
		then
			echo "$i" >> $FLAVOR.nonfree
		else
			echo "$i-$VERSION$EXTRAVERSION" >> $FLAVOR.pkglist
		fi
	done
	[ -s $FLAVOR.nonfree ] && $FILES="$FILES\n$FLAVOR.nonfree"
	for i in $LOCALSTATE/undigest/*/mirror ; do
		[ -s $i ] && cat $i >> $FLAVOR.mirrors
	done
	[ -s $FLAVOR.mirrors ] && $FILES="$FILES\n$FLAVOR.mirrors"
	echo -e "$FLAVOR.desc\n$FILES" | cpio -o -H newc 2>/dev/null | \
		gzip -9 > $FLAVOR.flavor
	rm `echo -e $FILES`
	status
	separator
	echo "Flavor size : `du -sh $FLAVOR.flavor`"
	newline
}

# tazlito get-flavor
get_flavor()
{
	# Get a flavor's files and prepare for gen-distro.
	FLAVOR=${1%.flavor}
	echo -e "\n\033[1mPreparing $FLAVOR distro flavor\033[0m"
	separator
	if [ -f $FLAVOR.flavor ] || download $FLAVOR.flavor; then
		echo -n "Cleaning $DISTRO..."
		rm -R $DISTRO 2> /dev/null
		mkdir -p $DISTRO
		status
		mkdir $TMP_DIR
		echo -n "Extracting flavor $FLAVOR.flavor... "
		zcat $FLAVOR.flavor | ( cd $TMP_DIR; cpio -i >/dev/null )
		status
		echo -n "Creating distro-packages.list..."
		mv $TMP_DIR/$FLAVOR.nonfree non-free.list 2> /dev/null
		mv $TMP_DIR/$FLAVOR.pkglist distro-packages.list
		status
		if [ -f "$TMP_DIR/$FLAVOR-distro.sh" ]; then
			echo -n "Extracting distro.sh... "
			mv $TMP_DIR/$FLAVOR-distro.sh  distro.sh 2> /dev/null
			status
		fi
		infos="$FLAVOR.desc"
		for i in rootcd rootfs; do
			if [ -f $TMP_DIR/$FLAVOR.$i ]; then
				echo -n "Adding $i files... "
				mkdir -p "$ADDFILES/$i"
				zcat $TMP_DIR/$FLAVOR.$i | \
					( cd "$ADDFILES/$i"; cpio -id > /dev/null)
				zcat $TMP_DIR/$FLAVOR.$i | cpio -tv 2> /dev/null \
					> $TMP_DIR/$FLAVOR.list$i
				infos="$infos\n$FLAVOR.list$i"
				status
			fi
		done
		if [ -s $TMP_DIR/$FLAVOR.mirrors ]; then
			n=""
			while read line; do
				mkdir -p $LOCALSTATE/undigest/$FLAVOR$n
				echo "$line" > $LOCALSTATE/undigest/$FLAVOR$n/mirror
				n=$(( $n + 1 ))
			done < $TMP_DIR/$FLAVOR.mirrors
			infos="$infos\n$FLAVOR.mirrors"
			tazpkg recharge
		fi
		rm -f /etc/slitaz/rootfs.list
		grep -q '^Rootfs list' $TMP_DIR/$FLAVOR.desc &&
			grep '^Rootfs list' $TMP_DIR/$FLAVOR.desc | \
			sed 's/.*: \(.*\)$/\1/' > /etc/slitaz/rootfs.list
		echo -n "Updating cookiso.conf..."
		[ -f cookiso.conf ] || cp /etc/slitaz/cookiso.conf .
		cat cookiso.conf | grep -v "^#VOLUM_NAME" | \
		sed "s/^VOLUM_NA/VOLUM_NAME=\"SliTaz $FLAVOR\"\\n#VOLUM_NA/" \
			> cookiso.conf.$$ && mv cookiso.conf.$$ cookiso.conf
		sed -i "s/ISO_NAME=.*/ISO_NAME=\"slitaz-$FLAVOR\"/" cookiso.conf
		status
		( cd $TMP_DIR ; echo -e $infos | cpio -o -H newc ) | \
			gzip -9 > /etc/slitaz/info
		rm -Rf $TMP_DIR
	fi
	separator
	echo -e "Flavor is ready to be generated by: cookiso gen-distro\n"
}

# tazlito clean-distro
clean_distro()
{
	# Remove old distro tree.
	#
	check_root
	newline
	boldify "Cleaning : $DISTRO"
	separator
	if [ -d "$DISTRO" ] ; then
		if [ -d "$ROOTFS" ] ; then
			echo -n "Removing the rootfs..."
			rm -f $DISTRO/$INITRAMFS
			rm -rf $ROOTFS
			status
		fi
		if [ -d "$ROOTCD" ] ; then
			echo -n "Removing the rootcd..."
			rm -rf $ROOTCD
			status
		fi
		echo -n "Removing eventual ISO image..."
		rm -f $DISTRO/$ISO_NAME.iso
		rm -f $DISTRO/$ISO_NAME.$SUM
		status
	fi
	separator
	newline
}

# tazlito pack-flavor
pack_flavor()
{
	# Create a flavor from $FLAVORS_REPOSITORY.
	FLAVOR=${1%.flavor}
	if [ -s $FLAVORS_REPOSITORY/$FLAVOR/receipt ]; then
		mkdir $TMP_DIR
		echo -n "Creating flavor $FLAVOR..."
		[ -s $LOCALSTATE/packages.list ] || tazpkg recharge
		if [ -s $FLAVORS_REPOSITORY/$FLAVOR/mirrors ]; then
			cp $FLAVORS_REPOSITORY/$FLAVOR/mirrors \
				$TMP_DIR/$FLAVOR.mirrors
			for i in $(cat $TMP_DIR/$FLAVOR.mirrors); do
				wget -O - $i/packages.list >> $TMP_DIR/packages.list
			done
		fi
		#add distro;sh if exist
		if [ -s $FLAVORS_REPOSITORY/$FLAVOR/distro.sh ]; then
			cp $FLAVORS_REPOSITORY/$FLAVOR/distro.sh $TMP_DIR/$FLAVOR-distro.sh
		fi
		[ -s $FLAVORS_REPOSITORY/$FLAVOR/packages.list ] &&
		get_pkglist $FLAVOR > $TMP_DIR/$FLAVOR.pkglist
		if grep -q ^ROOTFS_SELECTION \
			$FLAVORS_REPOSITORY/$FLAVOR/receipt; then
			. $FLAVORS_REPOSITORY/$FLAVOR/receipt
			set -- $ROOTFS_SELECTION
			[ -n "$FRUGAL_RAM" ] || FRUGAL_RAM=$1
			[ -f $FLAVORS_REPOSITORY/$2/packages.list ] ||
			extract_flavor $2
			get_pkglist $2 > $TMP_DIR/$FLAVOR.pkglist
			for i in rootcd rootfs; do
				mkdir $TMP_DIR/$i
				# Copy extra files from the first flavor
				[ -d $FLAVORS_REPOSITORY/$2/$i ] &&
				cp -a $FLAVORS_REPOSITORY/$2/$i $TMP_DIR
				# Overload extra files by meta flavor
				[ -d $FLAVORS_REPOSITORY/$FLAVOR/$i ] &&
				cp -a $FLAVORS_REPOSITORY/$FLAVOR/$i $TMP_DIR
				[ -n "$(ls $TMP_DIR/$i)" ] &&
				( cd $TMP_DIR/$i ; find . | cpio -o -H newc 2> /dev/null ) | \
				gzip -9 >$TMP_DIR/$FLAVOR.$i
				rm -rf $TMP_DIR/$i
			done
		else
			for i in rootcd rootfs; do
				[ -d $FLAVORS_REPOSITORY/$FLAVOR/$i ] || \
					continue
				( cd $FLAVORS_REPOSITORY/$FLAVOR/$i ; \
				find . | cpio -o -H newc 2> /dev/null ) | \
				gzip -9 >$TMP_DIR/$FLAVOR.$i
			done
		fi
		if [ -s $TMP_DIR/$FLAVOR.rootfs ]; then
			packed_size=$(($packed_size \
				+ $(cat $TMP_DIR/$FLAVOR.rootfs | wc -c ) / 100 ))
			unpacked_size=$(($unpacked_size \
				+ $(zcat $TMP_DIR/$FLAVOR.rootfs | wc -c ) / 100 ))
		fi
		# Estimate lzma
		packed_size=$(($packed_size * 2 / 3))
		iso_size=$(( $packed_size + 26000 ))
		if [ -s $TMP_DIR/$FLAVOR.rootcd ]; then
			iso_size=$(($iso_size \
				+ $(zcat $TMP_DIR/$FLAVOR.rootcd | wc -c ) / 100 ))
		fi
		VERSION=""
		MAINTAINER=""
		ROOTFS_SELECTION=""
		ROOTFS_SIZE="$(cent2human $unpacked_size) (estimated)"
		INITRAMFS_SIZE="$(cent2human $packed_size) (estimated)"
		ISO_SIZE="$(cent2human $iso_size) (estimated)"
		. $FLAVORS_REPOSITORY/$FLAVOR/receipt
		cat > $TMP_DIR/$FLAVOR.desc <<EOT
Flavor          : $FLAVOR
Description     : $SHORT_DESC
EOT
		[ -n "$VERSION" ] && cat >> $TMP_DIR/$FLAVOR.desc <<EOT
Version         : $VERSION
EOT
		[ -n "$MAINTAINER" ] && cat >> $TMP_DIR/$FLAVOR.desc <<EOT
Maintainer      : $MAINTAINER
EOT
		[ -n "$FRUGAL_RAM" ] && cat >> $TMP_DIR/$FLAVOR.desc <<EOT
LiveCD RAM size : $FRUGAL_RAM
EOT
		[ -n "$ROOTFS_SELECTION" ] && cat >> $TMP_DIR/$FLAVOR.desc <<EOT
Rootfs list     : $ROOTFS_SELECTION
EOT
		cat >> $TMP_DIR/$FLAVOR.desc <<EOT
Build date      : $(date +%Y%m%d\ \at\ \%H:%M:%S)
Packages        : $(grep -v ^# $TMP_DIR/$FLAVOR.pkglist | wc -l)
Rootfs size     : $ROOTFS_SIZE
Initramfs size  : $INITRAMFS_SIZE
ISO image size  : $ISO_SIZE
================================================================================

EOT
		rm -f $TMP_DIR/packages.list
		( cd $TMP_DIR ; ls | cpio -o -H newc 2> /dev/null) | \
			gzip -9 > $FLAVOR.flavor
		status
		rm -Rf $TMP_DIR
	else
		echo "No $FLAVOR flavor in $FLAVORS_REPOSITORY."
	fi
}

# tazlito extract-flavor
extract_flavor()
{
	# Extract a flavor into $FLAVORS_REPOSITORY.
	FLAVOR=${1%.flavor}
	if [ -f $FLAVOR.flavor ] || download $FLAVOR.flavor; then
		mkdir $TMP_DIR
		zcat $FLAVOR.flavor | ( cd $TMP_DIR; cpio -i >/dev/null )
		echo -n "Extracting $FLAVOR..."
		rm -rf $FLAVORS_REPOSITORY/$FLAVOR 2> /dev/null
		mkdir -p $FLAVORS_REPOSITORY/$FLAVOR
		echo "FLAVOR=\"$FLAVOR\"" > $FLAVORS_REPOSITORY/$FLAVOR/receipt
		grep ^Description $TMP_DIR/$FLAVOR.desc | \
			sed 's/.*: \(.*\)$/SHORT_DESC="\1"/' >> \
			$FLAVORS_REPOSITORY/$FLAVOR/receipt
		grep ^Version $TMP_DIR/$FLAVOR.desc | \
			sed 's/.*: \(.*\)$/VERSION="\1"/' >> \
			$FLAVORS_REPOSITORY/$FLAVOR/receipt
		grep ^Maintainer $TMP_DIR/$FLAVOR.desc | \
			sed 's/.*: \(.*\)$/MAINTAINER="\1"/' >> \
			$FLAVORS_REPOSITORY/$FLAVOR/receipt
		grep -q '^Rootfs list' $TMP_DIR/$FLAVOR.desc && \
		grep '^Rootfs list' $TMP_DIR/$FLAVOR.desc | \
			sed 's/.*: \(.*\)$/ROOTFS_SELECTION="\1"/' >> \
			$FLAVORS_REPOSITORY/$FLAVOR/receipt
		grep '^Rootfs size' $TMP_DIR/$FLAVOR.desc | \
			sed 's/.*: \(.*\)$/ROOTFS_SIZE="\1"/' >> \
			$FLAVORS_REPOSITORY/$FLAVOR/receipt
		grep ^Initramfs $TMP_DIR/$FLAVOR.desc | \
			sed 's/.*: \(.*\)$/INITRAMFS_SIZE="\1"/' >> \
			$FLAVORS_REPOSITORY/$FLAVOR/receipt
		grep ^ISO $TMP_DIR/$FLAVOR.desc | \
			sed 's/.*: \(.*\)$/ISO_SIZE="\1"/' >> \
			$FLAVORS_REPOSITORY/$FLAVOR/receipt
		for i in rootcd rootfs; do
			[ -f $TMP_DIR/$FLAVOR.$i ] || continue
			mkdir $FLAVORS_REPOSITORY/$FLAVOR/$i
			zcat $TMP_DIR/$FLAVOR.$i | \
				(cd $FLAVORS_REPOSITORY/$FLAVOR/$i; \
			cpio -idm > /dev/null)
		done
		[ -s $TMP_DIR/$FLAVOR.mirrors ] &&
			cp $TMP_DIR/$FLAVOR.mirrors \
				$FLAVORS_REPOSITORY/$FLAVOR/mirrors
		[ -s $LOCALSTATE/packages.list ] || tazpkg recharge
		while read org; do
			i=0
			pkg=$org
			while ! grep -q ^$pkg$ $LOCALSTATE/packages.txt; do
				pkg=${pkg%-*}
				i=$(($i + 1))
				[ $i -gt 5 ] && break;
			done
			echo $pkg
		done <  $TMP_DIR/$FLAVOR.pkglist \
			> $FLAVORS_REPOSITORY/$FLAVOR/packages.list
		status
		rm -Rf $TMP_DIR
	fi
}

# tazlito show-flavor
show_flavor()
{
	# Show flavor description.
	FLAVOR=${1%.flavor}
	if [ ! -f "$FLAVOR.flavor" ]; then
		echo "File $FLAVOR.flavor not found."
		exit 1
	fi
	mkdir $TMP_DIR
	zcat $FLAVOR.flavor | ( cd $TMP_DIR; cpio -i > /dev/null)
	if [ "$2" = "--brief" ]; then
		if [ "$3" != "--noheader" ]; then
			echo "Name              ISO   Rootfs  Description"
			separator
		fi
		printf "%-16.16s %6.6s %6.6s %s\n" "$FLAVOR" \
			"$(field ISO $TMP_DIR/$FLAVOR.desc)" \
			"$(field 'Rootfs size' $TMP_DIR/$FLAVOR.desc)" \
			"$(grep ^Description $TMP_DIR/$FLAVOR.desc | cut -d: -f2)"
	else
		separator
		cat $TMP_DIR/$FLAVOR.desc
	fi
	rm -Rf $TMP_DIR
}

# tazlito list-flavors
list_flavors()
{
	# Show available flavors.
	if [ ! -s /tmp/flavors.list -o "$2" == "--recharge" ]; then
		download flavors.list -O - > /tmp/flavors.list
	fi
	newline
	echo -e "\033[1mList of flavors\033[0m"
	separator
	cat /tmp/flavors.list
	newline
}

# tazlito extract-distro
extract_distro()
{
	# Extract an ISO image to a directory and rebuild the LiveCD tree.
	#
	check_root
	ISO_IMAGE=$1
	if [ -z "$ISO_IMAGE" ] ; then
		echo -e "\nPlease specify the path to the ISO image."
		echo -e "Example : `basename $0` image.iso /path/target\n"
		exit 0
	fi
	# Set the distro path by checking for $3 on cmdline.
	if [ -n "$2" ] ; then
		TARGET=$2
	else
		TARGET=$DISTRO
	fi
	# Exit if existing distro is found.
	if [ -d "$TARGET/rootfs" ] ; then
		echo -e "\nA rootfs exists in : $TARGET"
		echo -e "Please clean the distro tree or change directory path.\n"
		exit 0
	fi
	newline
	echo -e "\033[1mExtracting :\033[0m `basename $ISO_IMAGE`"
	separator
	# Start to mount the ISO.
	newline
	echo "Mounting ISO image..."
	mkdir -p $TMP_DIR
	# Get ISO file size.
	isosize=$(du -sh $ISO_IMAGE | cut -f1)
	mount -o loop $ISO_IMAGE $TMP_DIR
	sleep 2
	# Prepare target dir, copy the kernel and the rootfs.
	mkdir -p $TARGET/rootfs
	mkdir -p $TARGET/rootcd/boot
	echo -n "Copying the Linux kernel..."
	if cp $TMP_DIR/boot/vmlinuz* $TARGET/rootcd/boot 2> /dev/null; then
		ln $TARGET/rootcd/boot/vmlinuz* $TARGET/rootcd/boot/bzImage
	else
		cp $TMP_DIR/boot/bzImage $TARGET/rootcd/boot
	fi
	status
	echo -n "Copying isolinux files..."
	cp -a $TMP_DIR/boot/isolinux $TARGET/rootcd/boot
	for i in $(ls $TMP_DIR); do
		[ "$i" = "boot" ] && continue
		cp -a $TMP_DIR/$i $TARGET/rootcd
	done
	status
	if [ -d $TMP_DIR/boot/syslinux ]; then
		echo -n "Copying syslinux files..."
		cp -a $TMP_DIR/boot/syslinux $TARGET/rootcd/boot
		status
	fi
	if [ -d $TMP_DIR/boot/extlinux ]; then
		echo -n "Copying extlinux files..."
		cp -a $TMP_DIR/boot/extlinux $TARGET/rootcd/boot
		status
	fi
	if [ -d $TMP_DIR/boot/grub ]; then
		echo -n "Copying GRUB files..."
		cp -a $TMP_DIR/boot/grub $TARGET/rootcd/boot
		status
	fi
	echo -n "Copying the rootfs..."
	cp $TMP_DIR/boot/$INITRAMFS $TARGET/rootcd/boot
	status
	# Extract initramfs.
	cd $TARGET/rootfs
	echo -n "Extracting the rootfs... "
	extract_rootfs $TARGET/rootfs/rootcd/boot/$INITRAMFS $TARGET/rootfs
	# unpack /usr
	for i in etc/slitaz/*.extract; do
		[ -f "$i" ] && . $i ../rootcd
	done
	# Umount and remove temp directory and cd to $TARGET to get stats.
	umount $TMP_DIR && rm -rf $TMP_DIR
	cd ..
	newline
	separator
	echo "Extracted       : `basename $ISO_IMAGE` ($isosize)"
	echo "Distro tree     : `pwd`"
	echo "Rootfs size     : `du -sh rootfs`"
	echo "Rootcd size     : `du -sh rootcd`"
	separator
	newline
}

# tazlito update-flavor
update_flavor()
{
	# Update package list to the latest versions available.
	FLAVOR=${1%.flavor}
	if [ -f $FLAVOR.flavor ] || download $FLAVOR.flavor; then
		mkdir $TMP_DIR
		zcat $FLAVOR.flavor | ( cd $TMP_DIR; cpio -i >/dev/null )
		echo -n "Updating $FLAVOR package list..."
		[ -s $LOCALSTATE/packages.list ] || tazpkg recharge
		packed_size=0; unpacked_size=0
		while read org; do
			i=0
			pkg=$org
			while ! grep -q ^$pkg$ $LOCALSTATE/packages.txt; do
				pkg=${pkg%-*}
				i=$(($i + 1))
				[ $i -gt 5 ] && break;
			done
			set -- $(get_size $pkg)
			packed_size=$(( $packed_size + $1 ))
			unpacked_size=$(( $unpacked_size + $2 ))
			for i in $(grep ^$pkg $LOCALSTATE/packages.list); do
				echo $i
				break
			done
		done <  $TMP_DIR/$FLAVOR.pkglist \
			> $TMP_DIR/$FLAVOR.pkglist.$$
		mv -f $TMP_DIR/$FLAVOR.pkglist.$$ $TMP_DIR/$FLAVOR.pkglist
		if [ -s $TMP_DIR/$FLAVOR.rootfs ]; then
			packed_size=$(($packed_size \
				+ $(cat $TMP_DIR/$FLAVOR.rootfs | wc -c ) / 100 ))
			unpacked_size=$(($unpacked_size \
				+ $(zcat $TMP_DIR/$FLAVOR.rootfs | wc -c ) / 100 ))
		fi
		# Estimate lzma
		packed_size=$(($packed_size * 2 / 3))
		iso_size=$(( $packed_size + 26000 ))
		if [ -s $TMP_DIR/$FLAVOR.rootcd ]; then
			iso_size=$(($iso_size \
				+ $(zcat $TMP_DIR/$FLAVOR.rootcd | wc -c ) / 100 ))
		fi
		sed -i -e '/Image is ready/d' \
			-e "s/Rootfs size\( *:\) \(.*\)/Rootfs size\1 $(cent2human $unpacked_size)  (estimated)/" \
			-e "s/Initramfs size\( *:\) \(.*\)/Initramfs size\1 $(cent2human $packed_size)  (estimated)/" \
			-e "s/ISO image size\( *:\) \(.*\)/ISO image size\1 $(cent2human $iso_size)  (estimated)/" \
			-e "s/date\( *:\) \(.*\)/date\1 $(date +%Y%m%d\ \at\ \%H:%M:%S)/" \
			$TMP_DIR/$FLAVOR.desc
		( cd $TMP_DIR ; ls | cpio -o -H newc ) | gzip -9 > \
			$FLAVOR.flavor
		status
		rm -Rf $TMP_DIR
	fi
}

# tazlito check-distro
check_distro()
{
	# Check for a few LiveCD needed files not installed by packages.
	#
	check_rootfs
	newline
	echo -e "\033[1mChecking distro :\033[0m $ROOTFS"
	separator
	# SliTaz release info.
	if [ ! -f "$ROOTFS/etc/slitaz-release" ]; then
		echo "Missing release info : /etc/slitaz-release"
	else
		release=$(cat $ROOTFS/etc/slitaz-release)
		echo -n "Release      : $release"
		status
	fi
	# Tazpkg mirror.
	if [ ! -f "$ROOTFS$LOCALSTATE/mirror" ]; then
		echo -n "Mirror URL   : Missing $LOCALSTATE/mirror"
		todomsg
	else
		echo -n "Mirror configuration exists..."
		status
	fi
	# Isolinux msg
	if grep -q "cooking-XXXXXXXX" /$ROOTCD/boot/isolinux/isolinux.*g; then
		echo -n "Isolinux msg : Missing cooking date XXXXXXXX (ex `date +%Y%m%d`)"
		todomsg
	else
		echo -n "Isolinux message seems good..."
		status
	fi
	separator
	newline
}

# tazlito writeiso
writeiso()
{
	# Writefs to ISO image including /home unlike gen-distro we dont use
	# packages to generate a rootfs, we build a compressed rootfs with all
	# the current filesystem similar to 'tazusb writefs'.
	#
	DISTRO="/home/slitaz/$SLITAZ_VERSION/distro"
	ROOTCD="$DISTRO/rootcd"
	if [ -z $1 ]; then
		COMPRESSION=none
	else
		COMPRESSION=$1
	fi
	if [ -z $2 ]; then
		ISO_NAME="slitaz"
	else
		ISO_NAME="$2"
	fi
	check_root
	# Start info
	newline
	echo -e "\033[1mWrite filesystem to ISO\033[0m
===============================================================================
The command writeiso will write the current filesystem into a suitable cpio
archive ($INITRAMFS) and generate a bootable ISO image (slitaz.iso).

Archive compression: $COMPRESSION"
	newline

	# Save some space
	rm /var/cache/tazpkg/* -r -f
	[ -d $DISTRO ] && rm -rf $DISTRO

	# Optionally remove sound card selection and screen resolution.
	echo "Do you wish to remove the sound card and screen configs ? "
	echo -n "Press ENTER to keep or answer (No|yes|exit): "
	read anser
	case $anser in
		e|E|"exit"|Exit)
			exit 0 ;;
		y|Y|yes|Yes)
			echo -n "Removing current sound card and screen configurations..."
			rm -f /var/lib/sound-card-driver
			rm -f /etc/asound.state
			rm -f /etc/X11/screen.conf
			rm -f /etc/X11/xorg.conf ;;
		*)
			echo -n "Keeping current sound card and screen configurations..." ;;
	esac
	status

	cd /
	# Create list of files including default user files since it is defined in /etc/passwd
	# and some new users might have been added.
	find bin etc init sbin var dev lib root usr home >/tmp/list

	for dir in proc sys tmp mnt media media/cdrom media/flash media/usbdisk
	do
		echo $dir >>/tmp/list
	done

	# Generate initramfs with specified compression and display rootfs
	# size in realtime.
	rm -f /tmp/rootfs
	write_initramfs &
	sleep 2
	cd - > /dev/null
	echo -en "\nFilesystem size:"
	while [ ! -f /tmp/rootfs ]
	do
		sleep 1
		echo -en "\\033[18G`du -sh /$INITRAMFS | awk '{print $1}'`    "
	done
	echo -e "\n"

	# Move freshly generated rootfs to the cdrom.
	mkdir -p $ROOTCD/boot
	mv -f /$INITRAMFS $ROOTCD/boot

	# Now we need the kernel and isolinux files.
	if  mount /dev/cdrom /media/cdrom 2>/dev/null; then
		cp /media/cdrom/boot/bzImage $ROOTCD/boot
		cp -a /media/cdrom/boot/isolinux $ROOTCD/boot
		unmeta_boot $ROOTCD
		umount /media/cdrom
	elif  mount |grep /media/cdrom; then
		cp /media/cdrom/boot/bzImage $ROOTCD/boot
		cp -a /media/cdrom/boot/isolinux $ROOTCD/boot
		unmeta_boot $ROOTCD
		umount /media/cdrom;
	else
		echo -e "
When SliTaz is running in RAM the kernel and bootloader files are kept
on the cdrom. Please insert a LiveCD or loop mount the slitaz.iso to
/media/cdrom to let cookiso copy the files.\n"
		echo -en "----\nENTER to continue..."; read i
		exit 1
	fi

	# Generate the iso image.
	cd $DISTRO
	echo "Generating ISO image..."
	genisoimage -R -o $ISO_NAME.iso -b boot/isolinux/isolinux.bin \
	-c boot/isolinux/boot.cat -no-emul-boot -boot-load-size 4 \
	-V "SliTaz" -input-charset iso8859-1 -boot-info-table $ROOTCD
	if [ -x /usr/bin/isohybrid ]; then
		echo -n "Creating hybrid ISO..."
		/usr/bin/isohybrid $ISO_NAME.iso -entry 2 2> /dev/null
		status
	fi
	echo -n "Creating the ISO $CHECKSUM..."
	$CHECKSUM $ISO_NAME.iso > $ISO_NAME.$SUM
	status

	echo "==============================================================================="
	echo "ISO image: `du -sh $DISTRO/$ISO_NAME.iso`"
	newline
	echo -n "Exit or burn ISO to cdrom (Exit|burn)? "; read anser
	case $anser in
		burn)
			eject
			echo -n "Please insert a blank cdrom and press ENTER..."
			read i && sleep 2
			burn_iso $DISTRO/$ISO_NAME.iso
			echo -en "----\nENTER to continue..."; read i ;;
		*)
			exit 0 ;;
	esac
}

# tazlito repack
repack()
{
	# Repack an iso with maximum lzma compression ratio.
	#

	ISO=$1

	mkdir -p $TMP_DIR/mnt
	# Extract filesystems
	echo -n "Mounting $ISO"
	mount -o loop,ro $ISO $TMP_DIR/mnt 2> /dev/null
	status || cleanup_merge
	cp -a $TMP_DIR/mnt $TMP_DIR/iso
	umount -d $TMP_DIR/mnt

	for i in $TMP_DIR/iso/boot/rootfs* ; do
		echo -n "Repacking $(basename $i)"
		(zcat $i 2> /dev/null || unlzma -c $i || cat $i) \
			2>/dev/null > $TMP_DIR/rootfs
		lzma e $TMP_DIR/rootfs $i \
			 $(lzma_switches $TMP_DIR/rootfs)
		status
	done

		create_iso $ISO $TMP_DIR/iso
		rm -rf $TMP_DIR
}

frugal_install()
{
	ISO_IMAGE="$1"
	newline
	mkdir -p /boot/frugal
	if [ -f "$ISO_IMAGE" ]; then
		echo -n "Using ISO image: $ISO_IMAGE"
		mkdir -p /tmp/iso && mount -o loop $ISO_IMAGE /tmp/iso
		status
		echo -n "Installing the Kernel and rootfs..."
		cp -a /tmp/iso/boot/bzImage /boot/frugal
		if [ -f $ROOTCD/boot/rootfs1.gz ]; then
			cd /tmp/iso/boot
			cat $(ls -r rootfs*.gz) > /boot/frugal/$INITRAMFS
		else
			cp -a /tmp/iso/boot/$INITRAMFS /boot/frugal
		fi
		umount /tmp/iso
		status
	else
		echo -n "Using distro: $DISTRO"
		cd $DISTRO && status
		echo -n "Installing the Kernel and rootfs..."
		cp -a $ROOTCD/boot/bzImage /boot/frugal
		if [ -f $ROOTCD/boot/rootfs1.gz ]; then
			cd $ROOTCD/boot
			cat $(ls -r rootfs*.gz) > /boot/frugal/$INITRAMFS
		else
			cp -a $ROOTCD/boot/$INITRAMFS /boot/frugal
		fi
		status
	fi
	# Grub entry
	if ! grep -q "^kernel /boot/frugal/bzImage" /boot/grub/menu.lst; then
		echo -n "Configuring GRUB menu list..."
		cat >> /boot/grub/menu.lst << EOT
title SliTaz GNU/Linux (frugal)
root (hd0,0)
kernel /boot/frugal/bzImage root=/dev/null
initrd /boot/frugal/\$INITRAMFS
EOT
	else
		echo -n "GRUB menu list is up-to-date..."
	fi
	status
	newline
}

# Check iso for loram transformation
check_iso_for_loram()
{
	[ -s $TMP_DIR/iso/boot/$INITRAMFS ] ||
	[ -s $TMP_DIR/iso/boot/rootfs1.gz ]
}

# Build initial rootfs for loram ISO ram/cdrom/http
build_initfs()
{
	urliso="mirror.slitaz.org mirror.switch.ch/ftp/mirror/slitaz \
download.tuxfamily.org/slitaz slitaz.c3sl.ufpr.br"
	version=$(ls $TMP_DIR/iso/boot/vmlinuz-* | sed 's/.*vmlinuz-//')
	if [ -z "$version" ]; then
		cat <<EOT
Can't find the kernel version.
No file /boot/vmlinuz-<version> in ISO image.
Abort.
EOT
		exit 1
	fi
	[ -s /usr/share/boot/busybox-static ] || install_package busybox-static
	need_lib=false
	mkdir -p $TMP_DIR/initfs/bin $TMP_DIR/initfs/dev $TMP_DIR/initfs/lib \
		 $TMP_DIR/initfs/mnt $TMP_DIR/initfs/proc $TMP_DIR/initfs/tmp \
		 $TMP_DIR/initfs/sys
	while [ ! -f /lib/modules/$version/kernel/fs/aufs/aufs.ko.gz ]; do
		install_package aufs $version || return 1
	done
	# bootfloppybox will need floppy.ko.gz, /dev/fd0, /dev/tty0
	cp /lib/modules/$version/kernel/drivers/block/floppy.ko.gz \
		$TMP_DIR/initfs/lib 2> /dev/null
	cp -a /dev/tty0 /dev/fd0 $TMP_DIR/initfs/dev 2> /dev/null
	cp /lib/modules/$version/kernel/fs/aufs/aufs.ko.gz \
		$TMP_DIR/initfs/lib
	if [ -f /bin/cromfs-driver ]; then
		cp /bin/cromfs-driver $TMP_DIR/initfs/bin
		ls /bin/unmkcromfs | \
			cpio -o -H newc > $TMP_DIR/initfs/extractfs.cpio
	else
		[ ! -f /usr/sbin/mksquashfs ] && ! install_package squashfs && return 1
		while [ ! -f /lib/modules/$version/kernel/fs/squashfs/squashfs.ko.gz ]; do
			install_package linux-squashfs $version || return 1
		done
		cp /lib/modules/$version/kernel/fs/squashfs/squashfs.ko.gz \
			 $TMP_DIR/initfs/lib
		ls /sbin/unsquashfs /usr/lib/liblzma.so* $INSTALLED/squashfs/* | \
			cpio -o -H newc > $TMP_DIR/initfs/extractfs.cpio
	fi
	if [ "$1" == "cdrom" ]; then
		for i in $(ls /dev/[hs]d[a-f]*); do
			cp -a $i $TMP_DIR/initfs/dev
		done
	fi
	if [ "$1" == "http" ]; then
		mkdir $TMP_DIR/initfs/etc
		ln -s /proc/mounts $TMP_DIR/initfs/etc/mtab
		cp /usr/share/udhcpc/default.script $TMP_DIR/initfs/lib/udhcpc
		sed -i 's|/sbin/||' $TMP_DIR/initfs/lib/udhcpc
		cp -a /dev/fuse $TMP_DIR/initfs/dev
		if ! $need_lib && [ -x /usr/share/boot/fusermount-static ]; then
			cp /usr/share/boot/fusermount-static $TMP_DIR/initfs/bin/httpfs
		else
			cp /usr/bin/fusermount $TMP_DIR/initfs/bin
			need_lib=true
		fi
		if ! $need_lib && [ -x /usr/share/boot/httpfs-static ]; then
			cp /usr/share/boot/httpfs-static $TMP_DIR/initfs/bin/httpfs
		else
			[ ! -f /usr/bin/httpfs ] && ! install_package httpfs-fuse && return 1
			cp /usr/bin/httpfs $TMP_DIR/initfs/bin
			cp -a /lib/librt* $TMP_DIR/initfs/lib
			cp -a /lib/libdl* $TMP_DIR/initfs/lib
			cp -a /lib/libpthread* $TMP_DIR/initfs/lib
			cp -a /usr/lib/libfuse* $TMP_DIR/initfs/lib
			cp -a /lib/libresolv* $TMP_DIR/initfs/lib
			cp -a /lib/libnss_dns* $TMP_DIR/initfs/lib
			need_lib=true
		fi
		cd $TMP_DIR/initfs
		echo "Getting slitaz-release..."
		for i in $TMP_DIR/iso/boot/rootfs*.gz; do
			( zcat $i 2> /dev/null || unlzma -c $i) | \
			cpio -idmu etc/slitaz-release > /dev/null
		done
		cd - > /dev/null
		echo "Default urls for /iso/$(cat $TMP_DIR/initfs/etc/slitaz-release)/flavors/slitaz-loram-cdrom.iso /iso/$(cat $TMP_DIR/initfs/etc/slitaz-release)/flavors/slitaz-$(cat $TMP_DIR/initfs/etc/slitaz-release)-loram-cdrom.iso: $urliso"
		echo -n "List of urls to insert: "
		read -t 30 urliso2
		urliso="$urliso2 $urliso"
	fi
	if ! $need_lib && [ -x /usr/share/boot/busybox-static ]; then
		cp /usr/share/boot/busybox-static $TMP_DIR/initfs/bin/busybox
	else
		cp /bin/busybox $TMP_DIR/initfs/bin
		need_lib=true
	fi
	for i in $($TMP_DIR/initfs/bin/busybox | awk \
	  '{ if (s) printf "%s",$0 } /Currently/ { s=1 }' | sed 's/,//g'); do
		ln $TMP_DIR/initfs/bin/busybox $TMP_DIR/initfs/bin/$i
	done
	for i in /dev/console /dev/loop* /dev/null /dev/tty /dev/zero \
		 /dev/kmem /dev/mem /dev/random /dev/urandom; do
		cp -a $i $TMP_DIR/initfs/dev
	done
	$need_lib && for i in /lib/ld-* /lib/lib[cm].so* /lib/lib[cm]-* ; do
		cp -a $i $TMP_DIR/initfs/lib
	done
	cat > $TMP_DIR/initfs/init <<EOTEOT
#!/bin/sh

getarg()
{
	grep -q " \$1=" /proc/cmdline || return 1
	eval \$2=\$(sed "s/.* \$1=\\\\([^ ]*\\\\).*/\\\\1/" < /proc/cmdline)
	return 0
}

copy_rootfs()
{
	total=\$(grep MemTotal /proc/meminfo | sed 's/[^0-9]//g')
	need=\$(du -c \${path}rootfs* | tail -n 1 | cut -f1)
	[ \$(( \$total / \$need )) -gt 1 ] || return 1
	if ! grep -q " keep-loram" /proc/cmdline && cp \${path}rootfs* /mnt; then
		path=/mnt/
		return 0
	else
		rm -f /mnt/rootfs*
		return 1
	fi
}

echo "Switching / to tmpfs..."
mount -t proc proc /proc
size="\$(grep rootfssize= < /proc/cmdline | \\
	sed 's/.*rootfssize=\\([0-9]*[kmg%]\\).*/-o size=\\1/')"
[ -n "\$size" ] || size="-o size=90%"

if [ -x /bin/httpfs ]; then	# loram-http

while read var default; do
	eval \$var=\$default
	getarg \$var \$var
done <<EOT
eth	eth0
dns	208.67.222.222,208.67.220.220
netmask	255.255.255.0
gw
ip
EOT
if [ -n "\$ip" ]; then
	ifconfig \$eth \$ip netmask \$netmask up
	route add default gateway \$gw
	for i in \$(echo \$dns | sed 's/,/ /g'); do
		echo "nameserver \$i" >> /etc/resolv.conf
	done
else
	udhcpc -f -q -s /lib/udhcpc -i \$eth
fi
for i in $urliso ; do
	[ -n "\$URLISO" ] && URLISO="\$URLISO,"
	URLISO="\${URLISO}http://\$i/iso/\$(cat /etc/slitaz-release)/flavors/slitaz-loram-cdrom.iso,http://\$i/iso/\$(cat /etc/slitaz-release)/flavors/slitaz-\$(cat /etc/slitaz-release)-loram-cdrom.iso"
done
getarg urliso URLISO
DIR=fs
if getarg loram DIR; then
	DEVICE=\${DIR%,*}
	DIR=/\${DIR#*,}
fi
mount -t tmpfs \$size tmpfs /mnt
path2=/mnt/.httpfs/
path=/mnt/.cdrom/
mkdir -p /mnt/.rw \$path \$path2
while [ ! -d \$path/boot ]; do
	for i in \$(echo \$URLISO | sed 's/,/ /g'); do
		httpfs \$i \$path2 && break
	done
	mount -o loop,ro -t iso9660 \$path2/*.iso \$path
done
#copy_rootfs && umount -d \$path && umount -d \$path2

elif [ -f \$(echo /rootfs*.gz | cut -f1 -d' ') ]; then	# loram-ram

total=\$(grep MemTotal /proc/meminfo | sed 's/[^0-9]//g')
free=\$(grep MemFree /proc/meminfo | sed 's/[^0-9]//g')
if [ \$(( \$total/\$free )) -gt 1 ] || ! mount -t tmpfs \$size tmpfs /mnt; then
	echo "No tmpfs for /mnt"
	mkdir -p /mnt/.rw
	mount -t tmpfs tmpfs /mnt/.rw
	mkdir -p /mnt/.rw/mnt/.rw
	path=/
else
	mkdir -p /mnt/.rw
	path=/mnt/.
	for i in rootfs* ; do
		mv /\$i \$path\$i
	done
fi

else				# loram-cdrom

getarg cdrom DRIVE_NAME ||
DRIVE_NAME=\$(grep "drive name" < /proc/sys/dev/cdrom/info | cut -f 3)
DEVICE=/dev/\$DRIVE_NAME
DIR=fs
if getarg loram DIR; then
	DEVICE=\${DIR%,*}
	DIR=/\${DIR#*,}
fi
mount -t tmpfs \$size tmpfs /mnt
mkdir -p /mnt/.rw /mnt/.cdrom /mnt/mnt/.cdrom
i=0
while [ \$i -lt 5 ] && ! mount -r \$DEVICE /mnt/.cdrom; do
	case "\$DEVICE" in
	/dev/sd*|UUID=*|LABEL=*)
		mount -t sysfs sysfs /sys
		USBDELAY=\$(cat /sys/module/usb_storage/parameters/delay_use)
		umount /sys
		sleep \$((1+\$USBDELAY)) ;;
	esac
	i=\$((i+1))
done
path=/mnt/.cdrom/
copy_rootfs && umount -d /mnt/.cdrom

fi

memfree=\$(grep MemFree /proc/meminfo | sed 's/[^0-9]//g')
umount /proc
branch=br=/mnt/.rw:/mnt/.cdrom/\$DIR
if [ ! -d /mnt/.cdrom/\$DIR/etc ]; then
branch=br=/mnt/.rw
for i in \${path}rootfs* ; do
	fs=\${i#*root}
	branch=\$branch:/mnt/.\$fs
	mkdir -p /mnt/.rw/mnt/.\$fs /mnt/.\$fs /mnt/.rw/mnt/.cdrom
	if [ -f /bin/cromfs-driver ]; then
		cromfs-driver \${path}root\$fs /mnt/.\$fs -o ro,dev,suid,allow_other
	else
		insmod /lib/squashfs.ko.gz 2> /dev/null
		mount -o loop,ro -t squashfs \${path}root\$fs /mnt/.\$fs
	fi
done
else
mkdir -p /mnt/.rw/mnt/.httpfs
fi
insmod /lib/aufs.ko.gz
mount -t aufs -o \$branch none /mnt
[ -x /bin/httpfs ] && sed -i 's/DHCP="yes"/DHCP="no"/' /mnt/etc/network.conf
[ \$memfree -lt 30000 ] && sed -i 's/ slim//' /mnt/etc/rcS.conf
[ -x /mnt/sbin/init ] && exec /bin/switch_root mnt /sbin/init || sh
EOTEOT
	chmod +x $TMP_DIR/initfs/init
	( cd $TMP_DIR/initfs ; find | busybox cpio -o -H newc 2> /dev/null) | \
	lzma e $TMP_DIR/initfs.gz -si
	lzma_set_size $TMP_DIR/initfs.gz
	rm -rf $TMP_DIR/initfs
	rem=$(( $(stat -c "%s" $TMP_DIR/initfs.gz) % 4 ))
	[ $rem -ne 0 ] &&
	dd if=/dev/zero bs=1 count=$(( 4 - $rem )) >> $TMP_DIR/initfs.gz 2> /dev/null
	return 0
}

# Move each initramfs to squashfs (or cromfs)
build_loram_rootfs_cdrom()
{
	mkdir -p $TMP_DIR/fs
	cd $TMP_DIR/fs
	for i in $(ls -r $TMP_DIR/iso/boot/rootfs*.gz); do
		( zcat $i 2> /dev/null || unlzma -c $i) | cpio -idmu
	done
	rootfs=$TMP_DIR/$INITRAMFS
	if [ -x /usr/bin/mkcromfs ]; then
		/usr/bin/mkcromfs -qq -f 262144 -b 16384 $TMP_DIR/fs $rootfs
	else
		/usr/sbin/mksquashfs $TMP_DIR/fs $rootfs -comp xz -Xbcj x86
	fi
	rm -rf $TMP_DIR/fs
	cd - > /dev/null
}

# Move meta boot configuration files to basic configuration files
# because meta loram flavor is useless when rootfs is not loaded in ram
unmeta_boot()
{
	local root=${1:-$TMP_DIR/loramiso}
	if [ -f $root/boot/isolinux/noram.cfg ]; then
		# We keep enough information to do unloram...
		[ -s $root/boot/isolinux/common.cfg ] &&
		sed -i 's/label slitaz/label orgslitaz/' \
			$root/boot/isolinux/common.cfg
		set -- $(grep 'append ifmem [0-9]' $root/boot/isolinux/isolinux.cfg)
		shift
		sed -i '/ifmem/{NNNNNNNNd};/^LABEL/{N;/LABEL SliTaz [^L]/{NNNd}}' \
			$root/boot/isolinux/isolinux.cfg
		[ -n "$3" ] || set -- $(grep 'append [0-9]' $root/boot/isolinux/common.cfg)
		sed -i "s/label $3\$/label slitaz/;s|=/boot/rootfs\(.*\).gz |=/boot/rootfs.gz |" \
			$root/boot/isolinux/*.cfg
	fi
}

# Move each initramfs to squashfs (or cromfs)
build_loram_rootfs()
{
	rootfs_sizes=""
	for i in $TMP_DIR/iso/boot/rootfs*.gz; do
		mkdir -p $TMP_DIR/fs
		cd $TMP_DIR/fs
		( zcat $i 2> /dev/null || unlzma -c $i) | cpio -idm
		cd - > /dev/null
		rootfs=$TMP_DIR/$(basename $i)
		if [ -x /usr/bin/mkcromfs ]; then
			/usr/bin/mkcromfs -qq -f 262144 -b 16384 $TMP_DIR/fs $rootfs
		else
			/usr/sbin/mksquashfs $TMP_DIR/fs $rootfs -comp xz -Xbcj x86
		fi
		cd $TMP_DIR
		rootfs_sizes="$rootfs_sizes $(( $(du -s $TMP_DIR/fs | cut -f1) - $(du -s $rootfs | cut -f1) ))"
		( cd $(dirname $rootfs); echo $(basename $rootfs) | \
			  cpio -o -H newc ) > $rootfs.cpio
		rm -f $rootfs
		mv $rootfs.cpio $rootfs
		cd - > /dev/null
		rm -rf $TMP_DIR/fs
	done
}

# Move rootfs to squashfs filesystem(s) to the cdrom writeable with aufs.
# These squashfs may be loaded in ram a boot time.
# Rootfs are also copied to cdrom for tiny ramsize systems.
# Meta flavors are converted to normal flavors.
build_loram_cdrom()
{
	build_initfs cdrom || return 1
	build_loram_rootfs_cdrom
	cp -a $TMP_DIR/iso $TMP_DIR/loramiso
	if [ "$1" == "small" ]; then
		rm -f $TMP_DIR/loramiso/boot/root*
	else
		mkdir $TMP_DIR/loramiso/fs
		cd $TMP_DIR/loramiso/fs
		for i in $( ls ../boot/root* | sort -r ) ; do
			( zcat $i 2> /dev/null || unlzma -c $i ) | cpio -idmu
			rm -f $i
		done
		mkdir -p $TMP_DIR/loramiso/fs/mnt/.cdrom
		cd - > /dev/null
	fi
	mv $TMP_DIR/initfs.gz $TMP_DIR/loramiso/boot/$INITRAMFS
	mv $TMP_DIR/rootfs*.gz $TMP_DIR/loramiso
	unmeta_boot
	VOLUM_NAME="SliTaz_LoRAM_CDROM"
	sed -i "s/root=/loram=LABEL=$VOLUM_NAME,fs &/" \
		$TMP_DIR/loramiso/boot/isolinux/*.cfg
	create_iso $OUTPUT $TMP_DIR/loramiso
}

# Create http bootstrap to load and remove loram_cdrom
# Meta flavors are converted to normal flavors.
build_loram_http()
{
	build_initfs http || return 1
	cp -a $TMP_DIR/iso $TMP_DIR/loramiso
	rm -f $TMP_DIR/loramiso/boot/rootfs*
	mv $TMP_DIR/initfs.gz $TMP_DIR/loramiso/boot/$INITRAMFS
	unmeta_boot
	create_iso $OUTPUT $TMP_DIR/loramiso
}

# Update meta flavor selection sizes.
# Reduce sizes with rootfs gains.
update_metaiso_sizes()
{
	for cfg in $(grep -El '(append|ifmem) [0-9]' $TMP_DIR/loramiso/boot/isolinux/*.cfg)
	do
		local append="$(grep -E '(append|ifmem) [0-9]' $cfg)"
		local sizes="$rootfs_sizes"
		local new
		set -- $append
		shift
		[ "$1" == "ifmem" ] && shift
		new=""
		while [ -n "$2" ]; do
			local s
			case "$1" in
			*G) s=$(( ${1%G} * 1024 * 1024 ));;
			*M) s=$(( ${1%M} * 1024 ));;
			*)  s=${1%K};;
			esac
			sizes=${sizes#* }
			for i in $sizes ; do
				s=$(( $s - $i ))
			done
			new="$new $s $2"
			shift 2
		done
		sed -i -e "/append [0-9]/s/append .*/append$new $1/" -e \
			"/append ifmem [0-9]/s/append .*/append ifmem$new $1/" $cfg
	done
}

# Move rootfs to a squashfs filesystem into the initramfs writeable with aufs.
# Meta flavor selection sizes are updated.
build_loram_ram()
{
	build_initfs ram || return 1
	build_loram_rootfs
	cp -a $TMP_DIR/iso $TMP_DIR/loramiso
	rm -f $TMP_DIR/loramiso/boot/bzImage
	ln $TMP_DIR/loramiso/boot/vmlinuz* $TMP_DIR/loramiso/boot/bzImage
	rootfs=$(ls $TMP_DIR/rootfs* | sort | tail -n 1)
	cat $rootfs >> $TMP_DIR/initfs.gz
	mv $TMP_DIR/initfs.gz $rootfs
	cp $TMP_DIR/rootfs* $TMP_DIR/loramiso/boot
	update_metaiso_sizes
	create_iso $OUTPUT $TMP_DIR/loramiso
}
