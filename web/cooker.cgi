#!/bin/sh
#
# SliTaz Cooker CGI/web interface.
#

. /usr/lib/slitaz/httphelper.sh

[ -f "/etc/slitaz/cook.conf" ] && . /etc/slitaz/cook.conf
[ -f "cook.conf" ] && . ./cook.conf

# The same wok as cook.
wok="$WOK"

# Cooker DB files.
activity="$CACHE/activity"
commits="$CACHE/commits"
cooklist="$CACHE/cooklist"
cookorder="$CACHE/cookorder"
command="$CACHE/command"; touch $command
blocked="$CACHE/blocked"
broken="$CACHE/broken"
cooknotes="$CACHE/cooknotes"
cooktime="$CACHE/cooktime"
wokrev="$CACHE/wokrev"

# We're not logged and want time zone to display correct server date.
export TZ=$(cat /etc/TZ)

case "$QUERY_STRING" in
recook=*)
	case "$HTTP_USER_AGENT" in
	*SliTaz*)
		grep -qs "^${QUERY_STRING#recook=}$" $CACHE/recook-packages ||
		echo ${QUERY_STRING#recook=} >> $CACHE/recook-packages
	esac
	cat <<EOT
Location: ${HTTP_REFERER:-${REQUEST_URI%\?*}}

EOT
	exit ;;
poke)
	touch $CACHE/cooker-request
	cat <<EOT
Location: ${HTTP_REFERER:-${REQUEST_URI%\?*}}

EOT
	exit ;;
src*)
	file=$(busybox httpd -d "$SRC/${QUERY_STRING#*=}")
	cat <<EOT
Content-Type: application/octet-stream
Content-Length: $(stat -c %s "$file")
Content-Disposition: attachment; filename="$(basename "$file")"

EOT
	cat "$file"
	exit ;;
download*)
	file=$(busybox httpd -d "$PKGS/${QUERY_STRING#*=}")
	cat <<EOT
Content-Type: application/octet-stream
Content-Length: $(stat -c %s "$file")
Content-Disposition: attachment; filename="$(basename "$file")"

EOT
	cat "$file"
	exit ;;
rss)
	cat <<EOT
Content-Type: application/rss+xml

EOT
	;;
*)
	cat <<EOT
Content-Type: text/html; charset=utf-8

EOT
	;;
esac


# RSS feed generator
if [ "$QUERY_STRING" == 'rss' ]; then
	pubdate=$(date -R)
	cat <<EOT
<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
	<title>SliTaz Cooker</title>
	<description>The SliTaz packages cooker feed</description>
	<link>$COOKER_URL</link>
	<lastBuildDate>$pubdate</lastBuildDate>
	<pubDate>$pubdate</pubDate>
	<atom:link href="http://cook.slitaz.org/?rss" rel="self" type="application/rss+xml" />
