#!/bin/sh

# Define & create a temporary directory as it's used by report.
tmp=/tmp/$(basename $0)-$$
mkdir -p $tmp

log_command="$0 $@"

########################################################################
# EXIT FUNCTIONS
########################
# run_on_exit commands are executed when apps exit (whatever the reason)
# run_on_kill commands are executed only when apps are killed (or Ctrl+C)
# Note : one command per line in the variable.
run_on_exit="rm -rf $tmp"
run_on_kill=""
trap run_on_exit EXIT
trap run_on_kill INT KILL

run_on_exit()
{
	echo "$run_on_exit" | while read c; do
		run_on_exit=$(echo "$run_on_exit" | sed 1d)
		$c
	done
	trap - EXIT
	exit
}

run_on_kill()
{
	echo "$run_on_kill" | while read c; do
		run_on_kill=$(echo "$run_on_kill" | sed 1d)
		$c
	done
	trap - INT KILL
	run_on_exit
}

# List packages providing a virtual package.
whoprovide()
{
	local i;
	for i in $(fgrep -l PROVIDE $WOK/*/receipt); do
		. $i
		case " $PROVIDE " in
		*\ $1\ *|*\ $1:*) echo $(basename $(dirname $i));;
		esac
	done
}

# Be sure package exists in wok.
check_pkg_in_wok() {
	[ -f $receipt ] && return
	[ -f $WOK/$(whoprovide $PACKAGE)/receipt ] && return 1
	gettext -e "\nUnable to find package in the wok:"
	echo -e " $pkg\n" && exit 1
}

# rsync wok-hg with wok
rsync_wok() {
	if [ -d "$WOKHG" ]; then
		echo "Updating build wok"
		rsync -r -t -l -u --force -v -D -E --delete --exclude-from "/usr/share/cook/exclude.txt" $WOKHG/ $WOK/ | \
			sed '/^$/'d
		for i in $(ls $WOK); do
			[ ! -f $WOKHG/$i/receipt ] || continue
			if [ -d $WOK/$i ]; then
				echo "Deleting $i"
				rm -rf $WOK/$i
			fi
		done
	fi
}

# Store -- options in a variable.
# Test phase.
# Need to add something to filter options and report errors in case option is not
# listed and used by the command.
get_options()
{
	if echo "$log_command" | fgrep -q ' '--help; then
		echo "Available options for $(echo `basename "$log_command"` | cut -d ' ' -f 1,2) : $get_options_list"
		exit 0
	fi
	for get_option in $(echo "$log_command" | tr ' ' '\n' | grep ^-- | sed 's/^--//'); do
		if [ "${get_options_list/${get_option%%=*}}" = "$get_options_list" ]; then
			echo "Option ${get_option%%=*} is incorrect, valid options are : $get_options_list". >&2
			exit 1
		fi
		if [ "$get_option" = "${get_option/=}" ]; then
			export $get_option=yes
			export opts="$opts --$get_option"
		else
			export $get_option
			export opts="$opts --$get_option"
		fi
	done
}

# gen_wan_db is to make the wanted.txt
gen_wan_db()
{
	local receipt
	[ -f $wan_db ] && rm $wan_db
	for receipt in $(grep -l ^WANTED= $WOK/*/receipt); do
		unset WANTED DEPENDS
		[ -f $receipt ] || continue
		source $receipt
		[ "$WANTED" ] || continue
		echo -e $PACKAGE"\t"$WANTED >> $wan_db
	done
	if [ "$wan_db" = "$INCOMING/wanted.txt" ]; then
		cp -a $wan_db $PKGS/wanted.txt
	fi
}

# gen_dep_db is to make the depends.txt
gen_dep_db()
{
	local pkg receipt
	[ -f $dep_db ] && rm $dep_db
	for pkg in $(ls $WOK); do
		unset DEPENDS BUILD_DEPENDS
		receipt=$WOK/$pkg/receipt
		if [ -f $receipt ]; then
			source $receipt
			echo -e $PACKAGE"\t "$DEPENDS" \t "$BUILD_DEPENDS' ' >> $dep_db
		fi
	done
	if [ "$dep_db" = "$INCOMING/depends.txt" ]; then
		cp -a $dep_db $PKGS/depends.txt
	fi
}

# gen_wok_db is to create the wok cooklist database
# This helps create the wanted.txt, depends.txt and fullco.txt
gen_wok_db()
{
	echo "Generating wok database"
	echo "Removing old files"
	for file in $wan_db $dep_db $fullco; do
		[ -f $file ] && rm $file
	done
	echo "Generating $(basename $wan_db)"
	gen_wan_db
	echo "Generating $(basename $dep_db)"
	gen_dep_db
	echo "Generating $(basename $fullco)"
	sort_db
}

# look for $PACKAGE in $dep_db
look_for_dep()
{
	grep -m1 ^$PACKAGE$'\t' $dep_db | \
		cut -f 2
}

# look for all $PACKAGE depends and build depends in $dep_db
look_for_all()
{
	grep -m1 ^$PACKAGE$'\t' $dep_db | \
			cut -f 2,3 | sed 's/ 	 / /'
}

# same as look_for_all function
look_for_bdep()
{
	look_for_all
}

# reverse depend look up
look_for_rdep()
{
	fgrep ' '$PACKAGE' ' $dep_db | cut -f 1
}

# reverse build depend look up
look_for_rbdep()
{
	fgrep ' '$PACKAGE' ' $dep_db | \
		cut -f 1,3 | fgrep ' '$PACKAGE' ' | cut -f 1
}

# look for wanted $PACKAGE in wanted.txt
look_for_wanted()
{
	grep -m1 ^$PACKAGE$'\t' $wan_db | cut -f 2
}

# look for reverse wanted $PACKAGE in wanted.txt
look_for_rwanted()
{
	for rwanted in $(grep $'\t'$PACKAGE$ $wan_db | cut -f 1); do
		if [ -f "$WOK/$rwanted/receipt" ]; then
			echo "$rwanted"
		fi
	done
}

