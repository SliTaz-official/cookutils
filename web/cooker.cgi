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

# Path to sundown (markdown to html convertor)
if [ -n "$(which sundown 2>/dev/null)" ]; then
	SUNDOWN=$(which sundown)
elif [ -x "./sundown" ]; then
	SUNDOWN="./sundown"
fi

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
		exit
		;;

	poke)
		touch $CACHE/cooker-request
		cat <<EOT
Location: ${HTTP_REFERER:-${REQUEST_URI%\?*}}

EOT
		exit
		;;

	src*)
		file=$(busybox httpd -d "$SRC/${QUERY_STRING#*=}")
		cat <<EOT
Content-Type: application/octet-stream
Content-Length: $(stat -c %s "$file")
Content-Disposition: attachment; filename="$(basename "$file")"

EOT
		cat "$file"
		exit
		;;

	download*)
		file=$(busybox httpd -d "$PKGS/${QUERY_STRING#*=}")
		content_type='application/octet-stream'
		case $file in
			*.txt|*.conf|*/README|*/receipt)
			              content_type='text/plain; charset=UTF-8' ;;
			*.css)        content_type='text/css; charset=UTF-8' ;;
			*.htm|*.html) content_type='text/html; charset=UTF-8' ;;
			*.js)         content_type='application/javascript; charset=UTF-8' ;;
			*.desktop)    content_type='application/x-desktop; charset=UTF-8' ;;
			*.png)        content_type='image/png' ;;
			*.svg)        content_type='image/svg+xml' ;;
			*.jpg|*.jpeg) content_type='image/jpeg' ;;
			*.sh|*.cgi)   content_type='application/x-shellscript' ;;
			*.gz)         content_type='application/gzip' ;;
			*.ico)        content_type='image/vnd.microsoft.icon' ;;
		esac
		echo "Content-Type: $content_type"
		echo "Content-Length: $(stat -c %s "$file")"
		[ "$content_type" == 'application/octet-stream' ] &&
		echo "Content-Disposition: attachment; filename=\"$(basename "$file")\""

		echo

		cat "$file"
		exit
		;;

	rss)
		echo -e 'Content-Type: application/rss+xml\n'
		;;

	*)
		echo -e 'Content-Type: text/html; charset=UTF-8\n'
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
		-e "s|^|</pre><pre class='info'>|"
}


