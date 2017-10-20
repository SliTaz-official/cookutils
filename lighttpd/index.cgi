#!/bin/sh
#
# SliTaz Cooker CGI + Lighttpd web interface.
#

# Make request URI relative to the script name
base="$(dirname "$SCRIPT_NAME")"; [ "$base" == '/' ] && base=''
REQUEST_URI=$(echo "$REQUEST_URI" | sed "s|^$base/*|/|; s|\?.*||")

# Split the URI request to /pkg/cmd/arg
export pkg=$(echo "$REQUEST_URI" | cut -d/ -f2)
export cmd=$(echo "$REQUEST_URI" | cut -d/ -f3)
export arg=$(echo "$REQUEST_URI" | sed 's|^/[^/]*/[^/]*/||')


. /usr/lib/slitaz/httphelper.sh

[ -f "/etc/slitaz/cook.conf" ] && . /etc/slitaz/cook.conf
[ -f "./cook.conf" ] && . ./cook.conf
wok="$WOK"
title=${title:-SliTaz Cooker}
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
webstat="$CACHE/webstat"
splitdb="$CACHE/split.db"

# Path to markdown to html convertor
cmark_opts='--smart -e table -e strikethrough -e autolink -e tagfilter'
if [ -n "$(which cmark 2>/dev/null)" ]; then
	md2html="$(which cmark) $cmark_opts"
elif [ -x "./cmark" ]; then
	md2html="./cmark $cmark_opts"
elif [ -n "$(which sundown 2>/dev/null)" ]; then
	md2html=$(which sundown)
elif [ -x "./sundown" ]; then
	md2html="./sundown"
fi




# Search form redirection
if [ -n "$(GET search)" ]; then
	echo -e "HTTP/1.1 301 Moved Permanently\nLocation: $base/$(GET q)\n\n"
	exit 0
fi


# Show the running command and it's progression

running_command() {
	state="$(cat $command)"
	local pct=''
	if [ -n "$state" ];then
		echo -n "$state</td></tr><tr><td>Completion</td>"
		set -- $(grep "^$state" $cooktime)
		[ -n "$1" -a $2 -ne 0 ] && pct=$((($(date +%s)-$3)*100/$2))
		[ -n "$pct" ] && max="max='100'"
		echo -n "<td><progress id='gauge' $max value='$pct' title='Click to stop updating' onclick='stopUpdating()'>"
		echo -n "</progress> <span id='pct'>${pct:-?}%</span>"
		[ "$2" -gt 60 ] &&
			echo -n "</td></tr><tr><td>Estimated end time</td><td>$(date +%H:%M -ud @$(($2+$3)))"
	else
		echo 'not running'
	fi
}


# HTML page header

page_header() {
	local theme t='' css
	theme=$(COOKIE theme)
	[ "$theme" == 'default' ] && theme=''
	[ -n "$theme" ] && theme="-$theme"
	css="cooker$theme.css"

	echo -e 'Content-Type: text/html; charset=UTF-8\n'

	cat <<EOT
<!DOCTYPE html>
<html lang="en">
<head>
	<title>$([ -n "$pkg" ] && echo "$pkg - ")$title</title>
	<link rel="stylesheet" href="/$css">
	<link rel="icon" type="image/png" href="/slitaz-cooker.png">
	<link rel="search" href="$base/os.xml" title="$title" type="application/opensearchdescription+xml">
	<!-- mobile -->
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<meta name="theme-color" content="#222">
	<!-- rss -->
	<link rel="alternate" type="application/rss+xml" title="$title Feed" href="?rss">
</head>
<body>
<div id="container">
<header>
	<h1><a href="$base/">$title</a></h1>
	<div class="network">
		<a href="http://www.slitaz.org/">Home</a>
		<a href="http://bugs.slitaz.org/">Bugs</a>
		<a href="http://hg.slitaz.org/wok-next/">Hg</a>
		<a href="http://roadmap.slitaz.org/">Roadmap</a>
		<a href="http://pizza.slitaz.me/">Pizza</a>
		<a href="http://tank.slitaz.org/">Tank</a>
		|
		<a href="/cross/">Cross</a>
		<a href="/i486.cgi">i486</a>
		<a href="$base/cookiso.cgi">ISO</a>
		<select onChange="window.location.href=this.value" style="display: none">
			<option value=".">Go to…</option>
			<option value="http://www.slitaz.org/">Home</option>
			<option value="http://bugs.slitaz.org/">Bug tracker</option>
			<option value="http://hg.slitaz.org/wok/">Hg wok</option>
			<option value="http://roadmap.slitaz.org/">Roadmap</option>
			<option value="http://pizza.slitaz.me/">Pizza</option>
			<option value="http://tank.slitaz.org/">Tank</option>
			<option disabled>---------</option>
			<option value="cross/">Cross</option>
			<option value="i486.cgi">i486</option>
			<option value="cookiso.cgi">ISO</option>
		</select>
	</div>
</header>

<main>
EOT

	[ -n "$(GET debug)" ] && echo "<pre><code class='language-ini'>$(env | sort)</code></pre>"
}


# HTML page footer

page_footer() {
	date_now=$(date +%s)
	sec_now=$(date +%S); sec_now=${sec_now#0} # remove one leading zero
	wait_sec=$(( 60 - $sec_now ))
	cat <<EOT
</main>

<footer>
	<a href="http://www.slitaz.org/">SliTaz Website</a>
	<a href="$base/">Cooker</a>
	<a href="$base/doc/cookutils/cookutils.html">Documentation</a>
	<a href="$base/?theme">Theme</a>
</footer>
</div>
<script src="/cooker.js"></script>
<script>refreshDate(${wait_sec}000, ${date_now}000)</script>
</body>
</html>
EOT
}


show_note() {
	echo "<div class='bigicon-$1'>$2</div>"
}


not_found() {
	local file="${1#$PKGS/}"; file="${file#$LOGS/}"; file="${file#$WOK/}"
	echo "HTTP/1.1 404 Not Found"
	page_header
	echo "<h2>Not Found</h2>"
	case $2 in
		pkg)
			show_note e "The requested package “$(basename "$(dirname "$file")")” was not found." ;;
		*)
			show_note e "The requested file “$file” was not found." ;;
	esac
	page_footer
}


manage_modified() {
	local file="$1" option="$2" nul day mon year time hh mm ss date_s
	if [ ! -f "$file" ]; then
		if [ "$option" == 'silently-absent' ]; then
			echo "HTTP/1.1 404 Not Found"
			return
		else
			not_found "$file" "$2"
			exit
		fi
	fi
	[ "$option" == 'no-last-modified' ] && return
	if [ -n "$HTTP_IF_MODIFIED_SINCE" ]; then
		echo "$HTTP_IF_MODIFIED_SINCE" | \
		while read nul day mon year time nul; do
			case $mon in
				Jan) mon='01';; Feb) mon='02';; Mar) mon='03';; Apr) mon='04';;
				May) mon='05';; Jun) mon='06';; Jul) mon='07';; Aug) mon='08';;
				Sep) mon='09';; Oct) mon='10';; Nov) mon='11';; Dec) mon='12';;
			esac
			hh=$(echo $time | cut -d: -f1)
			mm=$(echo $time | cut -d: -f2)
			ss=$(echo $time | cut -d: -f3)
			date_s=$(date -ud "$year$mon$day$hh$mm.$ss" +%s)
#			if [ "$date_s" -ge "$(date -ur "$file" +%s)" ]; then
#				echo -e 'HTTP/1.1 304 Not Modified\n'
#				exit
#			fi
# TODO: improve caching control
		done
	fi
	echo "Last-Modified: $(date -Rur "$file" | sed 's|UTC|GMT|')"
	echo "Cache-Control: public, max-age=3600"
}


# Query '?pct=<package>': update percentage