# look for -dev $WANTED packages in wanted.txt
look_for_dev()
{
	WANTED=$(look_for_wanted)
	if [ "$WANTED" ]; then
		[ -f "$WOK/$WANTED-dev/receipt" ] && echo $WANTED-dev
	fi
	[ -f "$WOK/$PACKAGE-dev/receipt" ] && echo $PACKAGE-dev
}

# make list with $PACKAGE and $PACKAGE-dev
with_dev()
{
	for PACKAGE in $(cat); do
		echo $PACKAGE
		look_for_dev
	done
}

# make list with $PACKAGE and all its wanted receipt
with_wanted()
{
	for PACKAGE in $(cat); do
		echo $PACKAGE
		look_for_wanted
	done
}

use_wanted()
{
	for input in $(cat); do
		{ grep ^$input$'\t' $wan_db || echo $input
		}
	done | sed 's/.*\t//'
}

# We use md5 of cooking stuff in the packaged receipt to check
# commit. We look consecutively in 3 different locations :
# - in the wok/PACKAGE/taz/* folder
# - in the receipt in the package in incoming repository
# - in the receipt in the package in packages repository
# If md5sums match, there's no commit.
check_for_commit_using_md5sum()
{
	if [ ! -f $WOK/$PACKAGE/md5 ]; then
		sed -n '/# md5sum of cooking stuff :/,$p' receipt | \
			sed -e 1d -e 's/^# //' > $WOK/$PACKAGE/md5
		cd $WOK/$PACKAGE
	fi

	if [ -s md5 ]; then					
		if md5sum -cs md5; then
			# If md5sum check if ok, check for new/missing files in
			# cooking stuff.
			for file in $([ -f receipt ] && echo receipt; \
				[ -f description.txt ] && echo description.txt; \
				[ -d stuff ] && find stuff); do
				if ! fgrep -q "  $file" md5; then
					set_commited
				fi
			done
		else
			set_commited
		fi
	else
		set_commited
	fi
}

# add changed md5sum receipts to $commits
set_commited()
{
	grep -q ^$PACKAGE$ $commits || echo $PACKAGE >> $commits
	gen_cookmd5
	update_dep_db
}

# gen md5 files for receipt and stuff files
gen_cookmd5()
{
	# md5sum of cooking stuff make tazwok able to check for changes
	# without hg.
	md5sum $WOK/$PACKAGE/receipt > $WOK/$PACKAGE/md5
	[ -f $WOK/$PACKAGE/description.txt ] && md5sum $WOK/$PACKAGE/description.txt >> $WOK/$PACKAGE/md5
	if [ -d $WOK/$PACKAGE/stuff ]; then
		find $WOK/$PACKAGE/stuff -type f | while read file; do
			md5sum $file >> $WOK/$PACKAGE/md5
		done
	fi
	sed -i "s|$WOK/$PACKAGE/||g" $WOK/$PACKAGE/md5
}

check_for_commit()
{
	if ! check_pkg_in_wok; then
		[ "$?" = 2 ] && return 1
		return
	fi
	for PACKAGE in $(look_for_rwanted) $PACKAGE; do
		RECEIPT=$WOK/$PACKAGE/receipt
		unset_receipt
		[ -f $RECEIPT ] || continue
		source $RECEIPT

		taz_dir=$(echo $WOK/$PACKAGE/taz/$PACKAGE-* | fgrep -v '*')
		if [ -f $WOK/$PACKAGE/md5 ]; then
			cd $WOK/$PACKAGE
			check_for_commit_using_md5sum
		elif [ "$taz_dir" ]; then
			cd $taz_dir
			check_for_commit_using_md5sum
		else
			pkgfile=$(echo $INCOMING/$PACKAGE-$VERSION*.tazpkg | fgrep -v '*')
			[ "$pkgfile" ] || pkgfile=$(echo $PKGS/$PACKAGE-$VERSION*.tazpkg | fgrep -v '*')
			if [ "$pkgfile" ]; then
				get_pkg_files $pkgfile
				check_for_commit_using_md5sum
				rm -r $pkg_files_dir
			else
				set_commited
			fi
		fi
	[ "$forced" ] || echo $PACKAGE >> $tmp/checked
	unset pkgfile
	done
}

########################################################################
# SCAN
########################
# Use wanted.txt and depeds.txt to scan depends.
# Option in command line (must be first arg) :
#   --look_for=bdep/rbdep - Look for depends or reverse depends.
#   --with_dev - Add development packages (*-dev) in the result.
#   --with_wanted - Add package+reverse wanted in the result.
#   --with_args - Include packages in argument in the result.

