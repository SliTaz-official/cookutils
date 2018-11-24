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

case $QUERY_STRING in
	*debug*)
		debug='yes'
		QUERY_STRING="$(echo "$QUERY_STRING" | sed 's|debug||; s|^&||; s|&&|\&|; s|&$||')"
		;;
esac

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
webstat="$CACHE/webstat"		# note, file should be previously created with write permissions for www
splitdb="$CACHE/split.db"
maintdb="$CACHE/maint.db"
repologydb="$CACHE/repology.db"	# note, file should be previously created with write permissions for www

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


# Show the running command and its progression

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
	local theme t='' css pretitle='' command
	theme=$(COOKIE theme)
	[ "$theme" == 'default' ] && theme=''
	[ -n "$theme" ] && theme="-$theme"
	css="cooker$theme.css"

	if [ -n "$pkg" ]; then
		case "$pkg" in
			~) if [ -z "$cmd" ]; then pretitle="Tag cloud - "; else pretitle="Tag \"$cmd\" - "; fi;;
			=) if [ -z "$cmd" ]; then pretitle="Badges - "; else pretitle="Badge \"$cmd\" - "; fi;;
			*) pretitle="$pkg - ";;
		esac
	else
		command="$(cat $command)"
		[ -n "$command" ] && pretitle="$command - "
	fi
	[ -z "$favicon" ] && favicon='/slitaz-cooker.png'

	echo -e 'Content-Type: text/html; charset=UTF-8\n'

	cat <<EOT
<!DOCTYPE html>
<html lang="en">
<head>
	<title>$pretitle$title</title>
	<link rel="stylesheet" href="/$css">
	<link rel="icon" type="image/png" href="$favicon">
	<link rel="search" href="$base/os.xml" title="$title" type="application/opensearchdescription+xml">
	<!-- mobile -->
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<meta name="theme-color" content="#222">
	<!-- rss -->
	<link rel="alternate" type="application/rss+xml" title="$title Feed" href="?rss">
	<script>
		// Get part of the main page
		function getPart(part) {
			var partRequest = new XMLHttpRequest();
			partRequest.onreadystatechange = function() {
				if (this.readyState == 4 && this.status == 200) {
					response = this.responseText;
					var partElement = document.getElementById(part);
					if (response !== null) partElement.innerHTML = response;
				}
			};
			partRequest.open('GET', '?part=' + part, true);
			partRequest.responseType = '';
			partRequest.send();
		}
	</script>
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

	[ -n "$debug" ] && echo "<pre><code class='language-ini'>$(env | sort)</code></pre>"
}


# HTML page footer