htmlize() {
	sed -e 's|&|\&amp;|g; s|<|\&lt;|g; s|>|\&gt;|g'
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
					s|\[96m|<span style='color: #088'>|;
					s|\[39m|</span>|;"
			;;

		files)
			sed \
				-e "s|\[[01];31m|<span style='color: #F00'>|g;
					s|\[[01];32m|<span style='color: #080'>|g;
					s|\[[01];33m|<span style='color: #FF0'>|g;
					s|\[[01];34m|<span style='color: #00F'>|g;
					s|\[[01];35m|<span style='color: #808'>|g;
					s|\[[01];36m|<span style='color: #088'>|g;
					s|\[[01];0m|<span style='color: #333'>|g;
					s|\[0m|</span>|g;"
			;;

		receipt)
			sed	-e s'|&|\&amp;|g' -e 's|<|\&lt;|g' -e 's|>|\&gt;|'g \
				-e s"#^\#\([^']*\)#<span class='sh-comment'>\0</span>#"g \
				-e s"#\"\([^']*\)\"#<span class='sh-val'>\0</span>#"g
			;;

		diff)
			sed -e 's|&|\&amp;|g' -e 's|<|\&lt;|g' -e 's|>|\&gt;|g' \
				-e s"#^-\([^']*\).#<span class='span-red'>\0</span>#"g \
				-e s"#^+\([^']*\).#<span class='span-ok'>\0</span>#"g \
				-e s"#@@\([^']*\)@@#<span class='span-sky'>@@\1@@</span>#"g
			;;

		activity)
			sed s"#^\([^']* : \)#<span class='log-date'>\0</span>#"g
			;;
	esac
}


# Latest build pkgs.

list_packages() {
	cd $PKGS
	ls -1t *.tazpkg | head -n 20 | \
	while read file; do
		echo -n $(TZ=UTC stat -c '%y' $PKGS/$file | cut -d. -f1 | sed s/:[0-9]*$//)
		echo " : $file"
	done
}


# Optional full list button

more_button() {
	[ $(wc -l < ${3:-$CACHE/$1}) -gt ${4:-12} ] &&
	echo "<a class='button r' href='?file=$1'>$2</a>"
}


# Show the running command and its progression

running_command() {
	local state="Not running"
	if [ -s "$command" ]; then
		state="$(cat $command)"
		set -- $(grep "^$state" $cooktime)
		if [ -n "$1" ]; then
			state="$state $((($(date +%s)-$3)*100/$2))%"
			[ $2 -gt 300 ] && state="$state (should end $(date -u -d @$(($2+$3))))"
		fi
	fi
	echo $state
}


datalist() {
	(
		cd $wok

		ls | awk '
		BEGIN{printf("<datalist id=\"packages\">")}
		     {printf("<option>%s</option>",$1)}
		END  {printf("</datalist>")}
		'
	)
}


summary() {
	log="$1"
	pkg="$(basename ${log%%.log*})"
	if [ -f "$log" ]; then
		if grep -q "cook:$pkg$" $command; then
			echo "<pre>The Cooker is currently building: $pkg</pre>"
		fi
		if fgrep -q "Summary for:" $log; then
			echo "<pre>"
			sed '/^Summary for:/,$!d' $log | sed /^$/d | syntax_highlighter log
			echo "</pre>"
		fi

		if fgrep -q "Debug information" $log; then
			echo '<pre>'
			sed '/^Debug information/,$!d' $log | sed /^$/d | \
			if [ -n "$2" ]; then
				syntax_highlighter log | \
				sed 's|\([0-9][0-9]*\):|<a href="#l\1">\1</a>:|'
			else
				sed 's|^[0-9][0-9]*:||' | syntax_highlighter log
			fi
			echo '</pre>'
		fi
	else
		[ -n "$pkg" -a -d "$wok/$pkg" ] && echo "<pre>No log for $pkg</pre>"
	fi
}


pkg_info() {
	local log cmd active bpkg
	log=$LOGS/$pkg.log
	cmd=${QUERY_STRING%%=*}
	echo '<div id="info">'
	active=''; [ "$cmd" == 'receipt' -o "$cmd" == 'stuff' ] && active=' active'
	echo "<a class='button green$active' href='?receipt=$pkg'>receipt &amp; stuff</a>"

	unset WEB_SITE WANTED
	bpkg=$pkg
	. $wok/$pkg/receipt

	[ -n "$WANTED" ] && bpkg="${WANTED%% *}" # see locale-* with multiple WANTED

	[ -n "$WEB_SITE" ] &&
	echo "<a class='button sky' href='$WEB_SITE'>web site</a>"

	if [ -f "$wok/$pkg/taz/$PACKAGE-$VERSION/receipt" ]; then
		active=''; [ "$cmd" == 'files' ] && active=' active'
		echo "<a class='button khaki$active' href='?files=$pkg'>files</a>"

		unset EXTRAVERSION
		. $wok/$pkg/taz/$PACKAGE-$VERSION/receipt

		if [ -f $wok/$pkg/taz/$PACKAGE-$VERSION/description.txt ]; then
			active=''; [ "$cmd" == 'description' ] && active=' active'
			echo "<a class='button brown$active' href='?description=$pkg'>description</a>"
		fi

		if [ -f $PKGS/$PACKAGE-$VERSION$EXTRAVERSION.tazpkg ]; then
			echo "<a class='button gold' href='?download=$PACKAGE-$VERSION$EXTRAVERSION.tazpkg'>download</a>"
		fi

		if [ -f $PKGS/$PACKAGE-$VERSION$EXTRAVERSION-$ARCH.tazpkg ]; then
			echo "<a class='button gold' href='?download=$PACKAGE-$VERSION$EXTRAVERSION-$ARCH.tazpkg'>download</a>"
		fi
	fi

	[ -n "$TARBALL" ] && [ -s "$SRC/$TARBALL" ] &&
	echo "<a class='button yellow' href='?src=$TARBALL'>source</a>"

	[ -x ./man2html ] &&
	if [ -d $wok/$bpkg/install/usr/man ] ||
	   [ -d $wok/$bpkg/install/usr/share/man ] ||
	   [ -d $wok/$bpkg/taz/*/fs/usr/man ] ||
	   [ -d $wok/$bpkg/taz/*/fs/usr/share/man ]; then
		active=''; [ "$cmd" == 'man' ] && active=' active'
		echo "<a class='button plum$active' href='?man=$bpkg'>man</a>"
	fi

	if [ -d $wok/$bpkg/install/usr/doc ] ||
	   [ -d $wok/$bpkg/install/usr/share/doc ] ||
	   [ -d $wok/$bpkg/taz/*/fs/usr/doc ] ||
	   [ -d $wok/$bpkg/taz/*/fs/usr/share/doc ]; then
		active=''; [ "$cmd" == 'doc' ] && active=' active'
		echo "<a class='button plum$active' href='?doc=$bpkg'>doc</a>"
	fi

	if [ -d $wok/$bpkg/install/usr/info ] ||
	   [ -d $wok/$bpkg/install/usr/share/info ] ||
	   [ -d $wok/$bpkg/taz/*/fs/usr/info ] ||
	   [ -d $wok/$bpkg/taz/*/fs/usr/share/info ]; then
		active=''; [ "$cmd" == 'info' ] && active=' active'
		echo "<a class='button plum$active' href='?info=$bpkg'>info</a>"
	fi

	[ -n "$(echo $REQUEST_URI | sed 's|/[^/]*?pkg.*||')" ] ||
	echo "<a class='button' href='ftp://${HTTP_HOST%:*}/$pkg/'>browse</a>"

	if [ -s "$log" ]; then
		active=''; [ "$cmd" == 'log' ] && active=' active'
		echo "<a class='button gray$active' href='?log=$pkg.log'>logs</a>"
	fi

	echo '</div>'
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
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>SliTaz Cooker</title>
	<link rel="shortcut icon" href="favicon.ico">
	<link rel="stylesheet" href="style.css">
	<script src="prism.js"></script>
	<link rel="stylesheet" href="prism.css">
	<link rel="alternate" type="application/rss+xml" title="Cooker Feed" href="?rss">
	<meta name="robots" content="nofollow">
</head>
<body>

<div id="header">
	<div id="logo"></div>
	<h1><a href="cooker.cgi">SliTaz Cooker</a></h1>
</div>
EOT
fi


#
# Load requested page
#

case "${QUERY_STRING}" in
	pkg=*)
		pkg=${QUERY_STRING#pkg=}
		log=$LOGS/$pkg.log
		echo "<div id='content'>"
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
		if [ -f "$wok/$pkg/receipt" ]; then
			pkg_info
		else
			if [ $(ls $wok/*$pkg*/receipt 2>/dev/null | wc -l) -eq 0 ]; then
				echo "No package named: $pkg"
			else
				ls $wok/$pkg/receipt >/dev/null 2>&1 || pkg="*$pkg*"
				echo '<table class="zebra" style="width:100%">'
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

		# Check for a log file and display summary if it exists.
		summary "$log"
		if [ -f "$log" ]; then
			case "$HTTP_USER_AGENT" in
				*SliTaz*)
					[ -f $CACHE/cooker-request ] && [ -n "$HTTP_REFERER" ] &&
					echo "<a class=\"button\" href=\"?recook=$pkg\">Recook $pkg</a>"
					;;
			esac
		fi
		;;

	log=*)
		log=${QUERY_STRING#log=}
		logfile=$LOGS/$log
		pkg=${log%.log*}
		if [ -s "$logfile" ]; then
			echo "<div id='content'>"

			echo "<h2>Cook log $(stat -c %y $logfile | sed 's/:..\..*//')</h2>"
			pkg_info

			case $log in
				*.log) baselog=$logfile ;;
				*)     baselog=${logfile%.*} ;;
			esac
			for i in $(ls -t $baselog $baselog.* 2>/dev/null); do
				class=''; [ $i == $logfile ] && class=' gray'
				echo -n "<a class='button$class' href=\"?log=$(basename $i)\">"
				echo "$(stat -c %y $i | cut -d: -f1,2)</a>"
			done

			summary "$logfile" links

			cat $logfile | syntax_highlighter log | awk '
			BEGIN { print "<pre class=\"log\">"; }
			      { printf("<a name=\"l%d\" href=\"#l%d\">%5d</a>  %s\n", NR, NR, NR, $0); }
			END   { print "</pre>"; }
			'
		fi
		;;

	file=*)
		echo "<div id='content'>"
		# Don't allow all files on the system for security reasons.
		file=${QUERY_STRING#file=}
		case "$file" in
			activity|cooknotes|cooklist)
				[ "$file" == "cooklist" ] && \
					nb="- Packages: $(cat $cooklist | wc -l)"
				echo '<div id="content2">'
				echo "<h2>DB: $file $nb</h2>"
				echo '<ul class="activity">'
				tac $CACHE/$file | syntax_highlighter activity | \
				sed 's|^|<li>|; s|$|</li>|'
				echo '</ul></div>'
				;;

			broken)
				nb=$(wc -l < $broken)
				echo '<div id="content2">'
				echo "<h2>DB: broken - Packages: $nb</h2>"
				echo '<ul class="activity">'
				cat $CACHE/$file | sort | \
					sed "s#^[^']*#<a href='?pkg=\0'>\0</a>#g" | \
					sed 's|^|<li>|; s|$|</li>|'
				echo '</ul></div>'
				;;

			*.diff)
				diff=$CACHE/$file
				echo "<h2>Diff for: ${file%.diff}</h2>"
				[ "$file" == "installed.diff" ] && echo \
					"<p>This is the latest diff between installed packages \
					and installed build dependencies to cook.</p>"
				echo '<pre>'
				cat $diff | syntax_highlighter diff
				echo '</pre>'
				;;

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
				fi
				;;
		esac
		;;

	stuff=*)
		echo "<div id='content'>"
		file=${QUERY_STRING#stuff=}
		pkg=${file%%/*}
		if [ -f "$wok/$file" ]; then
			echo "<h2>$file</h2>"
			pkg_info
			echo "<a class='button' href='?receipt=$pkg'>receipt</a>"

			( cd $wok/$pkg ; find stuff -type f 2> /dev/null ) | sort | \
			while read i ; do
				class=''; [ "$pkg/$i" == "$file" ] && class=" green"
				echo "<a class='button$class' href='?stuff=$pkg/$i'>$i</a>"
			done

			case $file in
				*.desktop|*.theme) class="ini" ;;
				*.patch|*.diff|*.u)  class="diff" ;;
				*.sh)         class="bash" ;;
				*.conf*)
					class="bash"
					[ -n "$(cut -c1 < $wok/$file | fgrep '[')" ] && class="ini"
					;;
				*.pl)           class="perl" ;;
				*.c|*.h|*.awk)  class="clike" ;;
				*.svg)          class="svg" ;;
				*Makefile*)     class="makefile" ;;
				*.po|*.pot)     class="bash" ;;
				*.css)          class="css" ;;
				*.htm|*.html)   class="html" ;;
				*.js)           class="js" ;;
				*.txt)          class="asciidoc" ;;
				*)
					case $(head -n1 $wok/$file) in
						*!/bin/sh*|*!/bin/bash*) class="bash" ;;
					esac
					if [ -z "$class" -a "$(head -n1 $wok/$file | cut -b1)" == '#' ]; then
						class="bash"
					fi
					if [ -z "$class" ]; then
						# Follow Busybox restrictions. Search for non-printable chars
						if [ $(tr -d '[:alnum:][:punct:][:blank:][:cntrl:]' < "$wok/$file" | wc -c) -gt 0 ]; then
							raw="true"
						fi
					fi
					;;
			esac

			# Display image
			case $file in
				*.png|*.svg|*.jpg|*.jpeg|*.ico)
					echo "<img src='?download=../wok/$file' style='display: block; max-width: 100%; margin: auto'/>"
					;;
			esac

			# Display colored listing (also for *.svg)
			case $file in
				*.png|*.jpg|*.jpeg|*.ico) ;;
				*)
					if [ -z "$raw" ]; then
						echo -n "<pre><code class='language-$class'>"
						cat $wok/$file | sed 's|&|\&amp;|g; s|<|\&lt;|g; s|>|\&gt;|g'
						echo '</code></pre>'
					fi
					;;
			esac

			# Display hex dump for binary files
			if [ -n "$raw" ]; then
				echo -n "<pre><code class='language-$class'>"
				hexdump -C $wok/$file | sed 's|&|\&amp;|g; s|<|\&lt;|g; s|>|\&gt;|g'
				echo '</code></pre>'
			fi
		else
			echo "<pre>File '$file' absent!</pre>"
		fi
		;;

	receipt=*)
		echo "<div id='content'>"
		pkg=${QUERY_STRING#receipt=}
		if [ -f "$wok/$pkg/receipt" ]; then
			echo "<h2>Receipt for: $pkg</h2>"
			pkg_info
			echo "<a class='button green' href='?receipt=$pkg'>receipt</a>"
			. $wok/$pkg/receipt

			( cd $wok/$pkg; find stuff -type f 2> /dev/null ) | sort | \
			while read file; do
				echo "<a class='button' href='?stuff=$pkg/$file'>$file</a>"
			done | sort
			echo -n '<pre><code class="language-bash">'
			cat $wok/$pkg/receipt | htmlize
			echo '</code></pre>'
		else
			echo "<pre>No receipt for: $pkg</pre>"
		fi
		;;

	files=*)
		echo "<div id='content'>"
		pkg=${QUERY_STRING#files=}
		dir=$(ls -d $WOK/$pkg/taz/$pkg-* 2>/dev/null)
		if [ -d "$dir/fs" ]; then
			size=$(du -hs $dir/fs | awk '{ print $1 }')
			echo "<h2>Files installed by the package \"$pkg\" ($size)</h2>"
			pkg_info
			#echo "<a class='button gray' href='?pkg=$pkg'>‹ back</a>"

			echo '<pre class="files">'

			find $dir/fs -not -type d -print0 | \
			xargs -0 ls -ld --color=always | \
			syntax_highlighter files | \
			sed "s|\([^/]*\)/.*\(${dir#*wok}/fs\)\([^<]*\)\(<.*\)$|\1<a href=\"?download=../wok\2\3\">\3</a>\4|"

			echo '</pre>'
		else
			echo "<h2>No files list for \"$pkg\"</h2>"
			echo "<a class='button gray' href='?pkg=$pkg'>‹ back</a>"
		fi
		;;

	description=*)
		echo "<div id='content'>"
		pkg=${QUERY_STRING#description=}
		dir=$(ls -d $WOK/$pkg/taz/$pkg-* 2>/dev/null)
		if [ -s "$dir/description.txt" ]; then
			echo "<h2>Description of $pkg</h2>"
			pkg_info
			if [ -x "$SUNDOWN" ]; then
				echo '<div id="content2">'
				$SUNDOWN $dir/description.txt
				echo '</div>'
			else
				echo '<pre><code class="language-markdown">'
				cat $dir/description.txt | \
					sed 's/&/\&amp;/g;s/</\&lt;/g;s/>/\&gt;/g'
				echo '</code></pre>'
			fi
		else
			echo "<pre>No description for: $pkg</pre>"
		fi
		;;

	man=*|doc=*|info=*)
		echo '<div id="content">'
		type=${QUERY_STRING%%=*}
		pkg=$(GET $type)
		if [ -d "$wok/$pkg" ]; then
			dir=$WOK/$pkg/install/usr/share/$type
			[ -d $dir ] || dir=$WOK/$pkg/install/usr/$type
			[ -d $dir ] || dir=$(echo $WOK/$pkg/taz/*/fs/usr/share/$type)
			[ -d $dir ] || dir=$(echo $WOK/$pkg/taz/*/fs/usr/$type)
			page=$(GET file)
			if [ -z "$page" ]; then
				page=$(find $dir -type f | sed q)
				page=${page#$dir/}
			fi

			echo "<h2>$(basename $page)</h2>"

			pkg_info
			echo '<div style="max-height: 5em; overflow: auto">'
			find $dir -type f | sort | while read i ; do
				[ -s $i ] || continue
				case "$i" in
					*.jp*g|*.png|*.gif|*.svg|*.css) continue
				esac
				i=${i#$dir/}
				class=''; [ "$page" == "$i" ] && class=" plum"
				echo "<a class='button$class' href='?$type=$pkg&amp;file=$i'>$(basename $i .gz)</a>"
			done | sort -t \> -k 2
			echo '</div>'

			if [ -f "$dir/$page" ]; then
				tmp="$(mktemp)"
				docat "$dir/$page" > $tmp
				[ -s "$tmp" ] &&
				case "$type" in
					info)
						echo '<div id="content2">'
						echo '<pre class="info">'
						info2html < "$tmp"
						echo '</pre></div>'
						;;
					doc)
						case "$page" in
							*.sgml) class='xml';;
							*)      class='asciidoc';;
						esac
						case "$page" in
							*.htm*)
								echo '<div id="content2">'
								cat
								echo '</div>'
								;;
							*)
								echo "<pre><code class=\"language-$class\">"
								sed 's/&/\&amp;/g;s/</\&lt;/g;s/>/\&gt;/g'
								echo '</code></pre>'
								;;
						esac < "$tmp"
						;;
					man)
						export TEXTDOMAIN='man2html'
						echo "<div id='content2'>"

						html=$(./man2html "$tmp" | sed -e '1,/<header>/d' \
						-e 's|<a href="file:///[^>]*>\([^<]*\)</a>|\1|g' \
						-e 's|<a href="?[1-9]\+[^>]*>\([^<]*\)</a>|\1|g')

						if [ -n "$(echo "$html" | fgrep 'The requested file /tmp/tmp.')" ]; then
							# Process the pre-formatted man-cat page
							echo '<pre>'
							sed '
								s|M-bM-^@M-^S|—|g;
								s|M-bM-^@M-^\\|<b>|g;
								s|M-bM-^@M-^]|</b>|g
								s|M-bM-^@M-^X|<u>|g;
								s|M-bM-^@M-^Y|</u>|g;
								s|M-BM-||g;
								' "$tmp"
							echo '</pre>'
						else
							echo "$html"
						fi
						echo "</div>"
						;;
				esac
				rm -f $tmp
			else
				echo "<pre>File '$page' not exists!</pre>"
			fi
		else
			echo "<pre>Package '$pkg' not exists!</pre>"
		fi
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
<div id="content2">

<form method="get" action="" class="r">
	<input type="search" name="pkg" placeholder="Package" list="packages" autocorrect="off" autocapitalize="off"/>
</form>

<h2>Summary</h2>

<table>
<tr><td>Running command</td><td>: $(running_command)</td></tr>
<tr><td>Wok revision</td><td>: <a href="$WOK_URL">$(cat $wokrev)</a></td></tr>
<tr><td>Commits to cook</td><td>: $(wc -l < $commits)</td></tr>
<tr><td>Current cooklist</td><td>: $(wc -l < $cooklist)</td></tr>
<tr><td>Broken packages</td><td>: $(wc -l < $broken)</td></tr>
<tr><td>Blocked packages</td><td>: $(wc -l < $blocked)</td></tr>
<tr><td>Architecture</td><td>: $ARCH, <a href="$toolchain">toolchain</a></td></tr>
<tr><td>Server date</td><td>: $(date -u '+%F %R %Z')</td></tr>

</table>
EOT

		[ -e $CACHE/cooker-request ] &&
		[ $CACHE/activity -nt $CACHE/cooker-request ] &&
		echo '<a class="button r" href="?poke">Poke cooker</a>'

		cat <<EOT
<p class="info">Packages: $inwok in the wok · $cooked cooked · $unbuilt unbuilt</p>

<div class="pctbar">
	<div class="pct" style="width: ${pct}%;">${pct}%</div>
</div>

<p>
	Service logs:
	<a href="?file=cookorder.log">cookorder</a> ·
	<a href="?file=commits.log">commits</a> ·
	<a href="?file=pkgdb.log">pkgdb</a><!-- ·
	<a href="?file=installed.diff">installed.diff</a> -->
</p>

$(more_button activity "More activity" $CACHE/activity 12)
<h2 id="activity">Activity</h2>

<ul class="activity">
EOT

		tac $CACHE/activity | head -n 12 | syntax_highlighter activity | \
		sed 's|cooker.cgi||; s|^|<li>|; s|$|</li>|'

		echo '</ul>'

		[ -s $cooknotes ] && cat <<EOT
$(more_button cooknotes "More notes" $cooknotes 12)
<h2 id="cooknotes">Cooknotes</h2>
<pre>
$(tac $cooknotes | head -n 12 | syntax_highlighter activity)
</pre>
EOT

		[ -s $commits ] && cat <<EOT
<h2 id="commits">Commits</h2>
<ul class="activity">
$(sed 's|^|<li>|; s|$|</li>|' $commits)
</ul>
EOT

		[ -s $cooklist ] && cat <<EOT
$(more_button cooklist "Full cooklist" $cooklist 20)
<h2 id="cooklist">Cooklist</h2>
<ul class="activity">
$(head -n 20 $cooklist | sed 's|^|<li>|; s|$|</li>|')
</ul>
EOT

		[ -s $broken ] && cat <<EOT
$(more_button broken "All broken packages" $broken 20)
<h2 id="broken">Broken</h2>
<ul class="activity">
$(head -n 20 $broken | sed "s#^[^']*#<a href='?pkg=\0'>\0</a>#g" | sed 's|^|<li>|; s|$|</li>|')
</ul>
EOT

		[ -s $blocked ] && cat <<EOT
<h2 id="blocked">Blocked</h2>
<ul class="activity">
$(sed "s#^[^']*#<a href='?pkg=\0'>\0</a>#g" $blocked | sed 's|^|<li>|; s|$|</li>|')
</ul>
EOT

		cat <<EOT
<h2 id="lastcook">Latest cook</h2>
<ul class="activity">
$(list_packages | sed "s|^.* :|<span class='log-date'>\0</span> <span style='white-space:nowrap'>|g; s|^|<li>|; s|$|</span></li>|")
</ul>

EOT
		datalist
	;;
esac


# Close xHTML page

cat <<EOT
</div>

<div id="footer">
	<a href="http://www.slitaz.org/">SliTaz Website</a>
	<a href="cooker.cgi">Cooker</a>
	<a href="doc/cookutils/cookutils.html">Documentation</a>
</div>

</body>
</html>
EOT

exit 0