if [ -n "$(GET pct)" ]; then
	pkg="$(GET pct)"
	state="$(cat $command)"
	if [ "$state" == "cook:$pkg" ]; then
		set -- $(grep "^$state" $cooktime)
		[ -n "$1" ] && pct=$(( ($(date +%s) - $3) * 100 / $2 ))
		echo "${pct:-?}"
	else
		echo 'reload'
	fi
	exit 0
fi


# Query '?poke': poke cooker

if [ -n "$(GET poke)" ]; then
	touch $CACHE/cooker-request
	echo -e "Location: ${HTTP_REFERER:-${REQUEST_URI%\?*}}\n"
	exit
fi


# Query '?recook=<package>': query to recook package

if [ -n "$(GET recook)" ]; then
	pkg="$(GET recook)"
	case "$HTTP_USER_AGENT" in
		*SliTaz*)
			grep -qs "^$pkg$" $CACHE/recook-packages ||
			echo "$pkg" >>    $CACHE/recook-packages
	esac
	echo -e "Location: ${HTTP_REFERER:-${REQUEST_URI%\?*}}\n"
	exit
fi


# Query '/i/<log>/<pkg>': show indicator icon
# Can't use ?query - not able to change '+' to '%2B' in the sed rules (see log handler)

if [ "$pkg" == 'i' ]; then
	echo -en "Content-Type: image/svg+xml\n\n<svg xmlns='http://www.w3.org/2000/svg' height='12' width='8'><path d='"
	if [ $LOGS/$cmd -nt $PKGS/$arg.tazpkg ]; then
		echo "m1 2-1 1v8l1 1h6l1-1v-8l-1-1z' fill='#090'/></svg>"
	else
		echo "m0 3v8l1 1h6l1-1v-8l-1-1h-6zm3 0h2v5h-2zm0 6h2v2h-2z' fill='#d00'/></svg>"
	fi
	exit
fi


# Query '/s/<pkg>': show status indicator icon
# Can't use ?query - not able to change '+' to '%2B' in the sed rules (see log handler)

if [ "$pkg" == 's' ]; then
	# argument <pkg> is in $cmd variable

	# find main package
	main=$(awk -F$'\t' -vpkg=" $cmd " '{
		if (index(" " $2 " ", pkg)) {print $1; exit}
	}' $splitdb)
	# get version
	ver="$(. $wok/$main/receipt; echo "$VERSION")"

	echo -en "Content-Type: image/svg+xml\n\n<svg xmlns='http://www.w3.org/2000/svg' height='12' width='8'><path d='"
	if [ -e $PKGS/$cmd-$ver.tazpkg ]; then
		echo "m1 2-1 1v8l1 1h6l1-1v-8l-1-1z' fill='#090'/></svg>"
	else
		echo "m0 3v8l1 1h6l1-1v-8l-1-1h-6zm3 0h2v5h-2zm0 6h2v2h-2z' fill='#d00'/></svg>"
	fi
	exit
fi


# Query '?theme[=<theme>]': change UI theme

if [ -n "$(GET theme)" ]; then
	theme="$(GET theme)"
	ref="$(echo "$HTTP_REFERER" | sed 's|:|%3A|g; s|/|%2F|g; s|\?|%3F|g; s|\+|%2B|g;')"
	case $theme in
		theme)
			current=$(COOKIE theme)
			page_header
			cat <<EOT
<section>
	<h2>Change theme</h2>
	<p>Current theme: “${current:-default}”. Select other:</p>
	<ul>
		$(
			for i in default emerald sky goldenrod midnight like2016 terminal; do
				[ "$i" == "${current:-default}" ] || echo "<li><a href=\"$base/?theme=$i&amp;ref=$ref\">$i</a></li>"
			done
		)
	</ul>
</section>
EOT
			page_footer
			exit 0
			;;
		default|emerald|sky|goldenrod|midnight|like2016|terminal)
			ref="$(GET ref)"
			[ -n "$ref" ] || ref="$base/"
			# Expires in a year
			expires=$(date -uRd @$(($(date +%s)+31536000)) | sed 's|UTC|GMT|')
			echo -e "HTTP/1.1 302 Found\nLocation: $ref\nCache-Control: no-cache\nSet-Cookie: theme=$theme; expires=$expires\n\n"
			exit 0
			;;
	esac
fi


#case "$QUERY_STRING" in
#	stuff*)
#		file="$wok/$(GET stuff)"
#		manage_modified "$file"
#		;;
#
#	pkg=*|receipt=*|description=*|files=*|log=*|man=*|doc=*|info=*)
#		type=${QUERY_STRING%%=*}
#		pkg=$(GET $type)
#		case "$type" in
#			description)
#				manage_modified "$wok/$pkg/receipt" 'no-last-modified'
#				manage_modified "$wok/$pkg/description.txt" 'silently-absent'
#				;;
#			log)
#				manage_modified "$wok/${pkg%%.log*}/receipt" 'no-last-modified'
#				manage_modified "$LOGS/$pkg"
#				;;
#			*)
#				manage_modified "$wok/$pkg/receipt" pkg
#				;;
#		esac
#		;;
#esac


# RSS feed generator
# URI: ?rss[&limit={1..100}]