scan()
{
	# Get packages in argument.
	local PACKAGE=$PACKAGE WANTED=$WANTED pkg_list=
	for arg in $@; do
		[ "$arg" = "${arg#--}" ] || continue
		pkg_list="$pkg_list $arg"
	done

	# Get options.
	[ "$pkg_list" ] || return
	local cooklist= look_for= with_dev= with_wanted= with_args= log_command="$0 $@" \
		get_options_list="look_for with_dev with_wanted with_args cooklist use_wanted"
	get_options

	# Get db md5 to be able to check for changes latter.
	db_md5=$(md5sum $dep_db $wan_db)
	
	# Cooklist is a special case where we need to modify a little
	# scan behavior
	if [ "$cooklist" ]; then
		gen_wan_db
		look_for=all && with_args=yes && with_dev= && with_wanted=
		filter=use_wanted
		if [ "$COMMAND" = gen-cooklist ]; then
   			for PACKAGE in $pkg_list; do
				grep -q ^$PACKAGE$'\t' $dep_db && continue
				[ -d "$WOK/$p" ] || continue
				check_for_missing
			done
			append_to_dep()
			{
				if grep -q ^$PACKAGE$'\t' $dep_db; then
					echo $PACKAGE >> $tmp/dep
				else
					check_for_missing && echo $PACKAGE >> $tmp/dep
				fi
			}
		else
			append_to_dep()
			{
				check_for_commit && echo $PACKAGE >> $tmp/dep
			}
		fi
	else
		append_to_dep()
		{
			echo $PACKAGE >> $tmp/dep
		}
		# If requested packages are not in dep_db, partial generation of this db is needed.
		for PACKAGE in $pkg_list; do
			grep -q ^$PACKAGE$'\t' $dep_db && continue
			[ -d "$WOK/$p" ] || continue	
			plan_check_for_missing=yes	
			check_for_missing
		done
		if [ "$plan_check_for_missing" ]; then
			append_to_dep()
			{
				if grep -q ^$PACKAGE$'\t' $dep_db; then
					echo $PACKAGE >> $tmp/dep
				else
					check_for_missing && echo $PACKAGE >> $tmp/dep
				fi
			}
			unset plan_check_for_missing
		fi
	fi
	
	[ "$with_dev" ] && filter=with_dev
	[ "$with_wanted" ] && filter=with_wanted
	if [ "$filter" ]; then
		pkg_list=$(echo $pkg_list | $filter | sort -u)
		scan_pkg()
		{
			look_for_$look_for | $filter
		}
	else
		scan_pkg()
		{
			look_for_$look_for
		}
	fi
	touch $tmp/dep
	for PACKAGE in $pkg_list; do
		[ "$with_args" ] && append_to_dep
		scan_pkg		
	done  | tr ' ' '\n' | sort -u > $tmp/list
	[ "$look_for" = bdep ] && look_for=dep
	while [ -s $tmp/list ]; do
		PACKAGE=$(sed 1!d $tmp/list)
		sed 1d -i $tmp/list
		append_to_dep
		for pkg in $(scan_pkg); do
			grep -q ^$pkg$ $tmp/list $tmp/dep || echo $pkg >> $tmp/list
		done
	done
	if [ "$cooklist" ]; then
		mv $tmp/dep $tmp/cooklist
	else
		cat $tmp/dep | sort -u
	fi
	rm -f $tmp/dep $tmp/list
	sort -o $dep_db $dep_db
	sort -o $wan_db $wan_db
	if [ "$db_md5" != "$(md5sum $dep_db $wan_db)" ]; then
		grep -q "^#" $fullco || sed 1i"#PlanSort" -i $fullco
	fi
}