page_footer() {
	date_now=$(date +%s)
	sec_now=$(date +%S); sec_now=${sec_now#0} # remove one leading zero
	wait_sec=$(( 60 - $sec_now ))
	cat <<-EOT
	</main>

	<footer>
		<a href="http://www.slitaz.org/">SliTaz Website</a>
		<a href="http://tank.slitaz.org/graphs.php">Server status</a>
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


# Proxy to the Repology
# Problems:
# 1. Function "latest packaged version" widely used here and it has no JSON API, but only SVG badge.
# 2. So, all version comparisons can be only visual and not automated.
# 3. If the thousands of badges present on the web page, many of them are broken (maybe server
#    drops requests), while our server displays status icons well.
# 4. Default badges are wide and not customizable.
# Solution:
# 1. Make local cache. Update it on demand, but no more than once a day (Repology caches info
#    on a hourly basis). Use cached values when they are not expired.
# 2. Extract and save version(s) from the SVG badges. Values can be compared in the scripts as well
#    as custom badges that may also be provided.

repology_get() {
	local found versions day=$(date +%j)		# %j is the number of the day in the year
	found=$(awk -F$'\t' -vpkg="$1" -vday="$day" '{
		if ($1 == pkg && $2 == day) { print $3; exit; }
	}' $repologydb)
	if [ -n "$found" ]; then
		echo "$found"
	else
		# set HOST_WGET in cook.conf
		versions=$($HOST_WGET -q -T 20 -O- https://repology.org/badge/latest-versions/$1.svg \
		| sed '/<text /!d; /fill/d; /latest/d; s|.*>\(.*\)<.*|\1|; s|, | |g') # space separated list
		if [ -n "$versions" ]; then
			sed -i "/^$1	/d" $repologydb
			echo -e "$1\t$day\t$versions" >> $repologydb
			echo $versions
		fi
	fi
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
	echo -en "Content-Type: image/svg+xml\n\n<svg xmlns='http://www.w3.org/2000/svg' height='12' width='8'><path d='"
	# packages.info updates with each new package, so we'll find actual info here
	if grep -q "^$cmd"$'\t' $PKGS/packages-$ARCH.info; then
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
			cat <<-EOT
				<section>
					<h2>Change theme</h2>
					<p>Current theme: “${current:-default}”. Select other:</p>
					<ul>$(
							for i in default emerald sky goldenrod midnight like2016 terminal; do
								[ "$i" == "${current:-default}" ] || echo "<li><a href=\"$base/?theme=$i&amp;ref=$ref\">$i</a></li>"
							done
					)</ul>
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
	cat <<-EOT
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
		sed -e "/\?pkg=/s|http[^=]*=|$cooker_url|;" \
			-e "s|\([0-9]\)</pubDate>|\1 GMT</pubDate>|" $rss
	done
	cat <<-EOT
		</channel>
		</rss>
	EOT
	exit 0
fi


### OpenSearch ###

# Query '/os.xml': get OpenSearch Description

if [ "$pkg" == 'os.xml' ]; then
	cat <<-EOT
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
		-e 's|&|\&amp;|g; s|<|\&lt;|g; s|>|\&gt;|g;' \
		-e "s|\`\([^']*\)'|<b>\1</b>|g" \
		-e 's|"\([A-Za-z0-9]\)|“\1|g; s|"|”|g' \
		-e 's|^\* \(.*\)::|* <a href="#\1">\1</a>  |' \
		-e 's|\*note \(.*\)::|<a href="#\1">\1</a>|' \
		-e '/^File: / s|(dir)|Top|g' \
		-e '/^File: / s|Next: \([^,]*\)|<a class="button icon next" href="#\1">Next: \1</a>|' \
		-e '/^File: / s|Prev: \([^,]*\)|<a class="button icon prev" href="#\1">Prev: \1</a>|' \
		-e '/^File: / s|Up: \([^,]*\)|<a class="button icon up" href="#\1">Up: \1</a>|' \
		-e '/^File: / s|^.* Node: \([^,]*\), *\(.*\)$|<pre id="\1">\2|' \
		-e '/^<pre id=/ s|^\([^>]*>\)\(<a[^>]*>Next: [^,]*\), *\(<a[^>]*>Prev: [^,]*\), *\(<a[^>]*>Up: .*\)|\1<div class="buttonbar">\3 \4 \2</div>|' \
		-e '/^<pre id=/ s|^\([^>]*>\)*\(<a[^>]*>Prev: [^,]*\), *\(<a[^>]*>Up: .*\)|\1<div class="buttonbar">\2 \3 <a class="button icon next" href="#">Next</a></div>|' \
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
			# <b>is error (red)</b> <u>is warning (orange)</u> <i>is informative (green)</i>
			sed	\
				-e 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g' \
				-e 's#OK$#<i>OK</i>#' \
				-e 's#\([Dd]one\)$#<i>\1</i>#' \
				-e 's#Success$#<i>Success</i>#' \
				-e 's#\([^a-z]\)ok$#\1<i>ok</i>#' \
				-e 's#\([^a-z]\)yes$#\1<i>yes</i>#' \
				-e 's#: \(YES.*\)#: <i>\1</i>#' \
				-e 's#\([^a-z]\)ON$#\1<i>ON</i>#' \
				-e 's#\(enabled\)$#<i>\1</i>#' \
				-e 's#\([^a-z]\)no$#\1<u>no</u>#' \
				-e 's#: \(NO.*\)#: <u>\1</u>#' \
				-e 's#\([^a-z]\)none$#\1<u>none</u>#' \
				-e 's#\([^a-z]\)false$#\1<u>false</u>#' \
				-e 's#\([^a-z]\)OFF$#\1<u>OFF</u>#' \
				-e 's#\(disabled\)$#<u>\1</u>#' \
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
				-e 's#^.*multiple definition of.*#<b>\0</b>#' \
				-e 's#^.*[Ff][Aa][Ii][Ll][Ee][Dd].*#<b>\0</b>#' \
				-e 's#^.*[^A-Za-z:/-][Ff]atal.*#<b>\0</b>#' \
				-e '/non-fatal/ s|</*b>||g' \
				-e 's#^.*[Nn]ot found.*#<b>\0</b>#' \
				-e 's#^.*[Nn]o such file.*#<b>\0</b>#' \
				-e 's#^.*No package .* found.*#<b>\0</b>#' \
				-e 's#^.*Unable to find.*#<b>\0</b>#' \
				-e 's#[^a-zA-Z-][Ii]nvalid.*#<b>\0</b>#' \
				-e 's#Segmentation fault#<b>\1</b>#' \
				-e 's#\([Nn][Oo][Tt] found\.*\)$#<b>\1</b>#' \
				-e 's#\(found\.*\)$#<i>\1</i>#' \
				\
				-e 's#^.*WARNING:.*#<u>\0</u>#' \
				-e 's#^.*warning:.*#<u>\0</u>#' \
				-e 's#^.* [Ee]rror:* .*#<b>\0</b>#' \
				-e 's#^.*terminated.*#<b>\0</b>#' \
				-e 's#\(missing\)#<b>\1</b>#g' \
				-e 's#^.*[Cc]annot find.*#<b>\0</b>#' \
				-e 's#^.*unrecognized option.*#<u>\0</u>#' \
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
				-e 's|^Switching to the .*|<span class="switch">‣‣‣ \0</span>|' \
				\
				-e 's|^<u>\(.*libtool: warning: relinking.*\)</u>|\1|' \
				-e 's|^<u>\(.*libtool: warning: .* has not been installed in .*\)</u>|\1|' \
				-e 's|^<u>\(.*checking for a sed.*\)</u>|\1|' \
				-e 's|^<u><b>\(.*inlining failed.*\)</b></u>|<u>\1</u>|' \
				\
				-e "s|$_src|<var>\${src}</var>|g;
					s|$_install|<var>\${install}</var>|g;
					s|$_fs|<var>\${fs}</var>|g;
					s|$_stuff|<var>\${stuff}</var>|g" \
				\
				-e "s|\[\([01]\)m\[3\([1-7]\)m|<span class='c\2\1'>|g;
					s|\[\([01]\);3\([1-7]\)m|<span class='c\2\1'>|g;
					s|\[3\([1-7]\)m|<span class='c\10'>|g;
					s|\[\([01]\);0m|<span class='c0\1'>|g;
					s|\[0m|</span>|g;
					s|\[m|</span>|g;
					s|\[0;10m|</span>|g;
					s|\[K||g;" \
				\
				-e "s|\[9\([1-6]\)m|<span class='c\10'>|;
					s|\[39m|</span>|;
					#s|\[1m|<span class='c01'>|g;
					s|\[1m|<span style='font-weight:bold'>|g; s|(B|</span>|g;
					s|\[m||g;" \
				\
				-e "s!^|\(+.*\)!|<span class='c20'>\1</span>!;
					s!^|\(-.*\)!|<span class='c10'>\1</span>!;
					s!^|\(@@.*@@\)\$!|<span class='c30'>\1</span>!;" \
				\
				-e "s|^Successfully installed [^ ][^ ]*$|<i>\0</i>|;
					s|^Successfully installed .*$|<b>\0</b>|;
					s|^\(Requirement already satisfied: .*\) in|<i>\1</i> in|;
					s|^Collecting .* (from .*$|<b>\0</b>|;
					s|^  Could not find.*|<b>\0</b>|;
					s|^No matching distribution found for.*|<b>\0</b>|;"

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
				 s|^\(-rwsr-xr-x\)|<span class='c51'>\1</span>|;
				 s|^\([lrwxs-][lrwxs-]*\)|<span class='c11'>\1</span>|;
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
			show_note i "The Cooker is currently building $pkg" \
			| sed 's|>|&<progress id="gauge" class="meter-small" max="100" value="0"></progress> |'
			echo "<script>updatePkg = '${pkg//+/%2B}';</script>"
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
			# second line of log is "Cook: <package> <version>"
			echo -e "<section>\n<h3>Debug information for $(sed '2!d; s|.*: ||' $log)</h3>"
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
	local log active bpkg short_desc=''
	log="$LOGS/$pkg.log"

	echo -n "<div id=\"hdr\"><a href=\"$base/${requested_pkg:-$pkg}\">"
	if [ -e $wok/$pkg/.icon.png ]; then
		echo -n "<img src=\"$base/$pkg/browse/.icon.png\" alt=\"$pkg icon\"/>"
	else
		echo -n "<img src=\"/tazpkg.png\" alt=\"package icon\"/>"
	fi
	echo -n "</a>"
	echo -n "<h2><a href=\"$base/${requested_pkg:-$pkg}\">${requested_pkg:-$pkg}</a>"
	# Get short description for existing packages
	[ -f $PKGS/packages.info ] &&
	short_desc="$(awk -F$'\t' -vp="${requested_pkg:-$pkg}" '{if ($1 == p) { printf("%s", $4); exit; }}' $PKGS/packages.info)"
	# If package does not exist (not created yet or broken), get short description
	# (but only for "main" package) from receipt
	[ -n "$short_desc" ] || short_desc="$(. $wok/$pkg/receipt; echo "$SHORT_DESC")"
	echo "<br/>$short_desc</h2></div>"
	echo '<div id="info">'
	echo "<a class='button icon receipt$(active receipt stuff)' href='$base/$pkg/receipt'>receipt &amp; stuff</a>"

	# In the receipts $EXTRAVERSION is defined using $kvers, get it here [copy from 'cook' set_paths()]
	if [ -f "$wok/linux/receipt" ]; then
		kvers=$(. $wok/linux/receipt; echo $VERSION)
		kbasevers=$(echo $kvers | cut -d. -f1,2)
	elif [ -f "$INSTALLED/linux-api-headers/receipt" ]; then
		kvers=$(. $INSTALLED/linux-api-headers/receipt; echo $VERSION)
		kbasevers=$(echo $kvers | cut -d. -f1,2)
	fi

	unset WEB_SITE WANTED
	. $wok/$pkg/receipt

	[ -n "$WEB_SITE" ] &&
		echo "<a class='button icon website' href='$WEB_SITE' target='_blank' rel='noopener noreferrer'>web site</a>"

	[ -f "$wok/$pkg/taz/$PACKAGE-$VERSION$EXTRAVERSION/receipt" ] &&
		echo "<a class='button icon files$(active files)' href='$base/$pkg/files'>files</a>"

	[ -n "$(ls $wok/$pkg/description*.txt)" ] &&
		echo "<a class='button icon desc$(active description)' href='$base/$pkg/description'>description</a>"

	[ -n "$TARBALL" -a -s "$SRC/$TARBALL" -o -d "$wok/$pkg/taz" ] &&
		echo "<a class='button icon download' href='$base/$pkg/download'>downloads</a>"

	echo "<a class='button icon browse' href='$base/$pkg/browse/'>browse</a>"

	[ -x ./man2html.bin -a -d "$wok/$pkg/install/usr/share/man" ] &&
		echo "<a class='button icon doc$(active man)' href='$base/$pkg/man/'>man</a>"

	[ -d "$wok/$pkg/install/usr/share/doc" -o -d "$wok/$pkg/install/usr/share/gtk-doc" ] &&
		echo "<a class='button icon doc$(active doc)' href='$base/$pkg/doc/'>doc</a>"

	[ -d "$wok/$pkg/install/usr/share/info" ] &&
		echo "<a class='button icon doc$(active info)' href='$base/$pkg/info/#Top'>info</a>"

	if [ -n "$LFS" ]; then
		printf "<a class='button icon lfs' href='%s' target='_blank' rel='noopener noreferrer'>" "$LFS"
		[ "${LFS/blfs/}" != "$LFS" ] && printf "B"
		printf "LFS</a>\n"
	fi

	ls $log* >/dev/null 2>&1 &&
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
	# Get package names from $SPLIT variable
	local split=$(echo $SPLIT \
		| awk '
			BEGIN { RS = " "; FS = ":"; }
			{ print $1; }' \
		| tr '\n' ' ')
	local split_space=" $split "
	if ! head -n1 $WOK/$pkg/receipt | fgrep -q 'v2'; then
		# For receipts v1: $SPLIT may present in the $WANTED package,
		# but split packages have their own receipts
		echo $PACKAGE
	elif [ "${split_space/ $PACKAGE /}" != "$split_space" ]; then
		# $PACKAGE included somewhere in $SPLIT (probably in the end).
		# We should build packages in the order defined in the $SPLIT.
		echo $split
	else
		# We'll build the $PACKAGE, then all defined in the $SPLIT.
		echo $PACKAGE $split
	fi
}


toolchain_version() {
	echo "<tr><td><a href='$base/$1'>$1</a></td>"
	awk -F$'\t' -vpkg="$1" '
	BEGIN { version = description = "---"; }
	      {
	        if ($1 == pkg) { version = $2; description = $4; }
	      }
	END   { printf("<td>%s</td><td>%s</td></tr>", version, description); }
	' $PKGS/packages.info
}


files_header() {
	echo '<section><h3>Available downloads:</h3>'
	echo '<table><thead><tr><th>File</th><th>Size</th><th>Description</th></tr></thead><tbody>'
}


# Update statistics used in web interface.
# There is no need to recalculate the statistics every time the page is displayed.
# Note, $webstat file must be owned by www, otherwise this function will not be able to do the job.

update_webstat() {
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

	cat > $webstat <<-EOT
		rtotal="$rtotal"; rcooked="$rcooked"; runbuilt="$runbuilt"; rblocked="$rblocked"; rbroken="$rbroken"
		ptotal="$ptotal"; pcooked="$pcooked"; punbuilt="$punbuilt"; pblocked="$pblocked"; pbroken="$pbroken"
	EOT
}


# Show badges for specified package

show_badges() {
	local t p s # title problem solution

	case $layout in
		table)
			echo "<section><h2>Badges</h2><table class=\"badges\"><thead><tr><th></th><th>Problem</th><th>Solution</th></tr></thead><tbody>"
			;;
		list)
			echo "<section><h2>Badges list</h2><p>Click on badge to get list of packages</p><table class=\"badges\"><thead><tr><th></th><th>Problem</th></tr></thead><tbody>"
			;;
	esac

	for badge in $@; do
		case $badge in
			bdbroken)
				t="Broken bdeps"
				p="This package cannot be built because its creation depends on broken packages"
				s="Fix broken build dependencies"
				;;
			broken)
				t="Broken package"
				p="Package is broken"
				s="Fix package build: analyze <a href=\"log/\">logs</a>, upgrade the version, search for patches"
				;;
			any)
				t="“Any” arch"
				p="This package contains only architecture-less <a href=\"files\">files</a>, it does not make sense to make it several times in each build environment"
				s="Add the line <code>HOST_ARCH=\"any\"</code> to <a href=\"receipt\">receipt</a>"
				;;
			noany)
				t="No “any” arch"
				p="This package contains architecture dependent <a href=\"files\">files</a>"
				s="Remove the line <code>HOST_ARCH=\"any\"</code> from <a href=\"receipt\">receipt</a>"
				;;
			libtool)
				t="Libtool isn't fixed"
				p="This package use <code>libtool</code> that likes to add unnecessary dependencies to programs and libraries"
				s="Add the <code>fix libtool</code> command to the <a href=\"receipt\">receipt</a> between the <code>configure</code> and <code>make</code> commands invocation"
				;;
			nolibtool)
				t="Libtool is absent"
				p="This package does not use <code>libtool</code>, nothing to fix"
				s="Remove the command <code>fix libtool</code> from <a href=\"receipt\">receipt</a>"
				;;
			own)
				t="Ownership problems"
				p="Some files of this package have <a href=\"files\">ownership problems</a>"
				s="Correct the ownership or add problem files to the “<a href=\"stuff/overrides\">overrides</a>” list if you believe it is OK"
				;;
			ownover)
				t="Ownership overridden"
				p="This package contains files with <a href=\"files\">ownership problems</a> that have been overridden"
				s="<abbr title=\"For your information\">FYI</abbr> only, you may want to revise <a href=\"stuff/overrides\">the list</a>"
				;;
			perm)
				t="Permissions problems"
				p="Some files of this package have <a href=\"files\">unusual permissions</a>"
				s="Correct the permissions or add problem files to the “<a href=\"stuff/overrides\">overrides</a>” list if you believe it is OK"
				;;
			permover)
				t="Permissions overridden"
				p="This package contains files with <a href=\"files\">unusual permissions</a> that have been recorded"
				s="<abbr title=\"For your information\">FYI</abbr> only, you may want to revise <a href=\"stuff/overrides\">the list</a>"
				;;
			symlink)
				t="Broken symlink"
				p="This package contains one or more <a href=\"files\">broken symlinks</a>"
				s="Fix the symlinks destination; you may use <code>fix symlinks</code> when symlinks have absolute path"
				;;
			ss)
				t="Site script"
				p="This autotools-based building system use site script; most of paths (like <var>prefix</var>, <var>sysconfdir</var> and <var>mandir</var>) are defined there with correct default values"
				s="You may remove your paths from <code>configure</code> invocation"
				;;
			fadd)
				t="Files have been added"
				p="Some files absent in <var>\$install</var> was <a href=\"files#outoftree\">directly added</a> to <var>\$fs</var>"
				s="Rework your <code>compile_rules()</code> to add all the required files to <var>\$install</var> there"
				;;
			frem)
				t="Files have been removed"
				p="Some files existing in <var>\$install</var> <a href=\"files#orphans\">not belong to any package</a>"
				s="Revise <code>genpkg_rules()</code> or add files to “<a href=\"stuff/overrides\">overrides</a>” list"
				;;
			fdup)
				t="Files are duplicated"
				p="Some files existing in <var>\$install</var> was added to <a href=\"files#repeats\">more than one</a> package"
				s="Check your copy rules in <code>genpkg_rules()</code>"
				;;
			old)
				t="Oldie"
				p="According to Repology, this package may be <a href=\"https://repology.org/metapackage/${REPOLOGY:-$pkg}\" target=\"_blank\" rel=\"noopener noreferrer\">outdated</a>"
				s="Update the package"
				;;
			win)
				t="Winner"
				p="This package has no problems"
				s="Well done, keep it up!"
				;;
			orphan)
				t="Orphaned package"
				p="It seems that no other package depends on this one"
				s="See if anyone needs it"
				;;
			patch)
				t="Patch"
				p="Patch has been applied"
				s="<abbr title=\"For your information\">FYI</abbr> only, you may want to revise <a href=\"$base/$PACKAGE/stuff/patches/series\">the list of patches</a>"
				;;
		esac
		case $layout in
			table)
				echo "<tr><td><span class=\"badge $badge\" title=\"$t\"/></td><td>$p</td><td>$s</td></tr>"
				;;
			list)
				p=$(echo $p | sed 's|<a [^>]*>\([^<]*\)</a>|\1|g')
				s=$(echo $s | sed 's|<a [^>]*>\([^<]*\)</a>|\1|g|')
				echo "<tr><td><a href=\"$badge\"><span class=\"badge $badge\" title=\"$t\"/></a></td><td>$p</td></tr>"
				;;
			*)
				echo -n "<span class=\"badge $badge\" title=\"$t\"/>"
				;;
		esac
	done

	case $layout in
		table|list)
			echo "</tbody></table></section>"
			;;
	esac
}