if [ -n "$(GET rss)" ]; then
	limit=$(GET limit); limit="${limit:-12}"; [ "$limit" -gt 100 ] && limit='100'
	pubdate=$(date -Rur$(ls -t $FEEDS/*.xml | head -n1) | sed 's|UTC|GMT|')
	cooker_url="http://$HTTP_HOST$base/"
	cat <<EOT
Content-Type: application/rss+xml

<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
	<title>$title</title>
	<description>The SliTaz packages cooker feed</description>
	<link>$cooker_url</link>
	<lastBuildDate>$pubdate</lastBuildDate>
	<pubDate>$pubdate</pubDate>
	<atom:link href="$cooker_url?rss" rel="self" type="application/rss+xml" />
EOT
	for rss in $(ls -t $FEEDS/*.xml | head -n$limit); do
		sed "s|http[^=]*=|$cooker_url|; s|<guid|& isPermaLink=\"false\"|g; s|</pubDate| GMT&|g" $rss
	done
	cat <<EOT
</channel>
</rss>
EOT
	exit 0
fi


### OpenSearch ###

# Query '/os.xml': get OpenSearch Description

if [ "$pkg" == 'os.xml' ]; then
	cat <<EOT
Content-Type: application/xml; charset=UTF-8

<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
	<ShortName>$title</ShortName>
	<Description>SliTaz packages search</Description>
	<Image width="16" height="16" type="image/png">http://$HTTP_HOST/images/logo.png</Image>
	<Url type="text/html" method="GET" template="http://$HTTP_HOST$base/{searchTerms}"/>
	<Url type="application/x-suggestions+json" method="GET" template="http://$HTTP_HOST$base/">
		<Param name="oss" value="{searchTerms}"/>
	</Url>
	<SearchForm>http://$HTTP_HOST$base/</SearchForm>
	<InputEncoding>UTF-8</InputEncoding>
</OpenSearchDescription>
EOT
	exit 0
fi

# Query '?oss[=<term>]': OpenSearch suggestions

if [ -n "$(GET oss)" ]; then
	term="$(GET oss | tr -cd '[:alnum:]+-')"
	echo -e 'Content-Type: application/x-suggestions+json; charset=UTF-8\n'
	cd $wok
	ls | fgrep "$term" | head -n10 | awk -vterm="$term" '
		BEGIN{printf("[\"%s\",[", term)}
		     {printf("%s\"%s\"", NR != 1 ? "," : "", $0)}
		END  {printf("]]")}
		'
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


# Tiny texinfo converter

info2html() {
	sed \
		-e 's|&|\&amp;|g; s|<|\&lt;|g; s|>|\&gt;|g' \
		-e 's|^\* \(.*\)::|* <a href="#\1">\1</a>  |' \
		-e 's|\*note \(.*\)::|<a href="#\1">\1</a>|' \
		-e '/^File: / s|(dir)|Top|g' \
		-e '/^File: / s|Next: \([^,]*\)|<a class="button" href="#\1">Next: \1</a>|' \
		-e '/^File: / s|Prev: \([^,]*\)|<a class="button" href="#\1">Prev: \1</a>|' \
		-e '/^File: / s|Up: \([^,]*\)|<a class="button" href="#\1">Up: \1</a>|' \
		-e '/^File: / s|^.* Node: \([^,]*\), *\(.*\)$|<pre id="\1">\2|' \
		-e '/^<pre id=/ s|^\([^>]*>\)\(<a[^>]*>Next: [^,]*\), *\(<a[^>]*>Prev: [^,]*\), *\(<a[^>]*>Up: .*\)|\1 \3 \4 \2|' \
		-e '/^Tag Table:$/,/^End Tag Table$/d' \
		-e '/INFO-DIR/,/^END-INFO-DIR/d' \
		-e "s|https*://[^>),'\"\`’ ]*|<a href=\"&\">&</a>|g" \
		-e "s|ftp://[^>),\"\` ]*|<a href=\"&\">&</a>|g" \
		-e 's|^\* Menu:|<b>Menu:</b>|' \
		-e "s|^|</pre>|"
}


# Put some colors into log and DB files.

syntax_highlighter() {
	case $1 in
		log)
			# If variables not defined - define them with some rare values
			: ${_src=#_#_#}
			: ${_install=#_#_#}
			: ${_fs=#_#_#}
			: ${_stuff=#_#_#}
			# Use one-letter html tags to save some bytes :)
			# <b>is error (red)</b> <u>is warning (orange)</u> <i>is informal (green)</i>
			sed	-e 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g' \
				-e 's#OK$#<i>OK</i>#' \
				-e 's#\([Dd]one\)$#<i>\1</i>#' \
				-e 's#Success$#<i>Success</i>#' \
				-e 's#\([^a-z]\)ok$#\1<i>ok</i>#' \
				-e 's#\([^a-z]\)yes$#\1<i>yes</i>#' \
				-e 's#\([^a-z]\)ON$#\1<i>ON</i>#' \
				-e 's#\([^a-z]\)no$#\1<u>no</u>#' \
				-e 's#\([^a-z]\)none$#\1<u>none</u>#' \
				-e 's#\([^a-z]\)false$#\1<u>false</u>#' \
				-e 's#\([^a-z]\)OFF$#\1<u>OFF</u>#' \
				-e 's#\(^checking .*\.\.\. \)\(.*\)$#\1<i>\2</i>#' \
				\
				-e 's#\( \[Y[nm/]\?\] n\)$# <u>\1</u>#' \
				-e 's#\( \[N[ym/]\?\] y\)$# <i>\1</i>#' \
				-e 's# y$# <i>y</i>#' \
				-e 's# n$# <u>n</u>#' \
				-e 's#(NEW) *$#<b>(NEW)</b>#' \
				\
				-e 's#.*(pkg/local).*#<i>\0</i>#' \
				-e 's#.*(web/cache).*#<u>\0</u>#' \
				\
				-e 's#\([^a-zA-Z]\)\([Ee]rror\)$#\1<b>\2</b>#' \
				-e 's#ERROR:#<b>ERROR:</b>#g' \
				\
				-e 's#^.*[Ff][Aa][Ii][Ll][Ee][Dd].*#<b>\0</b>#' \
				-e 's#^.*[Ff]atal.*#<b>\0</b>#' \
				-e 's#^.*[Nn]ot found.*#<b>\0</b>#' \
				-e 's#^.*[Nn]o such file.*#<b>\0</b>#' \
				-e 's#^.*No package .* found.*#<b>\0</b>#' \
				-e 's#^.*Unable to find.*#<b>\0</b>#' \
				-e 's#[^a-zA-Z-][Ii]nvalid.*#<b>\0</b>#' \
				-e 's#\([Nn][Oo][Tt] found\.*\)$#<b>\1</b>#' \
				-e 's#\(found\.*\)$#<i>\1</i>#' \
				\
				-e 's#^.*WARNING:.*#<u>\0</u>#' \
				-e 's#^.*warning:.*#<u>\0</u>#' \
				-e 's#^.* [Ee]rror:* .*#<b>\0</b>#' \
				-e 's#^.*terminated.*#<b>\0</b>#' \
				-e 's#\(missing\)#<b>\1</b>#g' \
				-e 's#^.*[Cc]annot find.*#<b>\0</b>#' \
				-e 's#^.*unrecognized options.*#<u>\0</u>#' \
				-e 's#^.*does not.*#<u>\0</u>#' \
				-e 's#^.*[Ii]gnoring.*#<u>\0</u>#' \
				-e 's#^.*note:.*#<u>\0</u>#' \
				\
				-e 's#^.* will not .*#<u>\0</u>#' \
				-e 's!^Hunk .* succeeded at .*!<u>\0</u>!' \
				-e 's#^.* Warning: .*#<u>\0</u>#' \
				\
				-e "s#^Executing:\([^']*\).#<em>\0</em>#" \
				-e "s#^Making.*#<em>\0</em>#" \
				-e "s#^Scanning dependencies of target .*#<em>\0</em>#" \
				-e "s#^====\([^']*\).#<span class='span-line'>\0</span>#g" \
				-e "s#^[a-zA-Z0-9]\([^']*\) :: #<span class='span-sky'>\0</span>#g" \
				-e "s#[fh]tt*ps*://[^ '\"]*#<a href='\0'>\0</a>#g" \
				\
				-e 's|^<u>\(.*libtool: warning: relinking.*\)</u>|\1|' \
				-e 's|^<u>\(.*libtool: warning: .* has not been installed in .*\)</u>|\1|' \
				-e 's|^<u>\(.*checking for a sed.*\)</u>|\1|' \
				\
				-e "s|$_src|<var>\${src}</var>|g;
					s|$_install|<var>\${install}</var>|g;
					s|$_fs|<var>\${fs}</var>|g;
					s|$_stuff|<var>\${stuff}</var>|g" \
				-e "s|\[9\([1-6]\)m|<span class='c\10'>|;
					s|\[39m|</span>|;
					s|\[1m|<strong>|g; s|\[0m|</strong>|g;"
			;;

		files)
			# Highlight the Busybox's `ls` output
			awk '{
				part1 = substr($0,  0, 16);
				part2 = substr($0, 17,  9);
				part3 = substr($0, 26,  9);
				part4 = substr($0, 35);
				if (part2 != "root     ") part2 = "<span class=\"c11\">" part2 "</span>";
				if (part3 != "root     ") part3 = "<span class=\"c11\">" part3 "</span>";
				print part1 part2 part3 part4;
			}' | \
			sed "s|\[0m/|/\[0m|g;
				 s|\[\([01]\);3\([1-7]\)m|<a class='c\2\1'>|g;
				 s|\[\([01]\);0m|<a class='c0\1'>|g;
				 s|\[0m|</a>|g;
				 s|^\(lrwxrwxrwx\)|<span class='c61'>\1</span>|;
				 s|^\(-rwxr-xr-x\)|<span class='c21'>\1</span>|;
				 s|^\(-rw-r--r--\)|<span class='c31'>\1</span>|;
				 s|^\(drwxr-xr-x\)|<span class='c41'>\1</span>|;
				 s|^\([lrwxs-]*\)|<span class='c11'>\1</span>|;
				"
			;;
	esac
}


show_code() {
	echo -n "<pre><code class=\"language-$1\">"
	sed 's|&|\&amp;|g; s|<|\&lt;|g; s|>|\&gt;|g'
	echo '</code></pre>'
}


datalist() {
	cut -d$'\t' -f2 $splitdb | tr ' ' '\n' | sort -u | awk '
		BEGIN{printf("<datalist id=\"packages\">")}
		     {printf("<option>%s",$1)}
		END  {printf("</datalist>")}
		'
}


mklog() {
	awk '
	BEGIN { printf("<pre class=\"log dog\">\n") }
		  { print }
	  END { print "</pre>" }'
}


summary() {
	log="$1"
	pkg="$(basename ${log%%.log*})"

	if [ -f "$log" ]; then
		if grep -q "cook:$pkg$" $command; then
			show_note i "The Cooker is currently building $pkg"
		elif fgrep -q "Summary for:" $log; then
			sed '/^Summary for:/,$!d' $log | awk '
			BEGIN { print "<section>" }
			function row(line) {
				split(line, s, " : ");
				printf("\t<tr><td>%s</td><td>%s</td></tr>\n", s[1], s[2]);
			}
			function row2(line, rowNum) {
				split(line, s, " : ");
				if (rowNum == 1) {
					print "<thead>";
					printf("\t<tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr>\n", s[1], s[2], s[3], s[4], s[5]);
					print "</thead><tbody>";
				}
				else
					printf("\t<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>\n", s[1], s[2], s[3], s[4], s[5]);
			}
			{
				if (NR==1) { printf("<h3>%s</h3>\n<table>\n", $0); next }
				if ($0 ~ "===") { seen++; if (seen == 1) next; else exit; }
				if ($0 ~ "---") {
					seen2++;
					if (seen2 == 1) print "</table>\n\n<table class=\"pkgslist\">"
					next
				}
				if (seen2) row2($0, seen2); else row($0);
			}
			END { print "</tbody></table></section>" }
			'
		elif fgrep -q "Debug information" $log; then
			echo -e '<section>\n<h3>Debug information</h3>'
			sed -e '/^Debug information/,$!d; /^===/d; /^$/d' $log | sed -n '1!p' | \
			if [ -n "$2" ]; then
				syntax_highlighter log | sed 's|\([^0-9 ]\)\([0-9][0-9]*\):|\1<a href="#l\2">\2</a>:|'
			else
				sed 's|^[0-9][0-9]*:||' | syntax_highlighter log
			fi | mklog
			echo '</section>'
		fi
	else
		[ -n "$pkg" -a -d "$wok/$pkg" ] && show_note e "No log for $pkg"
	fi
}


active() {
	[ "$cmd" == "$1" -o "$cmd" == "${2:-$1}" ] && echo -n ' active'
}


pkg_info() {
	local log active bpkg
	log="$LOGS/$pkg.log"

	echo "<h2><a href=\"$base/$pkg\">$pkg</a></h2>"
	echo '<div id="info">'
	echo "<a class='button icon receipt$(active receipt stuff)' href='$base/$pkg/receipt'>receipt &amp; stuff</a>"

	unset WEB_SITE WANTED
	. $wok/$pkg/receipt

	[ -n "$WEB_SITE" ] &&
		echo "<a class='button icon website' href='$WEB_SITE' target='_blank' rel='noopener noreferrer'>web site</a>"

	[ -f "$wok/$pkg/taz/$PACKAGE-$VERSION/receipt" ] &&
		echo "<a class='button icon files$(active files)' href='$base/$pkg/files'>files</a>"

	[ -n "$(ls $wok/$pkg/description*.txt)" ] &&
		echo "<a class='button icon desc$(active description)' href='$base/$pkg/description'>description</a>"

	[ -n "$TARBALL" -a -s "$SRC/$TARBALL" -o -d "$wok/$pkg/taz" ] &&
		echo "<a class='button icon download' href='$base/$pkg/download'>download</a>"

	echo "<a class='button icon browse' href='$base/$pkg/browse/'>browse</a>"

	[ -x ./man2html -a -d "$wok/$pkg/install/usr/share/man" ] &&
		echo "<a class='button icon doc$(active man)' href='$base/$pkg/man/'>man</a>"

	[ -d "$wok/$pkg/install/usr/share/doc" -o -d "$wok/$pkg/install/usr/share/gtk-doc" ] &&
		echo "<a class='button icon doc$(active doc)' href='$base/$pkg/doc/'>doc</a>"

	[ -d "$wok/$pkg/install/usr/share/info" ] &&
		echo "<a class='button icon doc$(active info)' href='$base/$pkg/info/#Top'>info</a>"

	[ -n "$LFS" ] &&
		echo "<a class='button icon doc' href='$LFS' target='_blank' rel='noopener noreferrer'>(B)LFS</a>"

	[ -s "$log" ] &&
		echo "<a class='button icon log$(active log)' href='$base/$pkg/log/'>logs</a>"

	echo '</div>'
}


mktable() {
	sed 's# : #|#' | awk -vc="$1" '
	BEGIN { printf("<table class=\"%s\">\n", c); FS="|" }
		  { printf("<tr><td>%s</td>", $1);
			if (NF == 2) printf("<td>%s</td>", $2);
			printf("</tr>\n", $2) }
	  END { print "</table>" }'
}


section() {
	local i=$(basename "$1")
	echo -e '\n\n<section>'
	[ $(wc -l < $1) -gt $2 ] && echo "<a class='button icon more r' href='?$i'>${3#*|}</a>"
	echo "<h2>${3%|*}</h2>"
	mktable "$i"
	echo '</section>'
}


show_desc() {
	echo "<section><h3>Description of “$1”</h3>"
	if [ -n "$md2html" ]; then
		$md2html $2
	else
		show_code markdown < $2
	fi
	echo "</section>"
}


# Return all the names of packages bundled in this receipt

all_names() {
	local split=" $SPLIT "
	if [ "${split/ $PACKAGE /}" != "$split" ]; then
		# $PACKAGE included somewhere in $SPLIT (probably in the end).
		# We should build packages in the order defined in the $SPLIT.
		echo $SPLIT
	else
		# We'll build the $PACKAGE, then all defined in the $SPLIT.
		echo $PACKAGE $SPLIT
	fi
}


toolchain_version() {
	echo "<tr><td><a href='$base/$1'>$1</a></td><td>"
	if [ -e "$WOK/$1/receipt" ]; then
		grep ^VERSION $WOK/$1/receipt | cut -d '"' -f2
		echo '</td><td>'
		grep ^SHORT_DESC $WOK/$1/receipt | cut -d '"' -f2
	else
		echo -n '---</td><td>---'
	fi
	echo "</td></tr>"
}


files_header() {
	echo '<section><h3>Available downloads:</h3>'
	echo '<table><thead><tr><th>File</th><th>Size</th><th>Description</th></tr></thead><tbody>'
}


# Update statistics used in web interface.
# There is no need to recalculate the statistics every time the page is displayed.
# Note, $webstat file must be owned by www, otherwise this function will not be able to do the job.

update_webstat() {
	echo '<div id="waitme">'
	show_note i 'Please wait while statistics are being collected.'
	echo "</div>"

	# for receipts:
	rtotal=$(ls $WOK/*/arch.$ARCH | wc -l)
	rcooked=$(ls -d $WOK/*/taz | wc -l)
	runbuilt=$(($rtotal - $rcooked))
	rblocked=$(wc -l < $blocked)
	rbroken=$(wc -l < $broken)

	# for packages:
	ptotal=$(cut -d$'\t' -f2 $CACHE/split.db | tr ' ' '\n' | sort -u | wc -l)
	pcooked=$(ls $PKGS/*.tazpkg | wc -l)
	punbuilt=$(($ptotal - $pcooked))
	pblocked=$(
		while read i; do
			sed "/^$i\t/!d" $CACHE/split.db
		done < $blocked | cut -d$'\t' -f2 | tr ' ' '\n' | wc -l)
	pbroken=$(
		while read i; do
			sed "/^$i\t/!d" $CACHE/split.db
		done < $broken | cut -d$'\t' -f2 | tr ' ' '\n' | wc -l)

	cat > $webstat <<EOT
rtotal="$rtotal"; rcooked="$rcooked"; runbuilt="$runbuilt"; rblocked="$rblocked"; rbroken="$rbroken"
ptotal="$ptotal"; pcooked="$pcooked"; punbuilt="$punbuilt"; pblocked="$pblocked"; pbroken="$pbroken"
EOT

	echo '<script>document.getElementById("waitme").remove();</script>'
}




#
# Load requested page
#

if [ -z "$pkg" ]; then

	page_header
	if [ -n "$QUERY_STRING" -a "$QUERY_STRING" != 'debug' ]; then

		for list in activity cooknotes cooklist; do
			[ -n "$(GET $list)" ] || continue
			[ "$list" == 'cooklist' ] && nb="- Packages: $(wc -l < $cooklist)"
			echo '<section id="content2">'
			echo "<h2>DB: $list $nb</h2>"
			tac $CACHE/$list | sed 's|cooker.cgi?pkg=||; s|%2B|+|g;
				s|\[ Done|<span class="r c20">Done|;
				s|\[ Failed|<span class="r c10">Failed|;
				s| \]|</span>|' | mktable $list
			echo '</section>'
		done

		if [ -n "$(GET broken)" ]; then
			echo '<section id="content2">'
			echo "<h2>DB: broken - Packages: $(wc -l < $broken)</h2>"
			sort $CACHE/broken | sed "s|^[^']*|<a href='$base/\0'>\0</a>|g" | mktable
			echo '</section>'
		fi

		case "$QUERY_STRING" in
			*.log)
				log=$LOGS/$QUERY_STRING
				name=$(basename $log)
				if [ -f "$log" ]; then
					echo "<h2>Log for: ${name%.log}</h2>"
					if fgrep -q "Summary" $log; then
						echo '<pre class="log">'
						grep -A 20 'Summary' $log | syntax_highlighter log
						echo '</pre>'
					fi
					echo '<pre class="log">'
					syntax_highlighter log < $log
					echo '</pre>'
				else
					show_note e "No log file: $log"
				fi
				;;
			toolchain)
				cat <<EOT
<div id="content2">
<section>
<h2>SliTaz GNU/Linux toolchain</h2>

<table>
<tr><td>Build date</td>		<td colspan="2">$(sed -n '/^Cook date/s|[^:]*: \(.*\)|\1|p' $LOGS/slitaz-toolchain.log)</td></tr>
<tr><td>Build duration</td>	<td colspan="2">$(sed -n '/^Cook time/s|[^:]*: \(.*\)|\1|p' $LOGS/slitaz-toolchain.log)</td></tr>
<tr><td>Architecture</td>	<td colspan="2">$ARCH</td></tr>
<tr><td>Build system</td>	<td colspan="2">$BUILD_SYSTEM</td></tr>
<tr><td>Host system</td>	<td colspan="2">$HOST_SYSTEM</td></tr>
<tr><th>Package</th><th>Version</th><th>Description</th></tr>
$(toolchain_version slitaz-toolchain)
$(toolchain_version binutils)
$(toolchain_version linux-api-headers)
$(toolchain_version gcc)
$(toolchain_version glibc)
</table>

<p>Toolchain documentation: <a target="_blank" rel="noopener noreferrer"
href="http://doc.slitaz.org/en:cookbook:toolchain">http://doc.slitaz.org/en:cookbook:toolchain</a>
</p>

</section>
</div>
EOT
				;;
		esac
		page_footer
		exit 0
	fi


	# We may have a toolchain.cgi script for cross cooker's
	if [ -f "toolchain.cgi" ]; then
		toolchain="toolchain.cgi"
	else
		toolchain="?toolchain"
	fi

	# Main page with summary. Count only packages included in ARCH,
	# use 'cooker arch-db' to manually create arch.$ARCH files.

	cat <<EOT
<div id="content2">

<section>
<form method="get" action="" class="search r">
	<input type="hidden" name="search" value="pkg"/>
	<button type="submit" title="Search">Search</button>
	<input type="search" name="q" placeholder="Package" list="packages" autocorrect="off" autocapitalize="off"/>
</form>

<h2>Summary</h2>
EOT

mktable <<EOT
Cooker state     : $(running_command)
Wok revision     : <a href='$WOK_URL' target='_blank' rel='noopener noreferrer'>$(cat $wokrev)</a>
Commits to cook  : $(wc -l < $commits)
Current cooklist : $(wc -l < $cooklist)
Architecture     : $ARCH, <a href="$toolchain">toolchain</a>
Server date      : <span id='date'>$(date -u '+%F %R %Z')</span>
EOT

	# If command is "cook:*", update gauge and percentage periodically.
	# If different package is cooking, reload the page (with new settings)
	cmd="$(cat $command)"
	case "$cmd" in
		cook:*)
			pkg=${cmd#*:}
			echo "<script>updatePkg = '${pkg//+/%2B}';</script>"
			;;
	esac

	# Do we need to update the statistics?
	[ "$webstat" -nt "$activity" ] || update_webstat
	. $webstat

	pct=0; [ "$rtotal" -gt 0 ] && pct=$(( ($rcooked * 100) / $rtotal ))

cat <<EOT
<div class="meter"><progress max="100" value="$pct">${pct}%</progress><span>${pct}%</span></div>

<table class="webstat"><thead>
<tr><th>        </th><th>Total  </th><th>Cooked  </th><th>Unbuilt  </th><th>Blocked  </th><th>Broken  </th></tr>
</thead><tbody>
<tr><td>Receipts</td><td>$rtotal</td><td>$rcooked</td><td>$runbuilt</td><td>$rblocked</td><td>$rbroken</td></tr>
<tr><td>Packages</td><td>$ptotal</td><td>$pcooked</td><td>$punbuilt</td><td>$pblocked</td><td>$pbroken</td></tr>
</tbody></table>
EOT

	if [ -e "$CACHE/cooker-request" -a ! -s $command ]; then
		if [ "$activity" -nt "$CACHE/cooker-request" ]; then
			echo '<a class="button icon bell r" href="?poke">Wake up</a>'
		else
			show_note i 'Cooker will be launched in the next 5 minutes.'
		fi
	fi

	cat <<EOT
<p>
	Service logs:
	<a href="?cookorder.log">cookorder</a> ·
	<a href="?commits.log">commits</a> ·
	<a href="?pkgdb.log">pkgdb</a>
</p>
</section>
EOT

	tac $activity | head -n12 | sed 's|cooker.cgi?pkg=||;
		s|\[ Done|<span class="r c20">Done|;
		s|\[ Failed|<span class="r c10">Failed|;
		s| \]|</span>|;
		s|%2B|\+|g' | \
		section $activity 12 "Activity|More activity"

	[ -s "$cooknotes" ] && tac $cooknotes | head -n12 | \
		section $cooknotes 12 "Cooknotes|More notes"

	[ -s "$commits" ] &&
		section $commits 20 "Commits|More commits" < $commits

	[ -s "$cooklist" ] && head -n 20 $cooklist | \
		section $cooklist 20 "Cooklist|Full cooklist"

	[ -s "$broken" ] && head -n20 $broken | sed "s|^[^']*|<a href='\0'>\0</a>|g" | \
		section $broken 20 "Broken|All broken packages"

	[ -s "$blocked" ] && sed "s|^[^']*|<a href='\0'>\0</a>|g" $blocked | \
		section $blocked 12 "Blocked|All blocked packages"

	cd $PKGS
	ls -let *.tazpkg | awk '
	(NR<=20){
		sub(/:[0-9][0-9]$/, "", $9);
		mon = index("  JanFebMarAprMayJunJulAugSepOctNovDec", $7) / 3;
		printf("%d-%02d-%02d %s : <a href=\"get/%s\">%s</a>\n", $10, mon, $8, $9, $11, $11);
	}' | \
		section $activity 1000 "Latest cook"

	echo '</div>'
	datalist
	page_footer
	exit 0
fi


case "$cmd" in
	'')
		page_header

		# Package info.
		if [ ! -f "$wok/$pkg/receipt" ]; then
			# Let's look at the cases when the package was not found

			# Maybe query is the exact name of split package? -> proceed to main package
			mainpkg=$(awk -F$'\t' -vpkg=" $pkg " '{
				if (index(" " $2 " ", pkg)) {print $1; exit}
			}' $splitdb)

			# No, so let's find any matches among packages names (both main and split)
			if [ -z "$mainpkg" ]; then
				pkgs=$(cut -d$'\t' -f2 $splitdb | tr ' ' '\n' | fgrep "$pkg")
				# Nothing matched
				if [ -z "$pkgs" ]; then
					echo "<h2>Not Found</h2>"
					show_note e "The requested package <b>$pkg</b> was not found on this server."
					page_footer; exit 0
				fi
				# Search results page
				echo "<section><h2>Package names matching “$pkg”</h2>"
				echo "<table><thead><tr><th>Name</th><th>Description</th><th>Category</th></tr></thead><tbody>"
				query="$pkg"
				for pkg in $pkgs; do
					# Find main package
					mainpkg=$(awk -F$'\t' -vpkg=" $pkg " '{
						if (index(" " $2 " ", pkg)) {print $1; exit}
					}' $splitdb)
					unset SHORT_DESC CATEGORY; . $wok/$mainpkg/receipt

					unset SHORT_DESC CATEGORY
					[ -e "$wok/$mainpkg/taz/$PACKAGE-$VERSION/receipt" ] &&
						. $wok/$mainpkg/taz/$PACKAGE-$VERSION/receipt

					echo -n "<tr><td><a href="$base/$pkg">${pkg//$query/<mark>$query</mark>}</a>"
					[ "$pkg" == "$mainpkg" ] || echo -n " (${mainpkg//$query/<mark>$query</mark>})"
					echo -n "</td><td>$SHORT_DESC</td><td>$CATEGORY</td></tr>"
				done
				echo '</tbody></table></section>'
				page_footer; exit 0
			fi
			pkg="$mainpkg"
		fi

		log=$LOGS/$pkg.log
		pkg_info

		# Check for a log file and display summary if it exists.
		summary "$log"

		# Informal table with dependencies
		cat <<EOT
<section>
	<h3>Dependencies of packages</h3>
	<table class="half">
		<thead>
			<tr>
				<th>Build dependencies</th>
				<th>Required by</th>
			</tr>
		</thead>
		<tbody>
			<tr>
				<td>
					<table>
EOT
		for i in $BUILD_DEPENDS; do
			echo "<tr><td><img src='$base/s/$i'> <a href='$base/$i'>$i</a></td></tr>"
		done
		cat <<EOT
					</table>
				</td>
				<td>
					<table>
EOT
		{
			for i in $(awk -F$'\t' -vp="$pkg" '{if($1==p)print $2}' $splitdb); do

				[ -s "$PKGS/packages.info" ] &&
				awk -F$'\t' -vp=" $i " '{
					if (index(" " $8 " ", p)) print $1
				}' "$PKGS/packages.info"

				[ -s "$PKGS/bdeps.txt" ] &&
				awk -F$'\t' -vp=" $i " '{
					if (index(" " $2 " ", p)) print $1
				}' $PKGS/bdeps.txt
			done
		} | sort -u | \
		while read i; do
			echo "<tr><td><img src='$base/s/$i'> <a href='$base/$i'>$i</a></td></tr>"
		done
		cat <<EOT
					</table>
				</td>
			</tr>
		</tbody>
	</table>
</section>
EOT

		# Display <Recook> button only for SliTaz web browser
		case "$HTTP_USER_AGENT" in
			*SliTaz*)
				if [ -f $CACHE/cooker-request -a -n "$HTTP_REFERER" ]; then
					if grep -qs "^$pkg$" $CACHE/recook-packages; then
						show_note i "The package “$pkg” has been requested for recook"
					else
						echo "<a class='button' href='$base/?recook=${pkg//+/%2B}'>Recook $pkg</a>"
					fi
				fi
				;;
		esac
		;;

	receipt)
		page_header
		pkg_info
		echo "<a class='button receipt' href='$base/$pkg/receipt'>receipt</a>"
		( cd $wok/$pkg; find stuff -type f 2>/dev/null ) | sort | \
		awk -vb="$base/$pkg" '{printf("<a class=\"button\" href=\"%s/%s\">%s</a>\n", b, $0, $0)}'

		show_code bash < $wok/$pkg/receipt
		;;

	stuff)
		page_header
		pkg_info
		file="$pkg/stuff/$arg"
		echo "<a class='button' href='$base/$pkg/receipt'>receipt</a>"
		( cd $wok/$pkg; find stuff -type f 2>/dev/null ) | sort | \
		awk -vb="$base/$pkg" -va="stuff/$arg" '{
			printf("<a class=\"button%s\" href=\"%s/%s\">%s</a>\n", a==$0 ? " receipt" : "", b, $0, $0)
		}'

		if [ -f "$wok/$file" ]; then
			case $file in
				*.desktop|*.theme)   class="ini" ;;
				*.patch|*.diff|*.u)  class="diff" ;;
				*.sh)                class="bash" ;;
				*.conf*|*.ini)
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
					echo "<img src='$base/$pkg/browse/stuff/$arg' style='display: block; max-width: 100%; margin: auto'/>"
					;;
			esac

			# Display colored listing for all text-based documents (also for *.svg)
			case $file in
				*.png|*.jpg|*.jpeg|*.ico) ;;
				*)
					if [ -z "$raw" ]; then
						cat $wok/$file | show_code $class
					fi
					;;
			esac

			# Display hex dump for binary files
			if [ -n "$raw" ]; then
				hexdump -C $wok/$file | show_code #| sed 's|^\([0-9a-f][0-9a-f]*\)|<span class="c2">\1</span>|'
			fi
		else
			show_note e "File “$file” absent!"
		fi
		;;

	files)
		page_header
		pkg_info

		packaged=$(mktemp)

		# find main package
		wanted=$(. $wok/$pkg/receipt; echo $WANTED)
		main=${wanted:-$pkg}

		# identify split packages
		split="$main $(. $wok/$main/receipt; echo $SPLIT)"
		[ -d "$wok/$main-dev" ] && split="$split $main-dev"
		split="$(echo $split | tr ' ' '\n' | sort -u)"

		# finally we need the version
		if [ -f "$WOK/linux/receipt" ]; then
			kvers=$(. $WOK/linux/receipt; echo $VERSION)
			kbasevers=$(echo $kvers | cut -d. -f1,2)
		elif [ -f "$INSTALLED/linux-api-headers/receipt" ]; then
			kvers=$(. $INSTALLED/linux-api-headers/receipt; echo $VERSION)
			kbasevers=$(echo $kvers | cut -d. -f1,2)
		fi
		ver=$(. $wok/$main/receipt; echo $VERSION$EXTRAVERSION)


		echo "<section><h3>Quick jump:</h3><ul>"
		echo "$split" | sed 'p' | xargs printf "<li><a href='#%s'>%s</a></li>\n"
		echo "<li id='li-repeats' style='display:none'><a href='#repeats'>repeatedly packaged files</a></li>"
		echo "<li id='li-empty' style='display:none'><a href='#empty'>unpackaged empty folders</a></li>"
		echo "<li id='li-orphans' style='display:none'><a href='#orphans'>unpackaged files</a>"
		echo "<span id='orphansTypes'></span></li>"
		echo "</ul></section>"

		for p in $split; do
			namever="$p-$ver"
			if [ -d "$wok/$p/taz/$p-$ver" ]; then
				indir=$p
			elif [ -d "$wok/$main/taz/$p-$ver" ]; then
				indir=$main
			fi
			dir="$wok/$indir/taz/$p-$ver/fs"

			size=$(du -hs $dir | awk '{ sub(/\.0/, ""); print $1 }')

			echo "<section><h3 id='$p'>Contents of package “$namever” (${size:-empty}):</h3>"
			echo '<pre class="files">'
			if [ -s "$wok/$indir/taz/$p-$ver/files.list" ]; then
				echo -n '<span class="underline">permissions·lnk·user    ·'
				echo -en 'group   ·     size·date &amp; time ·name\n</span>'
				cd $dir
				find . -print0 | sort -z | xargs -0 ls -ldp --color=always | \
				syntax_highlighter files | \
				sed "s|\([^>]*\)>\.\([^<]*\)\(<.*\)$|\1 href='$base/$indir/browse/taz/$p-$ver/fs\2'>\2\3|;" | \
				awk 'BEGIN { FS="\""; }
					{ gsub("+", "%2B", $2); print; }'
			else
				echo 'No files'
			fi
			echo '</pre></section>'
			cat $wok/$indir/taz/$p-$ver/files.list >> $packaged
		done

		# find repeatedly packaged files
		repeats="$(sort $packaged | uniq -d)"
		if [ -n "$repeats" ]; then
			echo '<script>document.getElementById("li-repeats").style.display = "list-item"</script>'
			echo -n '<section><h3 id="repeats">Repeatedly packaged files:</h3><pre class="files">'
			echo "$repeats" | sed 's|^|<span class="c11">!!!</span> |'
			echo "</pre></section>"
		fi

		# find unpackaged empty folders
		emptydirs="$(
			cd $wok/$main/install
			find -type d | sed 's|\.||' | \
			while read d; do
				[ -z "$(ls "$wok/$main/install$d")" ] || continue
				echo $d
			done | \
			while read d; do
				notfound='yes'
				for p in $(cd $wok/$main/taz; ls); do
					if [ -d "$wok/$main/taz/$p/fs$d" ]; then
						notfound=''
						break
					fi
				done
				[ -n "$notfound" ] &&
				ls -ldp --color=always .$d | syntax_highlighter files | sed 's|>\./|>/|'
			done
		)"
		if [ -n "$emptydirs" ]; then
			echo '<script>document.getElementById("li-empty").style.display = "list-item"</script>'
			echo -n '<section><h3 id="empty">Unpackaged empty folders:</h3><pre class="files">'
			echo "$emptydirs"
			echo "</pre></section>"
		fi

		# find unpackaged files
		all_files=$(mktemp)
		cd $wok/$main/install; find ! -type d | sed 's|\.||' > $all_files
		orphans="$(sort $all_files $packaged | uniq -u)"
		if [ -d "$wok/$main/install" -a -n "$orphans" ]; then
			echo '<script>document.getElementById("li-orphans").style.display = "list-item"</script>'
			echo '<section><h3 id="orphans">Unpackaged files:</h3>'
			table=$(mktemp)
			echo "$orphans" | awk -vi="$base/$indir/browse/install" '
			function tag(text, color) {
				printf("<span class=\"c%s1\">%s</span> ", color, text);
				printf("<a class=\"c00\" href=\"%s\">%s</a>\n", i $0, $0);
			}
			/\/perllocal.pod$/ || /\/\.packlist$/ || /\/share\/bash-completion\// ||
				/\/lib\/systemd\// || /\.pyc$/ || /\.pyo$/ || /\/fonts\.scale$/ || /\/fonts\.dir$/ {
				tag("---", 0); next }
			/\.pod$/  { tag("pod", 5); next }
			/\/share\/man\// { tag("man", 5); next }
			/\/share\/doc\// || /\/share\/gtk-doc\// || /\/share\/info\// ||
				/\/share\/devhelp\// { tag("doc", 5); next }
			/\/share\/icons\// { tag("ico", 2); next }
			/\/share\/locale\// { tag("loc", 4); next }
			/\.h$/ || /\.a$/ || /\.la$/ || /\.pc$/ || /\/bin\/.*-config$/ ||
				/\/Makefile.*$/ { tag("dev", 3); next }
			{ tag("???", 1) }
			' > $table

			# Summary table
			orphans_types='()'
			for i in head body; do
				case $i in
					head) echo -n '<table class="summary"><tr>';;
					body) echo -n '<th> </th></tr><tr>';;
				esac
				for j in '???1' dev3 loc4 ico2 doc5 man5 pod5 '---0'; do
					tag=${j:0:3}; class="c${j:3:1}0"; [ "$class" == 'c00' ] && class='c01'
					case $i in
						head) echo -n "<th class='$class'>$tag</th>";;
						body)
							tagscount="$(grep ">$tag<" $table | wc -l)"
							printf '<td>%s</td>' "$tagscount"
							[ "$tagscount" -gt 0 ] && orphans_types="${orphans_types/)/ $tag)}"
							;;
					esac
				done
			done
			echo '<td> </td></tr></table>'
			orphans_types="${orphans_types/( /(}"
			[ "$orphans_types" != '()' ] &&
				echo "<script>document.getElementById('orphansTypes').innerText = '${orphans_types// /, }';</script>"

			echo -n '<pre class="files">'
			cat $table
			echo '</pre></section>'
			rm $table
		fi
		rm $packaged $all_files
		;;

	description)
		page_header
		pkg_info
		descs="$(ls $WOK/$pkg/description*.txt)"
		if [ -n "$descs" ]; then
			echo '<div id="content2">'
			[ -f "$WOK/$pkg/description.txt" ] && show_desc "$pkg" "$WOK/$pkg/description.txt"
			for i in $descs; do
				case $i in
					*/description.txt) continue ;;
					*) package=$(echo $i | cut -d. -f2) ;;
				esac
				show_desc "$package" "$i"
			done
			echo '</div>'
		else
			show_note w "No description of $pkg"
		fi
		;;

	log)
		page_header
		pkg_info
		[ -z "$arg" ] && arg=$(stat -c %Y $LOGS/$pkg.log)

		echo '<div class="btnList">'
		acc='l'		# access key for the latest log is 'L'
		while read log; do
			# for all $pkg.log, $pkg.log.0 .. $pkg.log.9, $pkg-pack.log (if any)
			timestamp=$(stat -c %Y $log)
			class=''
			if [ "$arg" == "$timestamp" ]; then
				class=' log'
				logfile="$log"
			fi
			case $log in *-pack.log) acc='p';; esac		# access key for the packing log is 'P'
			echo -n "<a class='button$class' data-acc='$acc' accesskey='$acc' href='$base/$pkg/log/$timestamp'>"
			echo "$(stat -c %y $log | cut -d: -f1,2)</a>"
			case $acc in
				l) acc=0;;
				*) acc=$((acc+1));;
			esac
		done <<EOT