# update wanted.txt database
update_wan_db()
{
	local PACKAGE=$PACKAGE
	wanted_list=$(fgrep WANTED=\"$PACKAGE\" $WOK/*/receipt | cut -f1 -d ':')
	grep $'\t'$PACKAGE$ $wan_db | cut -f 1 | while read wan; do
		echo "$wanted_list" | fgrep -q $WOK/$wan/receipt && continue
		sed "/^$wan\t/d" -i $wan_db
	done 
	for RECEIPT in $wanted_list; do
		unset WANTED PACKAGE
		[ -f $RECEIPT ] || continue
		source $RECEIPT
		[ "$WANTED" ] || continue
		sed "/^$PACKAGE\t/d" -i $wan_db
		echo -e $PACKAGE"\t"$WANTED >> $wan_db
	done
	unset wanted_list
}

# update depends.txt file
update_dep_db()
{
	sed "/^$PACKAGE\t/d" -i $dep_db
	echo -e $PACKAGE"\t "$DEPENDS" \t "$BUILD_DEPENDS' ' >> $dep_db
}

# create sorted fullco.txt file
sort_db()
{
	#echo "Generating full cookorder (fullco)"
	sed 's/ \t / /' $dep_db | while read PACKAGE BUILD_DEPENDS; do
		grep -q ^$PACKAGE$'\t' $wan_db && continue
		
		# Replace each BUILD_DEPENDS with a WANTED package by it's
		# WANTED package.
		echo -e $PACKAGE"\t $(echo $BUILD_DEPENDS | use_wanted | \
			sort -u | sed "/^$PACKAGE$/d" | tr '\n' ' ') "
	done > $tmp/db
	while [ -s "$tmp/db" ]; do
		status=start
		for pkg in $(cut -f 1 $tmp/db); do
			 if ! fgrep -q ' '$pkg' ' $tmp/db; then
				echo $pkg >> $tmp/fullco
				sed -e "/^$pkg\t/d" -e "s/ $pkg / /g" -i $tmp/db
				status=proceed
			fi
		done
		if [ "$status" = start ]; then
			cp -f $tmp/db /tmp/remain-depends.txt
			echo "Can't go further because of dependency loop(s). The remaining packages will be commented in the cookorder and will be unbuilt in case of major updates until the problem is solved." >&2
			for remaining in $(cut -f 1 $tmp/db); do
				if ! grep -q ^$remaining $blocked; then
					echo "$remaining" >> $blocked
				fi
			done
			break
		fi
	done
	[ -s $tmp/fullco ] || touch $tmp/fullco
	
	# The toolchain packages are moved in first position.
	grep $(for pkg in `scan "$TOOLCHAIN $TOOLCHAIN_EXTRA" \
		--look_for=all --with_args`; do echo " -e ^$pkg$"; done) \
		$tmp/fullco | tac > $fullco
	for pkg in $(cat $fullco); do
		sed "/^$pkg$/d" -i $tmp/fullco
	done

	tac $tmp/fullco >> $fullco
}

# check for missing $PACKAGE in wok
# used in scan function only
check_for_missing()
{
	local PACKAGE=$PACKAGE
	if ! check_pkg_in_wok; then
		[ "$?" = 2 ] && return 1
		return
	fi
	RECEIPT=$WOK/$PACKAGE/receipt
	[ -f $RECEIPT ] || continue
	source $RECEIPT
	PACKAGE=${WANTED:-$PACKAGE}
	update_wan_db
	for PACKAGE in $(look_for_rwanted) $PACKAGE; do
		RECEIPT=$WOK/$PACKAGE/receipt
		[ -f $RECEIPT ] || continue
		source $RECEIPT
		update_dep_db
	done
}

# look to see if package is missing in 
# $INCOMING/packages.txt and $PKGS/packages.txt
look_for_missing_pkg()
{
	for pkg in $(cat $1); do
		grep -q ^$pkg$ $INCOMING/packages.txt \
			$PKGS/packages.txt || \
			continue
		echo $pkg
	done
}

# Output $VERSION-$EXTRAVERSION using packages.txt
get_pkg_version()
{
	[ "$PACKAGE" ] || return
	grep -m1 -A1 -sh ^$PACKAGE$ $1/packages.txt | tail -1 | sed 's/ *//'
}

# remove previous package
remove_previous_package()
{
	if [ "$prev_VERSION" ] && [ "$VERSION$EXTRAVERSION" != "$prev_VERSION" ]; then
		rm -f $1/$PACKAGE-$prev_VERSION.tazpkg
	fi
	return 0
}

# create cook list
gen_cook_list()
{
	#echo "Scanning wok"
	if [ "$pkg" ]; then
		scan $pkg --cooklist
	elif [ "$LIST" ]; then
		scan `cat $LIST` --cooklist
	else
		scan `cat $cooklist` --cooklist
	fi
		
	[ -s $tmp/checked ] || [ -s $tmp/cooklist ] || return
	
	# Core toolchain should not be cooked unless cook-toolchain is used.
	if [ "$COMMAND" != "toolchain" ] ; then
		for PACKAGE in $(scan slitaz-toolchain --look_for=all --with_args --with_wanted); do
			grep -q ^$PACKAGE$ $blocked || \
				echo $PACKAGE >> $blocked
		done
	fi

	if [ -s $commits ] && [ "$COMMAND" != gen-cooklist ]; then
		for PACKAGE in $(cat $commits); do
			WANTED="$(look_for_wanted)"
			if [ "$WANTED" ]; then
				grep -q ^$WANTED$ $broken $cooklist $blocked $commits && continue
			fi
			grep -q ^$PACKAGE$ $blocked $cooklist && continue
			echo $PACKAGE >> $cooklist
		done
	fi
	sort_cooklist
}

# sort cooklist
sort_cooklist()
{
	if [ "$(sed 1!d $fullco)" = "#PlanSort" ]; then
		sed 1d -i $fullco
		sort_db
	fi
	#echo "Generating cooklist"
	if [ -f "$tmp/checked" ]; then
		rm -f $tmp/cooklist
		cat $tmp/checked | while read PACKAGE; do
			grep -q ^$PACKAGE$ $cooklist && echo $PACKAGE >> $tmp/cooklist
		done
	elif ! [ "$COMMAND" = gen-cooklist ]; then
		cat $blocked | while read PACKAGE; do
			sed "/^$PACKAGE/d" -i $tmp/cooklist
		done
	fi
	[ -s $tmp/cooklist ] || return

	#echo "Sorting cooklist"
	for PACKAGE in $(cat $tmp/cooklist); do
		WANTED="$(look_for_wanted)"
		[ "$WANTED" ] || continue
		if grep -q ^$WANTED$ $broken $tmp/cooklist; then
			sed "/^$PACKAGE$/d" -i $tmp/cooklist
		elif [ ! -d $WOK/$WANTED/install ]; then
			sed "/^$PACKAGE$/d" -i $tmp/cooklist
			echo $WANTED >> $tmp/cooklist
		fi
	done

	# Use cookorder.txt to sort cooklist.
	if [ -s $tmp/cooklist ]; then
		cat $fullco | while read PACKAGE; do
			if grep -q ^$PACKAGE$ $tmp/cooklist; then
				sed "/^$PACKAGE$/d" -i $tmp/cooklist
				echo $PACKAGE >> $tmp/cooklist.tmp
			fi
		done

		# Remaining packages in cooklist are those without compile_rules.
		# They can be cooked first in any order.
		if [ -f $tmp/cooklist.tmp ]; then
			cat $tmp/cooklist.tmp >> $tmp/cooklist
			rm $tmp/cooklist.tmp
		fi
		
		cat $tmp/cooklist
		[ "$LIST" ] || cat $tmp/cooklist > $cooklist
	fi
}

# Check $COOK_OPT; usage : get_cookopt particular_opt
# Return error if not found
# Return args if the opt is in the format opt=arg1:arg2:etc
look_for_cookopt()
{
	for arg in $COOK_OPT; do
		case $arg in
			$1=*)
				arg=${arg#$1=}
				while [ "$arg" ]; do
					echo "${arg%%:*}"
					[ "${arg/:}" = "$arg" ] && return
					arg=${arg#*:}
				done
			;;
			$1)
				return
			;;
		esac
	done
	return 1
}

# check $INCOMING packages into $PKGS
check_for_incoming()
{
	echo "Checking that all packages were cooked OK"
	[ -s $INCOMING/packages.desc ] || {
	echo "No packages in $INCOMING."
	return; }
	if [ -s $broken ]; then
		missingpkg=$(look_for_missing_pkg $broken)
		if [ "$missingpkg" ]; then
			echo "Don't move incoming packages to main repository because these ones are broken:" >&2
			echo "$missingpkg"
			return 1
		fi
	fi
	if [ -s $cooklist ]; then
		missingpkg=$(look_for_missing_pkg $cooklist)
		if [ "$missingpkg" ]; then
			echo "Don't move incoming packages to main repository because these ones need to be cooked:" >&2
			echo "$missingpkg"
			return 1
		fi
	fi
	incoming_pkgs="$(cut -f 1 -d '|' $INCOMING/packages.desc)"
	if ! [ "$forced" ]; then
		cooklist=$CACHE/cooklist
		pkg="$incoming_pkgs"
		gen_cook_list
		if [ -s $cooklist ]; then
			missingpkg=$(look_for_missing_pkg $cooklist)
			if [ "$missingpkg" ]; then
				echo "Don't move incoming packages to main repository because these ones need to be cooked:" >&2
				echo "$missingpkg"
				return 1
			fi
		fi
	fi

	echo "Moving incoming packages to main repository"
	unset EXTRAVERSION
	for PACKAGE in $incoming_pkgs; do
			prev_VERSION=$(get_pkg_version $PKGS)
			VERSION=$(get_pkg_version $INCOMING)
			if [ -f $INCOMING/$PACKAGE-${VERSION}${EXTRAVERSION}.tazpkg ]; then
				remove_previous_package $PKGS
				echo "Moving $PACKAGE..."
				mv -f $INCOMING/$PACKAGE-${VERSION}${EXTRAVERSION}.tazpkg $PKGS
				touch $PKGS/$PACKAGE-${VERSION}${EXTRAVERSION}.tazpkg
			else
				echo "$PACKAGE doesn't exist"
			fi
			if [ "$AUTO_PURGE_SRC" ]; then
				previous_tarball=$(grep ^$PACKAGE:main $SRC/sources.list | cut -f2)
				sed -e "/^$PACKAGE:main/d" \
					-e "s/^$PACKAGE:incoming/$PACKAGE:main/" \
					-i $SRC/sources.list
				if [ "$previous_tarball" ]; then
					grep -q $'\t'$previous_tarball$ $SRC/sources.list || \
						rm -f $SRC/$previous_tarball
				fi
			fi
	done
	for file in packages.list packages.equiv packages.md5 packages.desc \
		packages.txt; do
		echo -n "" > $INCOMING/$file
	done
	[ -f "$INCOMING/files.list.lzma" ] && rm -r $INCOMING/files.list.lzma
	pkg_repository=$PKGS && gen_packages_db

}

# help gen sources.list file from scranch
gen_sources_list()
{
	local src_repository=$1
	[ -f $src_repository/sources.list ] && rm -f $src_repository/sources.list
	for i in $WOK/*; do
		unset PACKAGE SOURCE KBASEVER VERSION WGET_URL TARBALL WANTED
		[ -f $i/receipt ] && source $i/receipt
		[ "$WGET_URL" ] || continue
		if grep -q "^$PACKAGE | $VERSION" $PKGS/packages.desc; then
			main_version="$VERSION"
			if [ -f $src_repository/${SOURCE:-$PACKAGE}-${KBASEVER:-$VERSION}.tar.lzma ]; then
				echo -e "$PACKAGE:main\t${SOURCE:-$PACKAGE}-${KBASEVER:-$VERSION}.tar.lzma" >> $src_repository/sources.list
			elif [ -f "$src_repository/$TARBALL" ]; then
				echo -e "$PACKAGE:main\t$TARBALL" >> $src_repository/sources.list
			fi
		else
			# May not works if package use extraversion.
			main_version=$(grep -m1 -A1 -sh ^$PACKAGE$ $PKGS/packages.txt | tail -1 | sed 's/ *//')
			if [ -f $src_repository/${SOURCE:-$PACKAGE}-${KBASEVER:-$main_version}.tar.lzma ]; then
				echo -e "$PACKAGE:main\t${SOURCE:-$PACKAGE}-${KBASEVER:-$main_version}.tar.lzma" >> $src_repository/sources.list
			else
				unset main_version
			fi
		fi
		if [ ! "$main_version" ] || [ $(grep -q "^$PACKAGE | $VERSION" $INCOMING/packages.desc 2>/dev/null) ]; then
			if [ -f $src_repository/${SOURCE:-$PACKAGE}-${KBASEVER:-$VERSION}.tar.lzma ]; then
				echo -e "$PACKAGE:incoming\t${SOURCE:-$PACKAGE}-${KBASEVER:-$VERSION}.tar.lzma" >> $src_repository/sources.list
			elif [ -f "$src_repository/$TARBALL" ]; then
				echo -e "$PACKAGE:incoming\t$TARBALL" >> $src_repository/sources.list
			fi
		fi
	done
}

# get package files for building libraries.txt, files.list.lzma, and packages.desc
get_pkg_files()
{
	pkg_files_dir=/tmp/cook/$(basename ${1%.tazpkg})
	mkdir -p $pkg_files_dir && \
		cd $pkg_files_dir && \
		cpio --quiet -idm receipt < $1 2>/dev/null && \
		cpio --quiet -idm files.list < $1 2>/dev/null && \
		cpio --quiet -idm library.list < $1 2>/dev/null
}

# check .so files
check_so_files()
{
	pwd=$(pwd)
	for rep in $PKGS $INCOMING; do
		prev_VERSION=$(get_pkg_version $rep)
		[ "$prev_VERSION" ] && pkg_file=$rep/$PACKAGE-$prev_VERSION.tazpkg && break
	done
	if [ "$pkg_file" ]; then
		gettext -e "Looking for major/minor updates in libraries\n"
		get_pkg_files $pkg_file
		if [ -d $WOK/$PACKAGE/taz/$PACKAGE-${VERSION}${EXTRAVERSION} ]; then
			cd $WOK/$PACKAGE/taz/$PACKAGE-${VERSION}${EXTRAVERSION}
		else
			cd $WOK/$PACKAGE/taz/$PACKAGE-$VERSION
		fi
		
		pkg_to_check=$(diff $pkg_files_dir/files.list files.list | \
		grep '^-/.*\.so' | while read lib; do
			pkg=$(fgrep " ${lib##*/} " $lib_db | cut -f1)
			for i in $pkg; do
				[ -f $WOK/$i/receipt ] || continue
				wanted=$(grep ^WANTED= $WOK/$i/receipt | cut -d "=" -f2 | sed -e 's/"//g')
				if [ "$wanted" ]; then
					echo $wanted
				else
					echo $i
				fi
			done
		done | sort -u)
		
		if [ "$pkg_to_check" ]; then
			for rdep in $(scan $PACKAGE --look_for=rdep | use_wanted); do
				echo "$pkg_to_check" | grep -q ^$rdep$ || continue
				[ "$rdep" = "${WANTED:-$PACKAGE}" ] && continue
				grep -q ^$rdep$ $blocked $cooklist && continue
				echo "Plan to recook $rdep"
				echo $rdep >> $cooklist
				regen_cooklist=yes
			done
		fi
		update_lib_db
		rm -r $pkg_files_dir
		unset pkg_file pkg_file_dir pkg_to_check
		cd $pwd
   	else
		if [ -d $WOK/$PACKAGE/taz/$PACKAGE-${VERSION}${EXTRAVERSION} ]; then
			cd $WOK/$PACKAGE/taz/$PACKAGE-${VERSION}${EXTRAVERSION}
		else
			cd $WOK/$PACKAGE/taz/$PACKAGE-$VERSION
		fi
		update_lib_db
		cd $pwd
   	fi
}

# check recook reverse depends
check_recook_rdeps()
{
	# Recook of reverse-depends if package was broken.
	if grep -q "^$PACKAGE$" $broken; then
		echo "Planning a re-try cook of reverse depends" 
		sed "/^$PACKAGE$/d" -i $broken
		for rdep in $(look_for_rdep); do
			grep -q "^$rdep$" $broken || continue
			grep -q "^$rdep$" $cooklist && continue
			echo "Adding $rdep to the cooklist"
			echo $rdep >> $cooklist
			regen_cooklist=t
		done
	fi
	sed "/^$PACKAGE$/d" -i $commits
	sed "/^$PACKAGE$/d" -i $cooklist
}

# remove source folder
remove_src()
{
	[ "$WANTED" ] && return
	look_for_cookopt !remove_src && return
	
	# Don't remove sources if a package uses src variable in its
	# genpkg_rules: it maybe needs something inside.
	for i in $PACKAGE $(look_for_rwanted); do
		sed -n '/^genpkg_rules\(\)/','/^}/'p $WOK/$i/receipt | \
			fgrep -q '$src' && gettext -e "Sources will not be removed \
because $i uses \$src in its receipt.\n" && return
	done
	
	gettext -e "Removing sources directory"
	echo ""
	rm -fr "$src"
	[ -d $WOK/$PACKAGE/source ] && rm -rf $WOK/$PACKAGE/source
}

# check for varable modification
check_for_var_modification()
{
	for var in $@; do
		for pkg in $PACKAGE $(look_for_wanted) $(look_for_rwanted); do
			[ -f $WOK/$pkg/receipt ] || continue
			fgrep -q "$var=" $WOK/$pkg/receipt && return 1
		done
	done
	
	# Tweak to make if; then...; fi function working with this one.
	echo -n ""
}

# clean $WOK/$PACKAGE folder
clean()
{
	cd $WOK/$PACKAGE
	ls -A $WOK/$PACKAGE | grep -q -v -e ^receipt$ -e ^description.txt$ \
		-e ^stuff$ || return
	
	[ "$COMMAND" = clean-wok ] || echo "Cleaning $PACKAGE"
	# Check for clean_wok function.
	if grep -q ^clean_wok $RECEIPT; then
		clean_wok
	fi
	# Clean should only have a receipt, stuff and optionals desc/md5.
	for f in `ls .`
	do
		case $f in
			receipt|stuff|description.txt|md5)
				continue ;;
			*)
				rm -rf $f ;;
		esac
	done
}

