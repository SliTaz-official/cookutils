#!/bin/sh
#
# SliTaz Cooker CGI/web interface.
#

[ -f "/etc/slitaz/cook.conf" ] && . /etc/slitaz/cook.conf
[ -f "cook.conf" ] && . ./cook.conf

# The same wok as cook.
wok="$WOK"

# Cooker DB files.
activity="$CACHE/activity"
commits="$CACHE/commits"
cooklist="$CACHE/cooklist"
cookorder="$CACHE/cookorder"
command="$CACHE/command"
blocked="$CACHE/blocked"
broken="$CACHE/broken"
cooknotes="$CACHE/cooknotes"
wokrev="$CACHE/wokrev"

# We're not logged and want time zone to display correct server date.
export TZ=$(cat /etc/TZ)

if [ "${QUERY_STRING%%=*}" == 'download' ]; then
	file=$(busybox httpd -d "$PKGS/${QUERY_STRING#*=}")
	cat <<EOT
Content-Type: application/octet-stream
Content-Length: $(stat -c %s "$file")
Content-Disposition: attachment; filename="$(basename "$file")"

EOT
	cat "$file"
	exit
fi

echo -n "Content-Type: "
if [ "$QUERY_STRING" == 'rss' ]; then
	echo 'application/rss+xml'
else
	echo 'text/html; charset=utf-8'
fi
echo ''

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
	<atom:link href="http://cook.slitaz.org/cooker.cgi?rss" rel="self" type="application/rss+xml" />
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


# Put some colors in log and DB files.

syntax_highlighter() {
	case $1 in
		log)
			sed	-e 's/&/\&amp;/g;s/</\&lt;/g;s/>/\&gt;/g' \
				-e 's#OK$#<span class="span-ok">OK</span>#g' \
				-e 's#Done$#<span class="span-ok">Done</span>#g' \
				-e 's#yes$#<span class="span-ok">yes</span>#g' \
				-e 's#no$#<span class="span-no">no</span>#g' \
				-e 's#error$#<span class="span-red">error</span>#g' \
				-e 's#ERROR:#<span class="span-red">ERROR:</span>#g' \
				-e 's#WARNING:#<span class="span-red">WARNING:</span>#g' \
				-e s"#^Executing:\([^']*\).#<span class='sh-val'>\0</span>#"g \
				-e s"#^====\([^']*\).#<span class='span-line'>\0</span>#"g \
				-e s"#^[a-zA-Z0-9]\([^']*\) :: #<span class='span-sky'>\0</span>#"g \
				-e s"#ftp://[^ '\"]*#<a href='\0'>\0</a>#"g	\
				-e s"#http://[^ '\"]*#<a href='\0'>\0</a>#"g ;;

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
	ls -1t *.tazpkg | head -20 | \
	while read file; do
		echo -n $(stat -c '%y' $PKGS/$file | cut -d . -f 1 | sed s/:[0-9]*$//)
		echo " : $file"
	done
}


# Optional full list button

more_button() {
	[ $(wc -l < ${3:-$CACHE/$1}) -gt ${4:-12} ] &&
	echo "<a class=\"button\" href=\"cooker.cgi?file=$1\">$2</a>"
}


# Show the running command and its progression