# Generate part of the main page

part() {
	echo -n "<div id='$1'>"

	case $1 in
		summary)
			echo '<h2>Summary</h2>'

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
			;;
		webstat)
			# Do we need to update the statistics?
			if [ -n "$nojs" -a "$activity" -nt "$webstat" ]; then update_webstat; fi
			. $webstat

			pct=0; [ "$rtotal" -gt 0 ] && pct=$(( ($rcooked * 100) / $rtotal ))

			cat <<-EOT
				<div class="meter"><progress max="100" value="$pct">${pct}%</progress><span>${pct}%</span></div>

				<table class="webstat">
					<thead>
						<tr>
							<th>        </th>
							<th>Total  </th>
							<th>Cooked  </th>
							<th>Unbuilt  </th>
							<th>Blocked  </th>
							<th>Broken  </th>
						</tr>
					</thead>
					<tbody>
						<tr>
							<td>Receipts</td>
							<td>$rtotal</td>
							<td>$rcooked</td>
							<td>$runbuilt</td>
							<td>$rblocked</td>
							<td>$rbroken</td>
						</tr>
						<tr>
							<td>Packages</td>
							<td>$ptotal</td>
							<td>$pcooked</td>
							<td>$punbuilt</td>
							<td>$pblocked</td>
							<td>$pbroken</td>
						</tr>
					</tbody>
				</table>
			EOT
			if [ -z "$nojs" ]; then echo "<script>getPart('$1')</script>"; fi
			;;
		activity)
			tac $activity | head -n12 | sed 's|cooker.cgi?pkg=||;
				s|\[ Done|<span class="r c20">Done|;
				s|\[ Failed|<span class="r c10">Failed|;
				s|\[ -Failed|<span class="r c10"><del>Failed</del>|;
				s| \]|</span>|;
				s|%2B|\+|g' \
			| while read line; do
				case "$line" in
					*data-badges=*)
						badges="$(echo "$line" | sed "s|.*data-badges='\([^']*\)'.*|\1|")"
						echo "$line" | sed "s|</a>|</a> $(show_badges "$badges")|"
						;;
					*)
						echo "$line"
						;;
				esac
			done | section $activity 12 "Activity|More activity" \
			;;
		cooknotes)
			[ -s "$cooknotes" ] && tac $cooknotes | head -n12 | \
				section $cooknotes 12 "Cooknotes|More notes"
			;;
		commits)
			[ -s "$commits" ] && head -n20 $commits | \
				section $commits 20 "Commits|More commits"
			;;
		cooklist)
			[ -s "$cooklist" ] && head -n 20 $cooklist | \
				section $cooklist 20 "Cooklist|Full cooklist"
			;;
		broken)
			[ -s "$broken" ] && head -n20 $broken | sed "s|^[^']*|<a href='\0'>\0</a>|g" | \
				section $broken 20 "Broken|All broken packages"
			;;
		blocked)
			[ -s "$blocked" ] && sed "s|^[^']*|<a href='\0'>\0</a>|g" $blocked | \
				section $blocked 12 "Blocked|All blocked packages"
			;;
		pkgs)
			cd $PKGS
			# About BusyBox's `ls`
			# On the Tank server: BusyBox v1.18.4 (2012-03-14 03:32:25 CET) multi-call binary.
			# It supported the option `-e`, output with `-let` options like this:
			# -rw-r--r--    1 user     group       100000 Fri Nov  3 10:00:00 2017 filename
			# 1             2 3        4           5      6   7    8 9        10   11
			# Newer BusyBox v1.27.2 doesn't support option `-e` and has no configs to
			# configure it or return the option back. It supported the long option
			# `--full-time` instead, but output is different:
			# -rw-r--r--    1 user     group       100000 2017-11-03 10:00:00 +0200 filename
			# 1             2 3        4           5      6          7        8     9
			if ls -let >/dev/null 2>&1; then
				ls -let *.tazpkg \
				| awk '
				(NR<=20){
					sub(/:[0-9][0-9]$/, "", $9);
					mon = index("  JanFebMarAprMayJunJulAugSepOctNovDec", $7) / 3;
					printf("%d-%02d-%02d %s : <a href=\"get/%s\">%s</a>\n", $10, mon, $8, $9, $11, $11);
				}' \
				| section $activity 1000 "Latest cook"
			else
				ls -lt --full-time *.tazpkg \
				| awk '
				(NR<=20){
					sub(/:[0-9][0-9]$/, "", $7);
					printf("%s %s : <a href=\"get/%s\">%s</a>\n", $6, $7, $9, $9);
				}' \
				| section $activity 1000 "Latest cook"
			fi
			;;
	esac
	echo "</div>"
}