# put $PACKAGE in $broken file if not already there
set_pkg_broken()
{
	grep -q ^$PACKAGE$ $broken || echo $PACKAGE >> $broken

	# Remove pkg from cooklist to avoid re-cook it if no changes happen
	# in the cook stuff.
	sed "/^$PACKAGE$/d" -i $cooklist $commits

	gen_cookmd5

	# Return 1 to make report know that its mother-function failed.
	return 1
}

# Log broken packages.
broken() {
	unset cook_code
	for PACKAGE in $(look_for_wanted) $PACKAGE; do
		set_pkg_broken
	done
	cook_code=1
}

# start package database
packages_db_start()
{
	if [ ! -s packages.txt ]; then
			echo "# SliTaz GNU/Linux - Packages list
#
# Packages : unknown
# Date     : $(date +%Y-%m-%d\ \%H:%M:%S)
#
" > packages.txt
	else
		sed -e 's/^# Packages :.*/# Packages : unknown/' \
			-e "s/# Date     :.*/# Date     : $(date +%Y-%m-%d\ \%H:%M:%S)/" \
			-i packages.txt
	fi
	
	# If $packages_repository is the main one, configure few functions
	# to act as they should, without having loop on them (speed-up)
	if [ "$pkg_repository" = "$PKGS" ]; then
		erase_package_info_extracmd="erase_package_info_main"
		get_packages_info_extracmd="get_packages_info_main"
	fi
}