$(find $LOGS -name "$pkg.log*" | sort)
$(find $LOGS -name "$pkg-pack.log")
EOT
		echo '</div>'

		if [ -z "$logfile" ]; then
			show_note e "Requested log is absent"
			page_footer
			exit 0
		fi

		# Define cook variables for syntax highlighter
		if [ -s "$WOK/$pkg/receipt" ]; then
			. "$WOK/$pkg/receipt"
			_wok='/home/slitaz/wok'
			_src="$_wok/$pkg/source/$PACKAGE-$VERSION"
			_install="$_wok/$pkg/install"
			_fs="$_wok/$pkg/taz/$PACKAGE-$VERSION/fs"
			_stuff="$_wok/$pkg/stuff"
		fi

#		if [ ! -f "gzlog/$pkg.$arg" ]; then
#			{
#				summary "$logfile" links
#
#				syntax_highlighter log < $logfile | awk '
#				BEGIN { print "<pre class=\"log\">"; }
#				      { printf("<a name=\"l%d\" href=\"#l%d\">%5d</a>  %s\n", NR, NR, NR, $0); }
#				END   { print "</pre>"; }
#				'
#
#				page_footer
#			} | gzip > gzlog/$pkg.$arg
#		fi

		blog=$(basename $logfile)
		summary "$logfile" links

		# disable next `sed` for the 'like2016' theme
		theme=$(COOKIE theme); theme=${theme:-default}; [ "$theme" != 'like2016' ] && theme=''
		cat $logfile | syntax_highlighter log | \
		sed -e "/(pkg\/local$theme):/ s|: \([^<]*\)|<img src='$base/i/$blog/\1'> \1|" | \
		awk '
		BEGIN { print "<pre class=\"log\">"; }
		      { printf("<span id=\"l%d\">%s</span><a href=\"#l%d\"></a>\n", NR, $0, NR); }
		END   { print "</pre>"; }
		'
		;;


	man|doc|info)
		page_header
		pkg_info
		echo '<div style="max-height: 6.4em; overflow: auto; padding: 0 4px">'

		dir="wok/$pkg/install/usr/share/$cmd"
		[ "$cmd" == 'doc' ] && dir="$dir wok/$pkg/install/usr/share/gtk-doc"
		if [ "$cmd" == 'doc' -a -z "$arg" ]; then
			try=$(for i in $dir; do find $i -name 'index.htm*'; done | sed q)
			[ -n "$try" ] && arg="$try"
		fi
		while read i; do
			[ -s "$i" ] || continue
			case "$i" in
				*.jp*g|*.png|*.gif|*.svg|*.css) continue
			esac
			i=${i#$dir/}
			[ -n "$arg" ] || arg="$i"
			class=''; [ "$arg" == "$i" ] && class=" doc"
			case "$cmd" in
				man)
					case $i in
						man*) lang='';;
						*)    lang="${i%%/*}: ";;
					esac
					man=$(basename $i .gz)
					echo "<a class='button$class' href='$base/$pkg/man/$i'>$lang${man%.*} (${man##*.})</a>"
					;;
				doc)
					echo "<a class='button$class' href='$base/$pkg/doc/$i'>$(basename $i .gz)</a>"
					;;
				info)
					info=$(basename $i)
					echo "<a class='button$class' href='$base/$pkg/info/$i#Top'>${info/.info/}</a>"
					;;
			esac
		done <<EOT