# Query '?part=<part>': get part of the main page

if [ -n "$(GET part)" ]; then
	part="$(GET part)"
	case $part in
		summary|webstat|activity|cooknotes|commits|cooklist|broken|blocked|pkgs)
			nojs='yes'
			part $part
			;;
	esac
	exit 0
fi




#
# Load requested page
#

if [ -z "$pkg" ]; then

	page_header
	if [ -n "$QUERY_STRING" ]; then

		[ "$QUERY_STRING" != 'commits.log' ] &&
		for list in activity cooknotes cooklist commits; do
			[ -n "$(GET $list)" ] || continue
			case $list in
				cooklist) nb="- Packages: $(wc -l < $cooklist)";;
				commits)  nb="- Packages: $(wc -l < $commits)";;
			esac
			echo '<section id="content2">'
			echo "<h2>DB: $list $nb</h2>"

			tac $CACHE/$list | sed 's|cooker.cgi?pkg=||; s|%2B|+|g;
				s|\[ Done|<span class="r c20">Done|;
				s|\[ Failed|<span class="r c10">Failed|;
				s|\[ -Failed|<span class="r c10"><del>Failed</del>|;
				s| \]|</span>|;
				s|%2B|\+|g' \
			| while read line; do
				case "$line" in
					*data-badges=*)
						badges="$(echo "$line" | sed "s|.*data-badges='\([^']*\)'.*|\1|")"
						echo "$line" | sed "s|</a>|</a> $(show_badges "$badges")|"
						;;
					*)
						echo "$line"
						;;
				esac
			done \
			| mktable $list

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
					if [ "$QUERY_STRING" == 'pkgdb.log' ]; then
						# Display button only for SliTaz web browser
						case "$HTTP_USER_AGENT" in
							*SliTaz*)
								if [ -f $CACHE/cooker-request -a -n "$HTTP_REFERER" ]; then
									if grep -qs '^pkgdb$' $CACHE/recook-packages; then
										show_note i "The package database has been requested for re-creation"
									else
										echo "<a class='button' href='$base/?recook=pkgdb'>Re-create the DB</a>"
									fi
								fi
								;;
						esac
					fi
				else
					show_note e "No log file: $log"
				fi
				;;
			toolchain)
				cat <<-EOT
					<div id="content2">
					<section>
					<h2>SliTaz GNU/Linux toolchain</h2>

					<table>
						<tr>
							<td>Build date</td>
							<td colspan="2">$(sed -n '/^Cook date/s|[^:]*: \(.*\)|\1|p' $LOGS/slitaz-toolchain.log)</td>
						</tr>
						<tr>
							<td>Build duration</td>
							<td colspan="2">$(sed -n '/^Cook time/s|[^:]*: \(.*\)|\1|p' $LOGS/slitaz-toolchain.log)</td>
						</tr>
						<tr>
							<td>Architecture</td>
							<td colspan="2">$ARCH</td>
						</tr>
						<tr>
							<td>Host system</td>
							<td colspan="2">$BUILD_SYSTEM</td>
						</tr>
						<tr>
							<td>Target system</td>
							<td colspan="2">$HOST_SYSTEM</td>
						</tr>
						<tr>
							<th>Package</th>
							<th>Version</th>
							<th>Description</th>
						</tr>
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
			maintainer*)
				maintainer=$(GET maintainer); maintainer=${maintainer/maintainer/}
				regexp=$(GET regexp); regexp=${regexp/regexp/}
				[ -n "$regexp" ] && maintainer=''
				cat <<-EOT
					<section>
						<h2>For maintainers</h2>
						<p>Here you can <a href="=/">explore the badges</a>.</p>
						<p>Or see some <a href="?maintainer&amp;stats">repository statistics</a>.</p>
						<p>Or check packages version either for specified maintainer or using regular expression:</p>
						<form>
							<select name="maintainer">
								<option value=''>--- select maintainer ---
				EOT
				cut -d$'\t' -f1 $maintdb | sort -u \
				| awk -vm=$maintainer '{
					selected=$0==m?"selected":""
					printf("<option %s value=\"%s\">%s\n", selected, $0, $0)
				}'
				cat <<-EOT
							</select>
							or
							<input type="text" name="regexp" value="$regexp"/>
							<button type="submit">Go</button>
						</form>
				EOT
				if [ -n "$maintainer" -o -n "$regexp" ]; then
					tmp_status=$(mktemp)
					cat <<-EOT
						<table class="maint">
						<thead><tr><th>Package</th><th>Version</th><th>Repology</th></tr></thead>
					EOT
					{
						if [ -n "$maintainer" ]; then
							awk -vm=$maintainer '{if ($1 == m) print $2}' $maintdb
						fi
						if [ -n "$regexp" ]; then
							cd $wok; ls | grep "$regexp"
						fi
					} | while read pkg; do
						unset VERSION; REPOLOGY=$pkg
						. $wok/$pkg/receipt
						ver=$(awk -F$'\t' -vpkg="$pkg" '{if ($1 == pkg) {print $2; exit}}' $PKGS/packages.info)
						if [ "$REPOLOGY" == '-' ]; then
							unset repo_info1 repo_info2
							echo '-' >>$tmp_status
						else
							repo_ver=$(repology_get $REPOLOGY)
							if [ "$repo_ver" == '-' ]; then
								echo '-' >>$tmp_status
								icon='more'
							else
								if echo " $repo_ver " | fgrep -q " ${ver:-$VERSION} "; then
									icon='actual'
								else
									icon='update'
								fi
								echo $icon >>$tmp_status
							fi
							repo_info1="<a class='icon $icon' href='https://repology.org/metapackage/$REPOLOGY' target='_blank'"
							repo_info2="rel='noopener noreferrer' title='latest packaged version(s)'>${repo_ver// /, }</a>"
						fi
						cat <<-EOT
							<tr>
								<td><img src="$base/s/$pkg" alt="$pkg"> <a href="$pkg">$pkg</a></td>
								<td>${ver:-$VERSION}</td>
								<td>$repo_info1 $repo_info2</td>
							</tr>
						EOT
					done

					pkg_total=$(   wc -l      < $tmp_status)
					pkg_actual=$(  fgrep actual $tmp_status | wc -l)
					pkg_outdated=$(fgrep update $tmp_status | wc -l)
					pkg_unknown=$( fgrep '-'    $tmp_status | wc -l)

					pct_actual=$((   $pkg_actual   * 100 / $pkg_total ))
					pct_outdated=$(( $pkg_outdated * 100 / $pkg_total ))
					pct_unknown=$((  $pkg_unknown  * 100 / $pkg_total ))

					[ "$pkg_actual"   -eq 0 ] && pkg_actual=''
					[ "$pkg_outdated" -eq 0 ] && pkg_outdated=''
					[ "$pkg_unknown"  -eq 0 ] && pkg_unknown=''

					cat <<-EOT
						</table>

						<div class="meter" style="width:100%;text-align:center"><div
						style="display:inline-block;background-color:#090;width:$pct_actual%">$pkg_actual</div><div
						style="display:inline-block;background-color:#f90;width:$pct_outdated%">$pkg_outdated</div><div
						style="display:inline-block;background-color:#ccc;width:$pct_unknown%">$pkg_unknown</div></div>
					EOT
					rm $tmp_status
				fi
				cat <<-EOT
					</section>
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

	cat <<-EOT
		<div id="content2">

		<section>
		<form method="get" action="" class="search r">
			<input type="hidden" name="search" value="pkg"/>
			<button type="submit" title="Search">Search</button>
			<input type="search" name="q" placeholder="Package" list="packages" autocorrect="off" autocapitalize="off"/>
		</form>
	EOT

	unset nojs
	part summary
	part webstat

	cat <<-EOT
		<p>
			Service logs:
			<a href="?cookorder.log">cookorder</a> ·
			<a href="?commits.log">commits</a> ·
			<a href="?pkgdb.log">pkgdb</a>
		</p>
	EOT

	if [ -e "$CACHE/cooker-request" -a ! -s $command ]; then
		if [ "$activity" -nt "$CACHE/cooker-request" ]; then
			echo '<a class="button icon bell r" href="?poke">Wake up</a>'
		else
			show_note i 'Cooker will be launched in the next 5 minutes.'
		fi
	fi

	cat <<-EOT
		<a class="button icon maintainers" href="?maintainer">For maintainers</a>
		<a class="button icon tag" href="~/">Tags</a>
		</section>
	EOT

	part activity
	part cooknotes
	part commits
	part cooklist
	part broken
	part blocked
	part pkgs

	echo '</div>'
	datalist
	page_footer
	exit 0