# erase previous package info
erase_package_info()
{
	cd $pkg_repository
	sed "/^$PACKAGE$/,/^$/d" -i packages.txt
	sed "/^$PACKAGE /d" -i packages.desc
	sed -e "s/=$PACKAGE /= /" -e "s/ $PACKAGE / /" 	-e "s/ $PACKAGE$//" \
		-e "/=$PACKAGE$/d" -e "s/=[0-9,a-z,A-Z]:$PACKAGE /= /" \
		-e "s/ [0-9,a-z,A-Z]:$PACKAGE / /" -e "s/ [0-9,a-z,A-Z]:$PACKAGE$/ /" \
		-e "/=[0-9,a-z,A-Z]:$PACKAGE$/d" \
		-i packages.equiv
	sed "/^$PACKAGE:/d" -i files.list
	sed "/^$(basename ${pkg%.tazpkg})$/d" -i packages.list
	sed "/ $(basename $pkg)$/d" -i packages.$SUM
	$erase_package_info_extracmd
}

# make the end of the package database
packages_db_end()
{
	cd $pkg_repository
	pkgs=$(wc -l packages.list | sed 's/ .*//')
	sed "s/# Packages : .*/# Packages : $pkgs/" -i packages.txt
	
	# If lists were updated it's generally needed to sort them well.
	echo "Sorting packages lists"
	files_list="packages.list packages.desc packages.equiv wanted.txt depends.txt libraries.txt"
	for file in $files_list; do
		[ -f $file ] || continue
		sort -o $file $file
	done
	
	$CHECKSUM packages.$SUM | cut -f1 -d' ' > ID
	[ -s ID ] || echo null > ID
	
	# Dont log this because lzma always output errors.
	lzma e files.list files.list.lzma
	rm -f files.list
	[ -f packages.equiv ] || touch packages.equiv
}