$(for i in $dir; do find $i -type f; done | sort)
EOT
		echo '</div>'

		[ -f "$arg" ] || arg="$dir/$arg"
		if [ -f "$arg" ]; then
			tmp="$(mktemp)"
			docat "$arg" > $tmp
			[ -s "$tmp" ] &&
			case "$cmd" in
				info)
					echo '<div id="content2" class="texinfo"><pre class="first">'
					info2html < "$tmp"
					echo '</pre></div>'
					;;
				doc)
					case "$arg" in
						*.sgml|*.devhelp2) class='xml';;
						*.py)       class='python';; # pycurl package
						*.css)      class='css';;
						*.sh)       class='bash';;
						*)
							first=$(head -n1 "$tmp")
							if [ "${first:0:1}" == '#' ]; then
								class='bash'	# first line begins with '#'
							else
								class='asciidoc'
							fi;;
					esac
					case "$arg" in
						*.htm*)
							case $arg in
								wok/*) page="${arg#wok/}"; page="$base/$pkg/browse/${page#*/}";;
								*)     page="$base/$pkg/browse/install/usr/share/$cmd/$arg";;
							esac
							# make the iframe height so long to contain its contents without scrollbar
							echo "<iframe id='idoc' src='$page' width='100%' onload='resizeIframe(this)'></iframe>"
							;;
						*.pdf)
							case $arg in
								wok/*) page="${arg#wok/}"; page="$base/$pkg/browse/${page#*/}";;
								*)     page="$base/$pkg/browse/install/usr/share/$cmd/$arg";;
							esac
							cat <<EOT