fi


# show tag

if [ "$pkg" == '~' ]; then
	page_header
	echo '<div id="content2"><section>'

	if [ -n "$cmd" ]; then
		tag="$cmd"
		cat <<-EOT
			<h2>Tag “$tag”</h2>

			<table>
				<thead><tr><th>Name</th><th>Description</th><th>Category</th></tr></thead>
				<tbody>
		EOT
		sort $PKGS/packages-$ARCH.info \
		| awk -F$'\t' -vtag=" $tag " -vbase="$base/" '{
			if (index(" " $6 " ", tag)) {
				url = base $1 "/";
				gsub("+", "%2B", url);
				printf("<tr><td><img src=\"%ss/%s\" alt=\"%s\"> ", base, $1, $1);
				printf("<a href=\"%s\">%s</a></td><td>%s</td><td>%s</td></tr>\n", url, $1, $4, $3);
			}
		}'
		echo '</tbody></table>'
	else
		# Fast and nice tag cloud
		echo '<h2>Tag cloud</h2><p class="tags">'
		# Some magic in tag sizes :-) It's because of non-linear distribution
		# of tags. Currently 1x198 (each of 198 tags marks one package);
		# 2x79 (each of 79 other tags marks two packages); 3x28 (and so on);
		# 4x23; 5x14; 6x5; 7x9; 8x11; 9x4; 10x3; 11x5; 12x6; 13x3; 14x1; 15x1;
		# 16x2; 18x1; 20x3; 22x3; 23, 24, 27, 33, 39, 42, 45, 57, 59, 65, 90x1.
		awk -F$'\t' -vbase="$base/~/" '
			{
				split($6, tags, " ");
				for (i in tags) { tag[tags[i]]++; if (tag[tags[i]] > max) max = tag[tags[i]]; }
			}
		END {
				for (i in tag) {
					j = tag[i];
					size = (j == 1) ? 0 : (j == 2) ? 1 : (j < 5) ? 2 : (j < 9) ? 3 : (j < 18) ? 4 : 5;
					printf("<a href=\"%s\" class=\"tag%s\">%s<sup>%s</sup></a>\n", base i, size, i, tag[i]);
				}
			}
		' $PKGS/packages-$ARCH.info | sort -f # sort alphabetically case insensitive
	fi
	echo '</p></section></div>'
	page_footer
	exit 0