# get packages info
get_packages_info()
{
	# If there's no taz folder in the wok, extract info from the
	# package.
	get_pkg_files $pkg
	unset_receipt
	. $pkg_files_dir/receipt
	
	#[ "$COMMAND" = "check-incoming" ] && gettext -e "Getting data from ${PACKAGE} \n"

	cat >> $pkg_repository/packages.txt << _EOT_
$PACKAGE
    $VERSION$EXTRAVERSION
    $SHORT_DESC
_EOT_
	if [ "$PACKED_SIZE" ]; then
		cat >> $pkg_repository/packages.txt << _EOT_
    $PACKED_SIZE ($UNPACKED_SIZE installed)

_EOT_
	else
		echo "" >> $pkg_repository/packages.txt
	fi

	# Packages.desc is used by Tazpkgbox <tree>.
	echo "$PACKAGE | $VERSION$EXTRAVERSION | $SHORT_DESC | $CATEGORY | $WEB_SITE" >> $pkg_repository/packages.desc

	# Packages.equiv is used by tazpkg install to check depends.
	for i in $PROVIDE; do
		DEST=""
		echo $i | fgrep -q : && DEST="${i#*:}:"
		if grep -qs ^${i%:*}= $pkg_repository/packages.equiv; then
			sed -i "s/^${i%:*}=/${i%:*}=$DEST$PACKAGE /" $pkg_repository/packages.equiv
		else
			echo "${i%:*}=$DEST$PACKAGE" >> $pkg_repository/packages.equiv
		fi
	done	

	if [ -f files.list ]; then 
		{ echo "$PACKAGE"; cat files.list; } | awk '
BEGIN { name="" } { if (name == "") name=$0; else printf("%s: %s\n",name,$0); }' >> $pkg_repository/files.list
	fi

	if [ -f library.list ]; then
		sed "/^$PACKAGE\t/d" -i $pkg_repository/libraries.txt
		cat library.list >> $pkg_repository/libraries.txt
	fi
	
	cd .. && rm -r "$pkg_files_dir"

	cd $pkg_repository
	echo $(basename ${pkg%.tazpkg}) >> packages.list
	$CHECKSUM $(basename $pkg) >> packages.$SUM
	$get_packages_info_extracmd
}

# gen packages database
gen_packages_db()
{
	[ "$pkg_repository" ] || pkg_repository=$PKGS
	cd $pkg_repository
	gettext -e "Generating packages lists: $pkg_repository\n"
	gettext -e "Removing old files\n"
	for file in files.list.lzma packages.list packages.txt \
		packages.desc packages.equiv packages.$SUM; do
		[ -f $file ] && rm $file
	done
	touch files.list
	[ -f libraries.txt ] && rm -f libraries.txt
	if [ "$pkg_repository" == "$INCOMING" ]; then
		if [ -f "$PKGS/libraries.txt" ]; then
			cp -a $PKGS/libraries.txt $INCOMING/libraries.txt
		fi
	fi
	touch libraries.txt
	touch depends.txt
	touch wanted.txt
	
	packages_db_start
	unset_receipt
	gettext -e "Reading data from all packages\n"
	for pkg in $(echo $pkg_repository/*.tazpkg | fgrep -v '*'); do
		get_packages_info
	done
	packages_db_end
}

# update package database
update_packages_db()
{
	[ "$pkg_repository" ] || pkg_repository=$PKGS
	cd $pkg_repository
	for file in packages.list packages.equiv packages.$SUM \
		packages.desc packages.txt; do
		if [ ! -f "$file" ]; then
			gen_packages_db
			return
		fi
	done
	if	[ -f files.list.lzma ]; then
		lzma d files.list.lzma files.list
	else
		gen_packages_db
		return
	fi
	gettext -e "Updating packages lists: $pkg_repository\n"
	echo ""
	packages_db_start

	# Look for removed/update packages.
	touch stamp -r packages.list
	for PACKAGE in $(grep ^[0-9,a-z,A-Z] packages.txt); do
		pkg="$pkg_repository/$(grep -m1 ^$PACKAGE- packages.list).tazpkg"
		if [ ! -f "$pkg" ]; then
			erase_package_info
		else
			if [ "$pkg" -nt "stamp" ]; then
				updated_pkg="$updated_pkg
$PACKAGE $pkg"
			elif [ ! -f $WOK/$PACKAGE/receipt ] && \
				[ "$COMMAND" = check-incoming -o "$pkg_repository" = "$INCOMING" ]; then
				erase_package_info
				gettext -e "Removing $PACKAGE from $pkg_repository.\n"	
				rm $pkg
				if [ "$pkg_repository" = "$INCOMING_REPOSITORY" ]; then
					[ -d $WOK/$PACKAGE ] && rm -r $WOK/$PACKAGE
					sed "/^$PACKAGE\t/d" -i $wan_db $dep_db
					for i in $fullco $cookorder $cooklist $commits $blocked $broken; do
						sed "/^$PACKAGE$/d" -i $i
					done
					[ -f $LOGS/$pkg.log ] && rm -f $LOGS/$pkg.log
					if [ "$(sed 1!d $fullco)" != "#PlanSort" ]; then
						sed 1i"#PlanSort" -i $fullco
						regen_cooklist=yes
					fi
				else
					echo "$PACKAGE" >> $CACHE/removed
					sed -n '1,10p' -i $CACHE/removed
				fi
			fi
		fi
	done
	rm stamp
	echo "$updated_pkg" | sed 1d | while read PACKAGE pkg; do
		erase_package_info
		get_packages_info
	done
	unset updated_pkg
	
	# Look for new packages.
	for pkg in $(echo $pkg_repository/*.tazpkg | fgrep -v '*'); do
		if ! fgrep -q "  ${pkg##*/}" packages.$SUM; then
			get_packages_info
		fi
	done
	packages_db_end
}

