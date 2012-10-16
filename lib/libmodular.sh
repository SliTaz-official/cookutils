#!/bin/sh


INIT=$ROOTFS/init
FLAVOR_MOD="justx gtkonly core"
UNION=$ROOTFS/union
LASTBR=$INIT
MODULES_DIR=$ROOTFS/modules
CDNAME="slitaz"
SGNFILE=$ROOTCD/${CDNAME}/livecd.sgn
KEY_FILES="init liblinuxlive linuxrc"
LOG=$DISTRO/log
EXT="xz"
COMPRESSION="xz -Xbcj x86"
MKOPTION="-b 512k"
#NCPU="-processors 3"

error () { echo -e "\033[1;31;40m!!! \033[1;37;40m$@\033[1;0m"; }
warn ()  { echo -e "\033[1;33;40m*** \033[1;37;40m$@\033[1;0m"; }
info () { echo -e "\033[1;32;40m>>> \033[1;37;40m$@\033[1;0m"; }

# build initramfs based one flavor
# $1 = flavor file
initramfs () {

	FLAVOR=${1%.flavor}
	if [ ! -f "$FLAVORS_REPOSITORY/$FLAVOR/receipt" ]; then
		error "error: $FLAVORS_REPOSITORY/$FLAVOR/receipt doesn't exist, aborting."
		exit 1
	fi

	if [ -d ${INIT} ]; then
		rm -Rf ${INIT}
	fi

	if [ ! -d ${INIT} ]; then
		mkdir -p $INIT
	fi

	if [ -d ${LOG} ]; then
		rm -Rf $LOG
	fi

	if [ ! -d ${LOG} ]; then
		mkdir -p $LOG
	fi

	info "Making bootable image"
	[ -f $LOG/initramfs.log ] && rm -f $LOG/initramfs.log
	cat "$FLAVORS_REPOSITORY/$FLAVOR/packages.list" | grep -v "^#" | while read pkgname; do
		if [ ! -f ${INIT}${INSTALLED}/${pkgname}/files.list ]; then
			tazpkg get-install $pkgname --root=$INIT 2>/dev/null | tee -a $LOG/initramfs.log
			sleep 1
		else
			info "${pkgname} installed" | tee -a $LOG/initramfs.log
		fi
	done

	if [ -d $INIT ]; then
		for i in $KEY_FILES; do
			if [ -f $INIT/$i ]; then
				cp -af $INIT/$i $INITRAMFS
			fi
		done
	fi

	if [ -f $INIT/liblinuxlive ]; then
		sed -i "s|^#MIRROR|MIRROR=$MIRROR_DIR|g" $INIT/liblinuxlive
	fi

}

# build slitaz union
slitaz_union () {

	if [ -d ${MODULES_DIR}/${mod}${INSTALLED} ]; then
		echo "${mod} module exist. Moving on."
	elif [ ! -d ${MODULES_DIR}/${mod}${INSTALLED} ]; then
		if [ -f "$FLAVORS_REPOSITORY/${mod}/packages.list" ]; then
			[ -f ${LOG}/${mod}-current.log ] && rm -f ${LOG}/${mod}-current.log
			cat "$FLAVORS_REPOSITORY/${mod}/packages.list" | grep -v "^#" | while read pkgname; do
				if [ ! -f ${UNION}${INSTALLED}/${pkgname}/files.list ]; then
					tazpkg get-install $pkgname --root=${UNION} | tee -a ${LOG}/${mod}-current.log
					sleep 1
				else
					info "${pkgname} installed" | tee -a ${LOG}/${mod}-current.log
				fi
			done
		fi
	fi
}

# build aufs union
union () {
	if [ "$FLAVOR_MOD" ]; then
		UNION_MODULES="$FLAVOR_MOD"
	else
		error "Error: no modules assigned in config for profile."
		exit 1
	fi

	
	mkdir -p $UNION
	mkdir -p $ROOTCD/${CDNAME}/base
	mkdir -p $ROOTCD/${CDNAME}/modules
	mkdir -p $ROOTCD/${CDNAME}/optional
	mkdir -p $ROOTCD/${CDNAME}/rootcopy
	mkdir -p $ROOTCD/${CDNAME}/tmp
	mkdir -p $LASTBR
	
	touch $SGNFILE

	[ -f $INSTALLED/aufs/receipt ] || tazpkg get-install aufs --forced
	modprobe aufs
	if [ $? -ne 0 ]; then
		error "Error loading Union filesystem module. (aufs)"
		exit 1
	fi

	# $INIT is now $LASTBR
	# This will be copyed to /mnt/memory/changes on boot
	initramfs init-modular

	mount -t aufs -o br:${LASTBR}=rw aufs ${UNION}
	if [ $? -ne 0 ]; then 
		error "Error mounting $union."
		exit 1
	fi
	
	info "====> Installing packages to '$UNION'"
	for mod in $UNION_MODULES; do

		if [ -d $MODULES_DIR/$mod ]; then
			rm -Rf $MODULES_DIR/$mod
		fi

		if [ ! -d $MODULES_DIR/$mod ]; then
			mkdir -p $MODULES_DIR/$mod
		fi
		info "Adding $MODULES_DIR/$mod as top branch of union."
		mount -t aufs -o remount,add:0:${MODULES_DIR}/${mod}=rw aufs $UNION
		info "Adding $LASTBR as lower branch of union."
		mount -t aufs -o remount,mod:${LASTBR}=rr+wh aufs $UNION
		LASTBR="$MODULES_DIR/${mod}"

		slitaz_union
	done
	
	if [ -d ${UNION}/${INSTALLED} ]; then
		ls ${UNION}/${INSTALLED} | sort > $ROOTCD/packages-installed.list
	fi
	
	info "Unmounting union"
	umount -l "${UNION}"

	info "Removing unionfs .wh. files."
	find ${MODULES_DIR} -type f -name ".wh.*" -exec rm {} \;
	find ${MODULES_DIR} -type d -name ".wh.*" -exec rm -rf {} \;
}

# _mksquash dirname
_mksquash () {
    if [ ! -d "$1" ]; then
        error "Error: '$1' is not a directory"
        return 1
    fi

    if [ ! -d "$2" ]; then
        error "Error: '$2' is not a directory"
        return 1
    fi

    if [ ! -d "${1}${3}" ]; then
        error "Error: '${1}${3}' is not a directory"
        return 1
    fi

    time_dir="${3}"
    sqimg="${2}/$(basename ${1}).${EXT}"
    info "====> Generating SquashFS image for '${1}'"
    if [ -e "${sqimg}" ]; then
        dirhaschanged=$(find ${1}${time_dir} -newer ${sqimg})
        if [ "${dirhaschanged}" != "" ]; then
            info "SquashFS image '${sqimg}' is not up to date, rebuilding..."
            rm "${sqimg}"
        else
            info "SquashFS image '${sqimg}' is up to date, skipping."
            return
        fi
    fi

    info "Creating SquashFS image. This may take some time..."
    start=$(date +%s)
    if [ "${QUIET}" = "y" ]; then
        mksquashfs "${1}" "${sqimg}" ${NCPU} -noappend ${MKOPTION} -comp ${COMPRESSION} >/dev/null
    else
        mksquashfs "${1}" "${sqimg}" ${NCPU} -noappend ${MKOPTION} -comp ${COMPRESSION}
    fi
    minutes=$(echo $start $(date +%s) | awk '{ printf "%0.2f",($2-$1)/60 }')
    info "Image creation done in $minutes minutes."
}