fi


# show badges

if [ "$pkg" == '=' ]; then
	page_header
	echo '<div id="content2">'

	if [ -n "$cmd" ]; then
		badge="$cmd"
		cat <<-EOT
			<section>
				<h2 class="badge $badge"> Badge “$badge”</h2>

				<table>
					<thead><tr><th>Name</th><th>Description</th><th>Category</th></tr></thead>
					<tbody>
		EOT
		ls $WOK \
		| while read pkg; do
			[ -e $WOK/$pkg/.badges ] || continue
			grep -q "^${badge}$" $WOK/$pkg/.badges &&
			awk -F$'\t' -vpkg="$pkg" -vbase="$base/" '{
				if ($1 == pkg) {
					url = base $1 "/";
					gsub("+", "%2B", url);
					printf("<tr><td><img src=\"%ss/%s\" alt=\"%s\"> ", base, $1, $1);
					printf("<a href=\"%s\">%s</a></td><td>%s</td><td>%s</td></tr>\n", url, $1, $4, $3);
				}
			}' $PKGS/packages-$ARCH.info
		done
		echo '</tbody></table></section>'
	else
		layout='list' show_badges bdbroken broken any noany libtool nolibtool own ownover perm permover symlink ss fadd frem fdup old orphan patch win
	fi
	echo '</div>'
	page_footer
	exit 0
fi