EOT
	for rss in $(ls -lt $FEEDS/*.xml | head -n 12); do
		cat $rss | sed 's|<guid|& isPermaLink="false"|g;s|</pubDate| GMT&|g'
	done
	cat <<EOT
</channel>
</rss>
EOT
	exit 0
fi


#
# Functions
#


# Unpack to stdout

docat() {
	case "$1" in
		*gz)   zcat ;;
		*bz2) bzcat ;;
		*xz)  xzcat ;;
		*)      cat
	esac < $1
}


# Tiny texinfo browser

info2html() {
	sed \
		-e 's|&|\&amp;|g' -e 's|<|\&lt;|g' \
		-e 's|^\* \(.*\)::|* <a href="#\1">\1</a>  |' \
		-e 's|\*note \(.*\)::|<a href="#\1">\1</a>|' \
		-e '/^File: /s|(dir)|Top|g' \
		-e '/^File: /s|Node: \([^,]*\)|Node: <a name="\1"></a><u>\1</u>|' \
		-e '/^File: /s|Next: \([^,]*\)|Next: <a href="#\1">\1</a>|' \
		-e '/^File: /s|Prev: \([^,]*\)|Prev: <a href="#\1">\1</a>|' \
		-e '/^File: /s|Up: \([^,]*\)|Up: <a href="#\1">\1</a>|' \
		-e '/^File: /s|^.*$|<i>&</i>|' \
		-e '/^Tag Table:$/,/^End Tag Table$/d' \
		-e '/INFO-DIR/,/^END-INFO-DIR/d' \
		-e "s|https*://[^>),'\"\` ]*|<a href=\"&\">&</a>|g" \
		-e "s|ftp://[^>),\"\` ]*|<a href=\"&\">&</a>|g" \
		-e "s|^|</pre><pre>|"
}


# Put some colors in log and DB files.

syntax_highlighter() {
	case $1 in
		log)
			# If variables not defined - define them with some rare values
			: ${_src=#_#_#}
			: ${_install=#_#_#}
			: ${_fs=#_#_#}
			: ${_stuff=#_#_#}
			sed	-e 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g' \
				-e 's#OK$#<span class="span-ok">OK</span>#g' \
				-e 's#Done$#<span class="span-ok">Done</span>#g' \
				-e 's#done$#<span class="span-ok">done</span>#g' \
				-e 's#\([^a-z]\)ok$#\1<span class="span-ok">ok</span>#g' \
				-e 's#\([^a-z]\)yes$#\1<span class="span-ok">yes</span>#g' \
				-e 's#\([^a-z]\)no$#\1<span class="span-no">no</span>#g' \
				\
				-e 's#\( \[Y[nm/]\?\] n\)$# <span class="span-no">\1</span>#g' \
				-e 's#\( \[N[ym/]\?\] y\)$# <span class="span-ok">\1</span>#g' \
				-e 's#(NEW) $#<span class="span-red">(NEW) </span>#g' \
				\
				-e 's#.*(pkg/local).*#<span class="span-ok">\0</span>#g' \
				-e 's#.*(web/cache).*#<span class="span-no">\0</span>#g' \
				\
				-e 's#error$#<span class="span-red">error</span>#g' \
				-e 's#ERROR:#<span class="span-red">ERROR:</span>#g' \
				-e 's#Error#<span class="span-red">Error</span>#g' \
				\
				-e 's#^.*[Ff]ailed.*#<span class="span-red">\0</span>#g' \
				-e 's#^.*[Ff]atal.*#<span class="span-red">\0</span>#g' \
				-e 's#^.*[Nn]ot found.*#<span class="span-red">\0</span>#g' \
				-e 's#^.*[Nn]o such file.*#<span class="span-red">\0</span>#g' \
				\
				-e 's#WARNING:#<span class="span-red">WARNING:</span>#g' \
				-e 's#warning:#<span class="span-no">warning:</span>#g' \
				-e 's#error:#<span class="span-no">error:</span>#g' \
				-e 's#missing#<span class="span-no">missing</span>#g' \
				\
				-e 's#^.* will not .*#<span class="span-no">\0</span>#' \
				-e 's!^Hunk .* succeeded at .*!<span class="span-no">\0</span>!' \
				-e 's#^.* Warning: .*#<span class="span-no">\0</span>#' \
				\
				-e "s#^Executing:\([^']*\).#<span class='sh-val'>\0</span>#" \
				-e "s#^Making.*#<span class='sh-val'>\0</span>#" \
				-e "s#^====\([^']*\).#<span class='span-line'>\0</span>#g" \
				-e "s#^[a-zA-Z0-9]\([^']*\) :: #<span class='span-sky'>\0</span>#g" \
				-e "s#ftp://[^ '\"]*#<a href='\0'>\0</a>#g" \
				-e "s#http://[^ '\"]*#<a href='\0'>\0</a>#g" \
				-e "s|$_src|<span class='var'>\${src}</span>|g;
					s|$_install|<span class='var'>\${install}</span>|g;
					s|$_fs|<span class='var'>\${fs}</span>|g;
					s|$_stuff|<span class='var'>\${stuff}</span>|g" \
				-e "s|\[91m|<span style='color: #F00'>|;
					s|\[92m|<span style='color: #080'>|;
					s|\[93m|<span style='color: #FF0'>|;
					s|\[94m|<span style='color: #00F'>|;
					s|\[95m|<span style='color: #808'>|;
					s|\[96m|<span style='color: #0CC'>|;
					s|\[39m|</span>|;"
				;;

		receipt)
			sed	-e s'|&|\&amp;|g' -e 's|<|\&lt;|g' -e 's|>|\&gt;|'g \
				-e s"#^\#\([^']*\)#<span class='sh-comment'>\0</span>#"g \
				-e s"#\"\([^']*\)\"#<span class='sh-val'>\0</span>#"g ;;

		diff)
			sed -e 's|&|\&amp;|g' -e 's|<|\&lt;|g' -e 's|>|\&gt;|g' \
				-e s"#^-\([^']*\).#<span class='span-red'>\0</span>#"g \
				-e s"#^+\([^']*\).#<span class='span-ok'>\0</span>#"g \
				-e s"#@@\([^']*\)@@#<span class='span-sky'>@@\1@@</span>#"g ;;

		activity)
			sed s"#^\([^']* : \)#<span class='log-date'>\0</span>#"g ;;
	esac
}


# Latest build pkgs.

list_packages() {
	cd $PKGS
	ls -1t *.tazpkg | head -n20 | \
	while read file; do
		echo -n $(TZ=UTC stat -c '%y' $PKGS/$file | cut -d. -f1 | sed s/:[0-9]*$//)
		echo " : $file"
	done
}


# Optional full list button

more_button() {
	[ $(wc -l < ${3:-$CACHE/$1}) -gt ${4:-12} ] && cat <<EOT
<div style="float: right;">
	<a class="button" href="?file=$1">$2</a>
</div>
EOT
}


# Show the running command and its progression

running_command()
{
	local state="Not running"
	if [ -s "$command" ]; then
		state="$(cat $command)"
		set -- $(grep "^$state" $cooktime)
		if [ -n "$1" -a $2 -ne 0 ]; then
			state="$state $((($(date +%s)-$3)*100/$2))%"
			[ $2 -gt 300 ] && state="$state (should end $(date -u -d @$(($2+$3))))"
		fi
	fi
	echo $state
}


# xHTML header. Pages can be customized with a separated html.header file.

if [ -f "header.html" ]; then
	cat header.html
else
	cat <<EOT
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<title>SliTaz Cooker</title>
	<link rel="shortcut icon" href="favicon.ico">
	<link rel="stylesheet" href="style.css">
	<meta name="robots" content="nofollow">
</head>
<body>

<div id="header">
	<div id="logo"></div>
	<h1><a href="cooker.cgi">SliTaz Cooker</a></h1>
</div>

<!-- Content -->
<div id="content">
EOT
fi


#
# Load requested page
#

case "${QUERY_STRING}" in
	pkg=*)
		pkg=${QUERY_STRING#pkg=}
		log=$LOGS/$pkg.log
		echo "<h2>Package: $pkg</h2>"

		# Define cook variables for syntax highlighter
		if [ -s "$WOK/$pkg/receipt" ]; then
			. "$WOK/$pkg/receipt"
			_wok='/home/slitaz/wok'
			_src="$_wok/$pkg/source/$PACKAGE-$VERSION"
			_install="$_wok/$pkg/install"
			_fs="$_wok/$pkg/taz/$PACKAGE-$VERSION/fs"
			_stuff="$_wok/$pkg/stuff"
		fi

		# Package info.
		echo '<div id="info">'
		if [ -f "$wok/$pkg/receipt" ]; then
			echo "<a href='?receipt=$pkg'>receipt</a>"
			unset WEB_SITE
			unset WANTED
			bpkg=$pkg
			. $wok/$pkg/receipt

			[ -n "$WANTED" ] && bpkg="${WANTED%% *}" # see locale-* with multiple WANTED
			[ -n "$WEB_SITE" ] && # busybox wget -s $WEB_SITE &&
			echo "<a href='$WEB_SITE'>home</a>"

			if [ -f "$wok/$pkg/taz/$PACKAGE-$VERSION/receipt" ]; then
				echo "<a href='?files=$pkg'>files</a>"
				unset EXTRAVERSION
				. $wok/$pkg/taz/$PACKAGE-$VERSION/receipt
				if [ -f $wok/$pkg/taz/$PACKAGE-$VERSION/description.txt ]; then
					echo "<a href='?description=$pkg'>description</a>"
				fi
				if [ -f $PKGS/$PACKAGE-$VERSION$EXTRAVERSION.tazpkg ]; then
					echo "<a href='?download=$PACKAGE-$VERSION$EXTRAVERSION.tazpkg'>download</a>"
				fi
				if [ -f $PKGS/$PACKAGE-$VERSION$EXTRAVERSION-$ARCH.tazpkg ]; then
					echo "<a href='?download=$PACKAGE-$VERSION$EXTRAVERSION-$ARCH.tazpkg'>download</a>"
				fi
			fi
			[ -x ./man2html ] &&
			if [ -d $wok/$bpkg/install/usr/man ] ||
			   [ -d $wok/$bpkg/install/usr/share/man ] ||
			   [ -d $wok/$bpkg/taz/*/fs/usr/man ] ||
			   [ -d $wok/$bpkg/taz/*/fs/usr/share/man ]; then
				echo "<a href='?man=$bpkg'>man</a>"
			fi
			if [ -d $wok/$bpkg/install/usr/doc ] ||
			   [ -d $wok/$bpkg/install/usr/share/doc ] ||
			   [ -d $wok/$bpkg/taz/*/fs/usr/doc ] ||
			   [ -d $wok/$bpkg/taz/*/fs/usr/share/doc ]; then
				echo "<a href='?doc=$bpkg'>doc</a>"
			fi
			if [ -d $wok/$bpkg/install/usr/info ] ||
			   [ -d $wok/$bpkg/install/usr/share/info ] ||
			   [ -d $wok/$bpkg/taz/*/fs/usr/info ] ||
			   [ -d $wok/$bpkg/taz/*/fs/usr/share/info ]; then
				echo "<a href='?info=$bpkg'>info</a>"
			fi
			[ -n "$(echo $REQUEST_URI | sed 's|/[^/]*?pkg.*||')" ] ||
			echo "<a href='ftp://${HTTP_HOST%:*}/$pkg/'>browse</a>"
		else
			if [ $(ls $wok/*$pkg*/receipt 2>/dev/null | wc -l) -eq 0 ]; then
				echo "No package named: $pkg"
			else
				ls $wok/$pkg/receipt >/dev/null 2>&1 || pkg="*$pkg*"
				echo '<table style="width:100%">'
				for i in $(cd $wok ; ls $pkg/receipt); do
					pkg=$(dirname $i)
					unset SHORT_DESC CATEGORY
					. $wok/$pkg/receipt
					cat <<EOT