running_command()
{
	local state="Not running"
	if [ -s "$command" ]; then
		state="$(cat $command)"
		if grep -q "^$state" $cooktime ; then
			set -- $(cat $cooktime)
			state="$state $((($(date +%s)-$3)*100/$2))%"
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
	<meta charset="utf-8"/>
	<title>SliTaz Cooker</title>
	<link rel="shortcut icon" href="favicon.ico"/>
	<link rel="stylesheet" type="text/css" href="style.css"/>
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

		# Package info.
		echo '<div id="info">'
		if [ -f "$wok/$pkg/receipt" ]; then
			echo "<a href='cooker.cgi?receipt=$pkg'>receipt</a>"
			unset WEB_SITE
			. $wok/$pkg/receipt

			[ -n "$WEB_SITE" ] && # busybox wget -s $WEB_SITE &&
			echo "<a href='$WEB_SITE'>home</a>"

			if [ -f "$wok/$pkg/taz/$PACKAGE-$VERSION/receipt" ]; then
				echo "<a href='cooker.cgi?files=$pkg'>files</a>"
				unset EXTRAVERSION
				. $wok/$pkg/taz/$PACKAGE-$VERSION/receipt
				if [ -f $wok/$pkg/taz/$PACKAGE-$VERSION/description.txt ]; then
					echo "<a href='cooker.cgi?description=$pkg'>description</a>"
				fi
				if [ -f $PKGS/$PACKAGE-$VERSION$EXTRAVERSION.tazpkg ]; then
					echo "<a href='cooker.cgi?download=$PACKAGE-$VERSION$EXTRAVERSION.tazpkg'>download</a>"
				fi
				if [ -f $PKGS/$PACKAGE-$VERSION$EXTRAVERSION-$ARCH.tazpkg ]; then
					echo "<a href='cooker.cgi?download=$PACKAGE-$VERSION$EXTRAVERSION-$ARCH.tazpkg'>download</a>"
				fi
				echo "<a href='ftp://${HTTP_HOST%:*}/$pkg/'>browse</a>"
			fi
		else
			if [ $(ls $wok/*$pkg*/receipt 2> /dev/null | wc -l) -eq 0 ]; then
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
<td><a href="cooker.cgi?pkg=$pkg">$pkg</a></td>
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
			echo '<h3>Cook log</h3>'
			echo '<pre>'
			cat $log | syntax_highlighter log
			echo '</pre>'
		else
			[ "$pkg" ] && echo "<pre>No log: $pkg</pre>"
		fi ;;

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
					sed s"#^[^']*#<a href='cooker.cgi?pkg=\0'>\0</a>#"g
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
			( cd $wok/$pkg ; find stuff -type f 2> /dev/null ) | \
			while read file ; do
				echo "<a href=\"?stuff=$pkg/$file\">$file</a>"
			done
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

	*)
		# We may have a toolchain.cgi script for cross cooker's
		if [ -f "toolchain.cgi" ]; then
			toolchain='toolchain.cgi'
		else
			toolchain='cooker.cgi?pkg=slitaz-toolchain'
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

<p class="info">
	Packages: $inwok in the wok | $cooked cooked | $unbuilt unbuilt |
	Server date: $(date -u '+%F %R %Z')
</p>
<div class="pctbar">
	<div class="pct" style="width: ${pct}%;">${pct}%</div>
</div>

<p>
	Latest:
	<a href="cooker.cgi?file=cookorder.log">cookorder.log</a>
	<a href="cooker.cgi?file=commits.log">commits.log</a>
	<a href="cooker.cgi?file=pkgdb.log">pkgdb.log</a>
	<a href="cooker.cgi?file=installed.diff">installed.diff</a>
	- Architecture $ARCH:
	<a href="$toolchain">toolchain</a>
</p>


<h2 id="activity">Activity</h2>
<pre>
$(tac $CACHE/activity | head -n 12 | syntax_highlighter activity)
</pre>
$(more_button activity "More activity" $CACHE/activity 12)


<h2 id="cooknotes">Cooknotes</h2>
<pre>
$(tac $cooknotes | head -n 12 | syntax_highlighter activity)
</pre>
$(more_button cooknotes "More notes" $cooknotes 12)


<h2 id="commits">Commits</h2>
<pre>
$(cat $commits)
</pre>


<h2 id="cooklist">Cooklist</h2>
<pre>
$(cat $cooklist | head -n 20)
</pre>
$(more_button cooklist "Full cooklist" $cooklist 20)


<h2 id="broken">Broken</h2>
<pre>
$(cat $broken | head -n 20 | sed s"#^[^']*#<a href='cooker.cgi?pkg=\0'>\0</a>#"g)
</pre>
$(more_button broken "All broken packages" $broken 20)


<h2 id="blocked">Blocked</h2>
<pre>
$(cat $blocked | sed s"#^[^']*#<a href='cooker.cgi?pkg=\0'>\0</a>#"g)
</pre>


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
	<a href="http://hg.slitaz.org/cookutils/raw-file/tip/doc/cookutils.en.html">
		Documentation</a>
</div>

</body>
</html>
EOT

exit 0