case "$cmd" in
	'')
		page_header

		requested_pkg="$pkg"
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


		# Show Cooker badges
		if [ -s $wok/$pkg/.badges ]; then
			layout='table' show_badges $(cat $wok/$pkg/.badges)
		fi


		# Repology badge
		[ "$REPOLOGY" == '-' ] || cat <<-EOT
			<section>
				<h3>Repology</h3>
				<a href="https://repology.org/metapackage/${REPOLOGY:-$pkg}" target='_blank'
				rel='noopener noreferrer' title="latest packaged version(s) by Repology">
				<img src="https://repology.org/badge/latest-versions/${REPOLOGY:-$pkg}.svg" alt="latest packaged version(s)">
				<img src="https://repology.org/badge/tiny-repos/${REPOLOGY:-$pkg}.svg" alt="Packaging status">
				</a>
			</section>
			EOT


		# Show tag list
		taglist=$(
			for i in $pkg $(awk -F$'\t' -vp="$pkg" '{if ($1 == p) print $2}' $splitdb); do
				[ -s "$PKGS/packages.info" ] &&
				awk -F$'\t' -vpkg="$i" '{
					if ($1 == pkg) { print $6; exit; }
				}' "$PKGS/packages.info"
			done \
			| tr ' ' '\n' \
			| sort -u
		)
		if [ -n "$taglist" ]; then
			echo -n '<section><h3>Tags</h3><p>'
			lasttag=$(echo "$taglist" | tail -n1)
			for tag in $taglist; do
				echo -n "<a href=\"$base/~/${tag//+/%2B}\">$tag</a>"
				[ "$tag" != "$lasttag" ] && echo -n " · "
			done
			echo '</p></section>'
		fi


		# Informational table with dependencies
		pkg="$requested_pkg"
		inf="$(mktemp -d)"

		# 1/3: Build dependencies (from receipt and pkgdb)
		for i in $WANTED $BUILD_DEPENDS $(awk -F$'\t' -vp=" $pkg " '{if (index(" " $2 " ", p) && (" " $1 " " != p)) print $1}' $splitdb); do
			echo "$i" >> $inf/a
		done

		# 2/3: Runtime dependencies (from pkgdb)
		{
			[ -s "$PKGS/packages.info" ] &&
			awk -F$'\t' -vp="$pkg" '{
				if ($1 == p) print $8
			}' "$PKGS/packages.info"
		} | tr ' ' '\n' | sort -u > $inf/b

		# 3/3: Required by (from pkgdb)
		{
			for i in $pkg $(awk -F$'\t' -vp="$pkg" '{if ($1 == p) print $2}' $splitdb); do
				[ -s "$PKGS/packages.info" ] &&
				awk -F$'\t' -vp=" $i " '{
					if (index(" " $8 " ", p)) print $1
				}' "$PKGS/packages.info"

				[ -s "$PKGS/bdeps.txt" ] &&
				awk -F$'\t' -vp=" $i " '{
					if (index(" " $2 " ", p)) print $1
				}' $PKGS/bdeps.txt
			done
		} | sort -u > $inf/c

		cat <<-EOT
			<section>
				<h3>Related packages</h3>
				<table class="third">
					<thead>
						<tr>
							<th>Build dependencies</th>
							<th>Runtime dependencies</th>
							<th>Required by</th>
						</tr>
					</thead>
					<tbody>
		EOT

		awk -vinf="$inf" -vbase="$base" '
			function linki(i) {
				if (i) return sprintf("<img src=\"%s/s/%s\" alt=\"%s\"> <a href=\"%s/%s\">%s</a>", base, i, i, base, i, i);
			}
			BEGIN{
				do {
					a = b = c = "";
					getline a < inf "/a";
					getline b < inf "/b";
					getline c < inf "/c";
					printf("<tr><td>%s </td><td>%s </td><td>%s </td></tr>", linki(a), linki(b), linki(c));
				} while ( a b c )
			}'
		cat <<-EOT
					</tbody>
				</table>
			</section>
		EOT
		# Clean
		rm -r $inf




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
				*/patches/series)    class="bash";;
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
					echo "<img src='$base/$pkg/browse/stuff/$arg' style='display: block; max-width: 100%; margin: auto' alt=''/>"
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

		# find main package
		wanted=$(. $wok/$pkg/receipt; echo $WANTED)
		main=${wanted:-$pkg}
		devpkg=''; [ -d "$wok/$main-dev" ] && devpkg="$main-dev"

		splitsets=$(echo $SPLIT" " \
			| awk '
				BEGIN { RS = " "; FS = ":"; }
				{ print $2; }' \
			| sort -u \
			| tr '\n' ' ' \
			| sed 's|^ *||; s| *$||')

		splitpkgs=$(echo $SPLIT" " \
			| awk '
				BEGIN { RS = " "; FS = ":"; }
				{ print $1; }' \
			| tr '\n' ' ' \
			| sed 's|^ *||; s| *$||')

		# we need the version
		if [ -f "$WOK/linux/receipt" ]; then
			kvers=$(. $WOK/linux/receipt; echo $VERSION)
			kbasevers=$(echo $kvers | cut -d. -f1,2)
		elif [ -f "$INSTALLED/linux-api-headers/receipt" ]; then
			kvers=$(. $INSTALLED/linux-api-headers/receipt; echo $VERSION)
			kbasevers=$(echo $kvers | cut -d. -f1,2)
		fi
		ver=$(. $wok/$main/receipt; echo $VERSION$EXTRAVERSION)

		echo "<section><h3>Quick jump:</h3>"


		for part in head body; do

			for set in '' $splitsets; do
				pkgsofset=$(echo $SPLIT" " \
					| awk -vset="$set" -vmain="$main" -vdev="$devpkg" '
						BEGIN {
							RS = " "; FS = ":";
							if (!set) print main;
							if (!set && dev) print dev;
						}
						{
							if ($2 == set) print $1;
						}' \
					| sort -u)

				set_description=''
				[ -n "$splitsets" ] &&
				case "$set" in
					'')
						set_description=' (default set)'
						set_title='Default set'
						;;
					*)
						set_description=" (set “$set”)"
						set_title="Set “$set”"
						;;
				esac

				install="$wok/$main/install"
				[ -n "$set" ] && install="$install-$set"

				case $part in
					head)
						[ -n "$splitsets" ] &&
						case "$set" in
							'') echo "<ul><li>Default set:";;
							*)  echo "<li>Set “$set”:";;
						esac
						echo -e '\t<ul>'
						echo "$pkgsofset" | sed 'p' | xargs printf "\t\t<li><a href='#%s'>%s</a></li>\n"
						cat <<-EOT
							<li id='li-repeats$set' style='display:none'>
								<a href='#repeats$set'>repeatedly packaged files</a></li>
							<li id='li-empty$set' style='display:none'>
								<a href='#empty$set'>unpackaged empty folders</a></li>
							<li id='li-outoftree$set' style='display:none'>
								<a href='#outoftree$set'>out-of-tree files</a></li>
							<li id='li-orphans$set' style='display:none'>
								<a href='#orphans$set'>unpackaged files</a>
								<span id='orphansTypes$set'></span></li>
						EOT
						echo -e '\t</ul>'
						[ -n "$splitsets" ] && echo "</li>"
						;;
					body)
						all_files=$(mktemp)
						cd $install; find ! -type d | sed 's|\.||' > $all_files

						# ------------------------------------------------------
						# Packages content
						# ------------------------------------------------------
						packaged=$(mktemp)
						for p in $pkgsofset; do
							namever="$(awk -F$'\t' -vp="$p" '{
								if ($1==p) {printf("%s-%s\n", $1, $2); exit}
								}' $PKGS/packages-$ARCH.info)"
							if [ -d "$wok/$p/taz/$p-$ver" ]; then
								indir=$p
							elif [ -d "$wok/$main/taz/$p-$ver" ]; then
								indir=$main
							fi
							dir="$wok/$indir/taz/$p-$ver/fs"

							size=$(du -hs $dir | awk '{ sub(/\.0/, ""); print $1 }')

							echo
							echo "<section id='$p'>"
							echo "	<h3>Contents of package “$namever” (${size:-empty}):</h3>"
							echo '	<pre class="files">'
							if [ -s "$wok/$indir/taz/$p-$ver/files.list" ]; then
								echo -en '<span class="underline">permissions·lnk·user    ·group   ·     size·date &amp; time ·name\n</span>'
								cd $dir
								find . -print0 \
								| sort -z \
								| xargs -0 ls -ldp --color=always \
								| syntax_highlighter files \
								| sed "s|\([^>]*\)>\.\([^<]*\)\(<.*\)$|\1 href='$base/$indir/browse/taz/$p-$ver/fs\2'>\2\3|;" \
								| awk 'BEGIN { FS="\""; }
									{ gsub("+", "%2B", $2); print; }'
							else
								echo 'No files'
							fi
							echo '</pre>'
							echo '</section>'

							cat $wok/$indir/taz/$p-$ver/files.list >> $packaged
						done
						# ------------------------------------------------------
						# /Packages content
						# ------------------------------------------------------

						# ------------------------------------------------------
						# Repeatedly packaged files
						# ------------------------------------------------------
						repeats=$(mktemp)
						sort $packaged | uniq -d > $repeats
						if [ -s "$repeats" ]; then
							cat <<-EOT

								<script>document.getElementById('li-repeats$set').style.display = 'list-item'</script>
								<section id='repeats$set'>
									<h3>Repeatedly packaged files$set_description:</h3>
							EOT
							cd $install

							IFS=$'\n'
							echo -n '	<pre class="files">'
							echo -en '<span class="underline">permissions·lnk·user    ·group   ·     size·date &amp; time ·name\n</span>'
							while read i; do
								find .$i -exec ls -ldp --color=always '{}' \; \
								| syntax_highlighter files \
								| sed 's|>\./|>/|'
							done < $repeats
							cat <<-EOT
								</pre>
								</section>
							EOT
							unset IFS
						fi
						rm $repeats
						# ------------------------------------------------------
						# /Repeatedly packaged files
						# ------------------------------------------------------

						# ------------------------------------------------------
						# Unpackaged empty folders
						# ------------------------------------------------------
						emptydirs=$(mktemp)
						cd $install
						IFS=$'\n'
						find -type d \
						| sed 's|\.||' \
						| while read d; do
							[ -z "$(ls "$install$d")" ] || continue
							# empty dir determined by empty `ls`
							echo $d
						done \
						| while read d; do
							notfound='yes'
							for p in $(cd $wok/$main/taz; ls); do
								if [ -d "$wok/$main/taz/$p/fs$d" ]; then
									notfound=''
									break
								fi
							done
							[ -n "$notfound" ] &&
							ls -ldp --color=always .$d \
							| syntax_highlighter files \
							| sed 's|>\./|>/|'
						done > $emptydirs
						unset IFS
						if [ -s "$emptydirs" ]; then
							cat <<-EOT

								<script>document.getElementById('li-empty$set').style.display = 'list-item'</script>
								<section id='empty$set'>
									<h3>Unpackaged empty folders$set_description:</h3>
							EOT
							echo -n '	<pre class="files">'
							echo -en '<span class="underline">permissions·lnk·user    ·group   ·     size·date &amp; time ·name\n</span>'
							cat $emptydirs
							cat <<-EOT
								</pre>
								</section>
							EOT
						fi
						rm $emptydirs
						# ------------------------------------------------------
						# /Unpackaged empty folders
						# ------------------------------------------------------

						# ------------------------------------------------------
						# Out-of-tree files
						# ------------------------------------------------------
						outoftree=$(mktemp)
						awk -F$'\n' -vall="$all_files" '
							{
								if (FILENAME == all) files_all[$1] = "1";
								else                 files_pkg[$1] = "1";
							}
							END {
								for (i in files_pkg) {
									if (! files_all[i]) print i;
								}
							}
						' "$all_files" "$packaged" > $outoftree

						if [ -d "$install" -a -s "$outoftree" ]; then
							echo
							echo "<script>document.getElementById('li-outoftree$set').style.display = 'list-item'</script>"
							echo "<section id='outoftree$set'>"
							echo "	<h3>Out-of-tree files$set_description:</h3>"
							echo -n '	<pre class="files">'
							echo -en '<span class="underline">permissions·lnk·user    ·group   ·     size·date &amp; time ·name\n</span>'
							IFS=$'\n'
							while read outoftree_line; do
								# Find the package out-of-tree file belongs to
								for i in $pkgsofset; do
									if grep -q "^$outoftree_line$" $wok/$main/taz/$i-$ver/files.list; then
										cd $wok/$main/taz/$i-$ver/fs
										ls -ldp --color=always ".$outoftree_line" \
										| syntax_highlighter files \
										| sed "s|\([^>]*\)>\.\([^<]*\)\(<.*\)$|\1 href='$base/$main/browse/taz/$i-$ver/fs\2'>\2\3|;" \
										| awk 'BEGIN { FS="\""; }
											{ gsub("+", "%2B", $2); print; }'
									fi
								done
							done < $outoftree
							unset IFS
							echo '</pre>'
							echo '</section>'
						fi
						rm $outoftree
						# ------------------------------------------------------
						# /Out-of-tree files
						# ------------------------------------------------------

						# ------------------------------------------------------
						# Unpackaged files
						# ------------------------------------------------------
						orphans=$(mktemp)
						awk -F$'\n' -vall="$all_files" '
							{
								if (FILENAME == all) files_all[$1] = "1";
								else                 files_pkg[$1] = "1";
							}
							END {
								for (i in files_all) {
									if (! files_pkg[i]) print i;
								}
							}
						' "$all_files" "$packaged" | sort > $orphans
						if [ -d "$install" -a -s "$orphans" ]; then
							echo
							echo "<script>document.getElementById('li-orphans$set').style.display = 'list-item'</script>"
							echo "<section id='orphans$set'>"
							echo "	<h3>Unpackaged files$set_description:</h3>"
							table=$(mktemp)
							awk '
							function tag(text, color) {
								printf("<span class=\"c%s1\">%s</span> ", color, text);
								printf("%s\n", $0);
							}
							/\/perllocal\.pod$/ || /\/\.packlist$/ ||
								/\/share\/bash-completion\// || /\/etc\/bash_completion\.d\// ||
								/\/lib\/systemd\// || /\.pyc$/ || /\.pyo$/ ||
								/\/fonts\.scale$/ || /\/fonts\.dir$/ || /\.la$/ ||
								/\/cache\/.*\.gem$/ {
								tag("---", 0); next }
							/\.pod$/  { tag("pod", 5); next }
							/\/share\/man\// { tag("man", 5); next }
							/\/share\/doc\// || /\/share\/gtk-doc\// || /\/share\/info\// ||
								/\/share\/devhelp\// { tag("doc", 5); next }
							/\/share\/icons\// { tag("ico", 2); next }
							/\/share\/locale\// { tag("loc", 4); next }
							/\.h$/ || /\.a$/ || /\.pc$/ || /\/bin\/.*-config$/ ||
								/\/Makefile.*$/ { tag("dev", 3); next }
							/\/share\/help\// || /\/share\/appdata\// ||
							/\/share\/metainfo\// || /\/share\/application-registry\// ||
							/\/share\/mime-info\// || /\/share\/gnome\/help\// || /\/share\/omf\// {
								tag("gnm", 6); next }
							{ tag("???", 1) }
							' "$orphans" > $table

							# Summary table
							orphans_types='()'
							for i in head body; do
								case $i in
									head) echo -n '<table class="summary"><tr>';;
									body) echo -n '<th> </th></tr><tr>';;
								esac
								for j in '???1' dev3 loc4 ico2 doc5 man5 pod5 gnm6 '---0'; do
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
							echo "<script>document.getElementById('orphansTypes$set').innerText = '${orphans_types// /, }';</script>"

							suffix=''; [ -n "$set" ] && suffix="-$set"
							echo -n '	<pre class="files">'
							echo -en '<span class="underline">tag·permissions·lnk·user    ·group   ·     size·date &amp; time ·name\n</span>'
							IFS=$'\n'
							while read orphan_line; do
								echo -n "${orphan_line/span> */span>} "
								cd $install
								ls -ldp --color=always ".${orphan_line#*</span> }" \
								| syntax_highlighter files \
								| sed "s|\([^>]*\)>\.\([^<]*\)\(<.*\)$|\1 href='$base/$main/browse/install$suffix\2'>\2\3|;" \
								| awk 'BEGIN { FS="\""; }
									{ gsub("+", "%2B", $2); print; }'
							done < $table
							unset IFS
							echo '</pre>'
							echo '</section>'
							rm $table
						fi
						rm $orphans
						# ------------------------------------------------------
						# /Unpackaged files
						# ------------------------------------------------------

						rm $all_files $packaged
						;;
				esac
			done # /set

			case "$part" in
				head)
					[ -n "$splitsets" ] && echo "</ul>"
					echo "</section>"
					;;
			esac
		done # /part

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
		sed -e "/(pkg\/local$theme):/ s|: \([^<]*\)|<img src='$base/i/$blog/\1' alt=''> \1|" | \
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

		dir="wok/$pkg/install/usr/share/$cmd/"; dir2=''
		if [ "$cmd" == 'doc' ]; then
			dir2="wok/$pkg/install/usr/share/gtk-doc/"
			subdirs="$(ls -p $dir | sed '/\/$/!d')"
			[ $(echo "$subdirs" | wc -l) -eq 1 ] && dir="$dir$subdirs"
			if [ -z "$arg" ]; then
				try=$(for i in $dir $dir2; do find $i -name 'index.htm*'; done | sed q)
				[ -n "$try" ] && arg="$try"
			fi
		fi

		while read i; do
			[ -s "$i" ] || continue
			case "$i" in
				*.jp*g|*.png|*.gif|*.svg|*.css) continue
			esac
			i=${i#$dir}; i=${i#$dir2}
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
					echo "<a class='button$class' href='$base/$pkg/doc/$i'>$i</a>"
					;;
				info)
					info=$(basename $i)
					echo "<a class='button$class' href='$base/$pkg/info/$i#Top'>${info/.info/}</a>"
					;;
			esac
		done <<EOT