<object id="idoc" data="$page" width="100%" height="100%" type="application/pdf" style="min-height: 600px">
	$(show_note w "Missing PDF plugin.<br/>Get the file <a href="$page">$(basename "$page")</a>.")
</object>
EOT
							;;
						*.md|*.markdown)
							echo '<section>'
							$md2html "$tmp"
							echo '</section>'
							;;
						*)
							show_code $class < "$tmp"
							;;
					esac
					;;
				man)
					#export TEXTDOMAIN='man2html'
					echo "<div id='content2'>"

					html=$(./man2html "$tmp" | sed -e '1,/<header>/d' -e '/<footer>/,$d' \
					-e 's|<a href="file:///[^>]*>\([^<]*\)</a>|\1|g' \
					-e 's|<a href="?[1-9]\+[^>]*>\([^<]*\)</a>|\1|g')

					if [ -n "$(echo "$html" | fgrep 'The requested file /tmp/tmp.')" ]; then
						# Process the pre-formatted man-cat page
						# (for example see sudo package without groff in build dependencies)
						sed -i '
							s|M-bM-^@M-^S|—|g;
							s|M-bM-^@M-^\\|<b>|g;
							s|M-bM-^@M-^]|</b>|g
							s|M-bM-^@M-^X|<u>|g;
							s|M-bM-^@M-^Y|</u>|g;
							s|M-BM-||g;
							s|++oo|•|g;
							s|&|\&amp;|g; s|<|\&lt;|g; s|>|\&gt;|g;
							' "$tmp"
						for i in a b c d e f g h i j k l m n o p q r s t u v w x y z \
								 A B C D E F G H I J K L M N O P Q R S T U V W X Y Z \
								 0 1 2 3 4 5 6 7 8 9 _ - '\\+' '\.' /; do
							sed -i "s|$i$i|<b>$i</b>|g; s|_$i|<u>$i</u>|g" "$tmp"
						done
						echo '<pre class="catman">'
						sed 's|</b><b>||g; s|</u><u>||g; s|</u><b>_</b><u>|_|g; s|</b> <b>| |g;' "$tmp"
						echo '</pre>'
					else
						echo "$html"
					fi
					echo "</div>"
					;;
			esac
			rm -f $tmp
		else
			show_note e "File “$arg” not exists!"
		fi
		;;

	download)
		page_header
		pkg_info
		show=0

		. $wok/$pkg/receipt

		if [ -n "$TARBALL" -a -s "$SRC/$TARBALL" ]; then
			files_header
			echo "<tr><td><a href='$base/src/$TARBALL'>$TARBALL</a></td>"
			ls -lh "$SRC/$TARBALL" | awk '{printf("<td>%sB</td>", $5)}'
			echo "<td>Sources for building the package “$pkg”</td></tr>"
			show=1
		fi

		if [ -d "$wok/$pkg/taz" ]; then
			[ "$show" -eq 1 ] || files_header

			for i in $(all_names); do
				[ -e "$wok/$pkg/taz/$i-$VERSION$EXTRAVERSION/receipt" ] || continue
				. $wok/$pkg/taz/$i-$VERSION$EXTRAVERSION/receipt

				for filename in "$PACKAGE-$VERSION$EXTRAVERSION.tazpkg" "$PACKAGE-$VERSION$EXTRAVERSION-$ARCH.tazpkg"; do
					[ -f "$PKGS/$filename" ] &&
						cat <<EOT
<tr>
<td><a href="$base/get/$filename">$filename</a></td>
<td>$(ls -lh ./packages/$filename | awk '{printf("%sB", $5)}')</td>
<td>$SHORT_DESC</td>
</tr>
EOT
				done
			done
			show=1
		fi

		if [ "$show" -eq 1 ]; then
			echo '</tbody></table></section>'
		else
			show_note w "Sorry, there's nothing to download…"
		fi
		;;

esac


page_footer
exit 0