# make package database
# $1 = incoming/packages or the folder of the package repo
pkgdb()
{
	case "$1" in
		incoming)
			PKGSDB="incoming" ;;
		packages)
			PKGSDB="packages" ;;
		*)
			[ "$1" ] && PKGSDB="$1"
			[ ! -d "$PKGSDB" ] && \
					gettext -e "\nPackages directory doesn't exist\n\n" && exit 1 ;;
	esac
	time=$(date +%s)
	echo "cook:pkgdb" > $command
	echo "Cook pkgdb: Creating all packages lists" | log
	echo ""
	gettext "Creating lists for: "; echo "$PKGSDB"
	separator
	gettext "Cook pkgdb started: "; date "+%Y-%m-%d %H:%M"
	if [ "$PKGSDB" = packages ]; then
		# Packages package db
		pkg_repository=$PKGS && gen_packages_db
		nb=$(ls $PKGS/*.tazpkg | wc -l)
		time=$(($(date +%s) - $time))
		echo -e "Packages: $nb - Time: ${time}s\n"
	elif [ "$PKGSDB" = incoming ]; then
		# Incoming package db
		pkg_repository=$INCOMING && gen_packages_db
		nb=$(ls $INCOMING/*.tazpkg | wc -l)
		time=$(($(date +%s) - $time))
		echo -e "Packages: $nb - Time: ${time}s\n"
	elif [ -d "$PKGSDB" ]; then
		# User path for package db
		pkg_repository=$PKGSDB && gen_packages_db
		nb=$(ls $PKGSDB/*.tazpkg | wc -l)
		time=$(($(date +%s) - $time))
		echo -e "Packages: $nb - Time: ${time}s\n"
	else
		pkg_repository=$PKGS && gen_packages_db
		nb=$(ls $PKGS/*.tazpkg | wc -l)
		time=$(($(date +%s) - $time))
		echo -e "Packages: $nb - Time: ${time}s\n"
		pkg_repository=$INCOMING && gen_packages_db
		incoming_nb=$(ls $INCOMING/*.tazpkg | wc -l)
		time=$(($(date +%s) - $time))
		echo -e "Incoming: $incoming_nb - Time: ${time}s\n"
	fi
		
	echo "" && rm -f $command
}

# clean chroot
clean_chroot()
{
	# Remove packages which was not in the chroot at creation time.
	if [ -f "$CACHE/chroot-pkgs" ]; then
		for pkg in $(ls ${root}${INSTALLED}); do
			[ -f ${root}${INSTALLED}/$pkg/receipt ] || continue	
			[ "$(grep ^$pkg$ $CACHE/chroot-pkgs)" ] || tazpkg remove $pkg --auto --root=$root
		done
		
		for pkg in $(ls ${root}${INSTALLED}); do
			if [ -d ${root}${INSTALLED}/$pkg -a ! -f ${root}${INSTALLED}/$pkg/receipt ]; then
				echo "empty: $pkg"
				rm -rf ${root}${INSTALLED}/$pkg
			fi
		done
		
		for pkg in $(cat $CACHE/chroot-pkgs); do
			if [ ! -d ${root}${INSTALLED}/$pkg ]; then
				echo "Reinstalling $pkg"
				tazpkg get-install $pkg --root=$root --forced
			fi
		done
	fi
}

# update library database file
update_lib_db()
{
	# Update lib_db
	libs=$(for file in $(find * -type f -not -name "*.o" -not -name "*.ko" -not -name "*.a"); do
	[ "$(dd if=$file bs=1 skip=1 count=3 2> /dev/null)" = "ELF" ] || continue
		LD_TRACE_LOADED_OBJECTS=1 /lib/ld*.so $PWD/$file
	done | { cut -f 1 -d ' ' | tr -d '\t' | sort -u | \
	sed -e 's/^linux-gate.so.*$/SLIB/' -e 's~^/lib/ld-.*$~SLIB~' \
		-e '/^statically$/d' | tr '\n' ' '; })
	
	if [ "$libs" ]; then
		libs=$(echo " $libs" | sed -r 's/( SLIB)+ / /g')
		echo -e "$PACKAGE\t$libs" >> $lib_db
		sort -o $lib_db $lib_db
		echo -e "$PACKAGE\t$libs" >> library.list
		sort -o library.list library.list
	fi
	unset libs
}

# Check for a specified file list on cmdline.
check_for_list()
{
	if [ ! "$LIST" ]; then
		echo -e "\nPlease specify the path to the list of packages to cook.\n" >&2
		exit 1
	elif ! [ -f "$LIST" ]; then
		echo -e "\nUnable to find $LIST packages list.\n" >&2
		exit 1
	elif ! [ -s "$LIST" ]; then
		echo -e "\nList is empty.\n" >&2
		exit 1
	fi
}

# get $PACKAGE wanted and depends info into wanted.txt and depends.txt files
get_packages_info_main()
{
	erase_package_info_main
	[ "$WANTED" ] && echo -e "$PACKAGE\t$WANTED" >> wanted.txt
	echo -e "$PACKAGE\t "$DEPENDS" \t "$BUILD_DEPENDS" " >> depends.txt
}

# erase $PACKAGE line in wanted.txt and depends.txt
erase_package_info_main()
{
	for i in wanted.txt depends.txt; do
		[ -f $i ] || continue
		sed "/^$PACKAGE\t/d" -i $i
	done
}