$(for i in $dir $dir2; do find $i -type f; done | sort)
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
						*.rb|*/Rakefile*|*/Gemfile*) class='ruby';;
						*.rdoc)     class='asciidoc';;
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
							cat <<-EOT
								<object id="idoc" data="$page" width="100%" height="100%" type="application/pdf" style="min-height: 600px">
									$(show_note w "Missing PDF plugin.<br/>Get the file <a href="$page">$(basename "$page")</a>.")
								</object>
							EOT
							;;
						*.md|*.markdown)
							echo '<section class="markdown">'
							$md2html "$tmp" | sed 's|class="|class="language-|g'
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

					html=$(./man2html.bin "$tmp" | sed -e '1,/<header>/d' -e '/<footer>/,$d' \
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
			show_note e "File “$arg” does not exist!"
		fi
		;;

	download)
		page_header
		pkg_info
		show=0

		. $wok/$pkg/receipt

		if [ -n "$TARBALL" -a -s "$SRC/$TARBALL" ]; then
			files_header
			echo "<tr><td><a href='$base/src/$TARBALL' class='icon tarball'>$TARBALL</a></td>"
			ls -lh "$SRC/$TARBALL" | awk '{printf("<td>%sB</td>", $5)}'
			echo "<td>Sources for building the package “$pkg”</td></tr>"
			show=1
		fi

		if [ -d "$wok/$pkg/taz" ]; then
			[ "$show" -eq 1 ] || files_header

			common_version=$VERSION
			for i in $(all_names | tr ' ' '\n' | sort); do
				[ -e "$wok/$pkg/taz/$i-$common_version$EXTRAVERSION/receipt" ] || continue
				. $wok/$pkg/taz/$i-$common_version$EXTRAVERSION/receipt

				for filename in "$PACKAGE-$VERSION$EXTRAVERSION.tazpkg" "$PACKAGE-$VERSION$EXTRAVERSION-$ARCH.tazpkg" "$PACKAGE-$VERSION$EXTRAVERSION-any.tazpkg"; do
					[ -f "$PKGS/$filename" ] || continue

					case $filename in
						*-x86_64.tazpkg) class='pkg64';;
						*-any.tazpkg)    class='pkgany';;
						*)               class='pkg32';;
					esac
					cat <<-EOT
						<tr>
							<td><a href="$base/get/$filename" class='icon $class'>$filename</a></td>
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