<tr>
<td><a href="?pkg=$pkg">$pkg</a></td>
<td>$SHORT_DESC</td>
<td>$CATEGORY</td>
</tr>
EOT
				done
				echo '</table>'
				unset pkg
			fi
		fi
		echo '</div>'

		# Check for a log file and display summary if it exists.
		if [ -f "$log" ]; then
			if grep -q "cook:$pkg$" $command; then
				echo "<pre>The Cooker is currently building: $pkg</pre>"
			fi
			if fgrep -q "Summary for:" $LOGS/$pkg.log; then
				echo '<h3>Cook summary</h3>'
				echo '<pre>'
				grep -A 12 "^Summary for:" $LOGS/$pkg.log | sed /^$/d | \
					syntax_highlighter log
				echo '</pre>'
			fi
			if fgrep -q "Debug information" $LOGS/$pkg.log; then
				echo '<h3>Cook failed</h3>'
				echo '<pre>'
				grep -A 8 "^Debug information" $LOGS/$pkg.log | sed /^$/d | \
						syntax_highlighter log
				echo '</pre>'
			fi
			echo "<h3>Cook log $(stat -c %y $log | sed 's/:..\..*//')</h3>"
			for i in $(ls -t $log.*); do
				echo -n "<a href=\"?log=$(basename $i)\">"
				echo "$(stat -c %y $i | sed 's/ .*//')</a>"
			done
			echo '<pre>'
			cat $log | syntax_highlighter log
			echo '</pre>'
			case "$HTTP_USER_AGENT" in
			*SliTaz*)
				[ -f $CACHE/cooker-request ] && [ -n "$HTTP_REFERER" ] &&
				echo "<a class=\"button\" href=\"?recook=$pkg\">Recook $pkg</a>"
			esac
		else
			[ "$pkg" ] && echo "<pre>No log: $pkg</pre>"
		fi ;;

	log=*)
		log=$LOGS/${QUERY_STRING#log=}
		if [ -s $log ]; then
			echo "<h3>Cook log $(stat -c %y $log | sed 's/:..\..*//')</h3>"
			if fgrep -q "Summary" $log; then
				echo '<pre>'
				grep -A 20 "^Summary" $log | sed /^$/d | \
					syntax_highlighter log
				echo '</pre>'
			fi
			echo '<pre>'
			cat $log | syntax_highlighter log
			echo '</pre>'
		fi
		;;
	file=*)
		# Don't allow all files on the system for security reasons.
		file=${QUERY_STRING#file=}
		case "$file" in
			activity|cooknotes|cooklist)
				[ "$file" == "cooklist" ] && \
					nb="- Packages: $(cat $cooklist | wc -l)"
				echo "<h2>DB: $file $nb</h2>"
				echo '<pre>'
				tac $CACHE/$file | syntax_highlighter activity
				echo '</pre>' ;;

			broken)
				nb=$(cat $broken | wc -l)
				echo "<h2>DB: broken - Packages: $nb</h2>"
				echo '<pre>'
				cat $CACHE/$file | sort | \
					sed s"#^[^']*#<a href='?pkg=\0'>\0</a>#"g
				echo '</pre>' ;;

			*.diff)
				diff=$CACHE/$file
				echo "<h2>Diff for: ${file%.diff}</h2>"
				[ "$file" == "installed.diff" ] && echo \
					"<p>This is the latest diff between installed packages \
					and installed build dependencies to cook.</p>"
				echo '<pre>'
				cat $diff | syntax_highlighter diff
				echo '</pre>' ;;

			*.log)
				log=$LOGS/$file
				name=$(basename $log)
				echo "<h2>Log for: ${name%.log}</h2>"
				if [ -f "$log" ]; then
					if fgrep -q "Summary" $log; then
						echo '<pre>'
						grep -A 20 "^Summary" $log | sed /^$/d | \
							syntax_highlighter log
						echo '</pre>'
					fi
					echo '<pre>'
					cat $log | syntax_highlighter log
					echo '</pre>'
				else
					echo "<pre>No log file: $log</pre>"
				fi ;;
		esac ;;

	stuff=*)
		file=${QUERY_STRING#stuff=}
		echo "<h2>$file</h2>"
		echo '<pre>'
		cat $wok/$file | sed 's/&/\&amp;/g;s/</\&lt;/g;s/>/\&gt;/g'
		echo '</pre>' ;;

	receipt=*)
		pkg=${QUERY_STRING#receipt=}
		echo "<h2>Receipt for: $pkg</h2>"
		if [ -f "$wok/$pkg/receipt" ]; then
			. $wok/$pkg/receipt
			[ -n "$TARBALL" ] && [ -s "$SRC/$TARBALL" ] &&
			echo "<a href='?src=$TARBALL'>source</a>"

			( cd $wok/$pkg ; find stuff -type f 2> /dev/null ) | \
			while read file ; do
				echo "<a href=\"?stuff=$pkg/$file\">$file</a>"
			done | sort
			echo '<pre>'
			cat $wok/$pkg/receipt | \
				syntax_highlighter receipt
			echo '</pre>'
		else
			echo "<pre>No receipt for: $pkg</pre>"
		fi ;;

	files=*)
		pkg=${QUERY_STRING#files=}
		dir=$(ls -d $WOK/$pkg/taz/$pkg-*)
		if [ -d "$dir/fs" ]; then
			echo "<h2>Installed files by: $pkg ($(du -hs $dir/fs | awk '{ print $1 }'))</h2>"
			echo '<pre>'
			find $dir/fs -not -type d -print0 | xargs -0 ls -ld | \
				sed "s|\(.*\) /.*\(${dir#*wok}/fs\)\(.*\)|\1 <a href=\"?download=../wok\2\3\">\3</a>|;s|^\([^-].*\)\(<a.*\)\">\(.*\)</a>|\1\3|"
			echo '</pre>'
		else
			echo "<pre>No files list for: $pkg</pre>"
		fi ;;

	description=*)
		pkg=${QUERY_STRING#description=}
		echo "<h2>Description of $pkg</h2>"
		dir=$(ls -d $WOK/$pkg/taz/$pkg-*)
		if [ -s "$dir/description.txt" ]; then
			echo '<pre>'
			cat $dir/description.txt | \
				sed 's/&/\&amp;/g;s/</\&lt;/g;s/>/\&gt;/g'
			echo '</pre>'
		else
			echo "<pre>No description for: $pkg</pre>"
		fi ;;

	man=*|doc=*|info=*)
		type=${QUERY_STRING%%=*}
		pkg=$(GET $type)
		dir=$WOK/$pkg/install/usr/share/$type
		[ -d $dir ] || dir=$WOK/$pkg/install/usr/$type
		[ -d $dir ] || dir=$(echo $WOK/$pkg/taz/*/fs/usr/share/$type)
		[ -d $dir ] || dir=$(echo $WOK/$pkg/taz/*/fs/usr/$type)
		page=$(GET file)
		if [ -z "$page" ]; then
			page=$(find $dir -type f | sed q)
			page=${page#$dir/}
		fi
		find $dir -type f | while read file ; do
			[ -s $file ] || continue
			case "$file" in
			*.jp*g|*.png|*.gif|*.svg) continue
			esac
			file=${file#$dir/}
			echo "<a href='?$type=$pkg&amp;file=$file'>$(basename $file)</a>"
		done | sort -t \> -k 2
		echo "<h2>$(basename $page)</h2>"
		tmp="$(mktemp)"
		docat "$dir/$page" > $tmp
		[ -s "$tmp" ] && case "$type" in
		info)
			echo '<pre>'
			info2html < "$tmp"
			echo '</pre>' ;;
		doc)
			echo '<pre>'
			case "$page" in
			*.htm*)	cat ;;
			*)	sed 's/&/\&amp;/g;s/</\&lt;/g;s/>/\&gt;/g'
			esac < "$tmp"
			echo '</pre>' ;;
		man)
			export TEXTDOMAIN='man2html'
			./man2html "$tmp" | sed -e '1,/<header>/d' \
			-e 's|<a href="file:///[^>]*>\([^<]*\)</a>|\1|g' \
			-e 's|<a href="?[1-9]\+[^>]*>\([^<]*\)</a>|\1|g' ;;
		esac
		rm -f $tmp
		;;
	*)
		# We may have a toolchain.cgi script for cross cooker's
		if [ -f "toolchain.cgi" ]; then
			toolchain='toolchain.cgi'
		else
			toolchain='?pkg=slitaz-toolchain'
		fi
		# Main page with summary. Count only package include in ARCH,
		# use 'cooker arch-db' to manually create arch.$ARCH files.
		inwok=$(ls $WOK/*/arch.$ARCH | wc -l)
		cooked=$(ls $PKGS/*.tazpkg | wc -l)
		unbuilt=$(($inwok - $cooked))
		pct=0
		[ $inwok -gt 0 ] && pct=$(( ($cooked * 100) / $inwok ))
		cat <<EOT
<div style="float: right;">
	<form method="get" action="$SCRIPT_NAME">
		Package:
		<input type="text" name="pkg" />
	</form>
</div>

<h2>Summary</h2>

<pre>
Running command  : $(running_command)
Wok revision     : <a href="$WOK_URL">$(cat $wokrev)</a>
Commits to cook  : $(cat $commits | wc -l)
Current cooklist : $(cat $cooklist | wc -l)
Broken packages  : $(cat $broken | wc -l)
Blocked packages : $(cat $blocked | wc -l)
</pre>
EOT
		[ -e $CACHE/cooker-request ] &&
		[ $CACHE/activity -nt $CACHE/cooker-request ] && cat <<EOT
<div style="float: right;">
	<a class="button" href="?poke">Poke cooker</a>
</div>
EOT
		cat <<EOT
<p class="info">
	Packages: $inwok in the wok | $cooked cooked | $unbuilt unbuilt |
	Server date: $(date -u '+%F %R %Z')
</p>
<div class="pctbar">
	<div class="pct" style="width: ${pct}%;">${pct}%</div>
</div>

<p>
	Latest:
	<a href="?file=cookorder.log">cookorder.log</a>
	<a href="?file=commits.log">commits.log</a>
	<a href="?file=pkgdb.log">pkgdb.log</a>
	<a href="?file=installed.diff">installed.diff</a>
	- Architecture $ARCH:
	<a href="$toolchain">toolchain</a>
</p>

$(more_button activity "More activity" $CACHE/activity 12)
<h2 id="activity">Activity</h2>
<pre>
$(tac $CACHE/activity | head -n 12 | syntax_highlighter activity)
</pre>
EOT

		[ -s $cooknotes ] && cat <<EOT
$(more_button cooknotes "More notes" $cooknotes 12)
<h2 id="cooknotes">Cooknotes</h2>
<pre>
$(tac $cooknotes | head -n 12 | syntax_highlighter activity)
</pre>
EOT

		[ -s $commits ] && cat <<EOT
<h2 id="commits">Commits</h2>
<pre>
$(cat $commits)
</pre>
EOT

		[ -s $cooklist ] && cat <<EOT
$(more_button cooklist "Full cooklist" $cooklist 20)
<h2 id="cooklist">Cooklist</h2>
<pre>
$(cat $cooklist | head -n 20)
</pre>
EOT

		[ -s $broken ] && cat <<EOT
$(more_button broken "All broken packages" $broken 20)
<h2 id="broken">Broken</h2>
<pre>
$(cat $broken | head -n 20 | sed s"#^[^']*#<a href='?pkg=\0'>\0</a>#"g)
</pre>
EOT

		[ -s $blocked ] && cat <<EOT
<h2 id="blocked">Blocked</h2>
<pre>
$(cat $blocked | sed s"#^[^']*#<a href='?pkg=\0'>\0</a>#"g)
</pre>
EOT

		cat <<EOT
<h2 id="lastcook">Latest cook</h2>
<pre>
$(list_packages | sed s"#^\([^']*\).* : #<span class='log-date'>\0</span>#"g)
</pre>
EOT
	;;
esac


# Close xHTML page

cat <<EOT
</div>

<div id="footer">
	<a href="http://www.slitaz.org/">SliTaz Website</a>
	<a href="cooker.cgi">Cooker</a>
	<a href="doc/cookutils/cookutils.en.html">Documentation</a>
</div>

</body>
</html>
EOT

exit 0
