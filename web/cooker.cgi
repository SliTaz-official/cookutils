#!/bin/sh
#
# SliTaz Cooker CGI/web interface.
#
echo "Content-Type: text/html"
echo ""

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

#
# Functions
#

# Put some colors in log and DB files.
syntax_highlighter() {
	sed -e 's#OK$#<span class="span-ok">OK</span>#g' \
		-e 's#yes$#<span class="span-ok">yes</span>#g' \
		-e 's#no$#<span class="span-no">no</span>#g' \
		-e 's#error$#<span class="span-error">error</span>#g' \
		-e 's#ERROR:#<span class="span-error">ERROR:</span>#g' \
		-e s"#^Executing:\([^']*\).#<span class='span-sky'>\0</span>#"g \
		-e s"#^====\([^']*\).#<span class='span-line'>\0</span>#"g \
		-e s"#http://\([^']*\).*#<a href='\0'>\1</a>#"g	
}

# Latest build pkgs.
list_packages() {
	cd $PKGS
	ls -1t *.tazpkg | head -20 | \
	while read file
	do
		echo -n $(stat -c '%y' $PKGS/$file | cut -d . -f 1 | sed s/:[0-9]*$//)
		echo " : $file"
	done
}

# xHTML header
cat << EOT
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
	<title>SliTaz Cooker</title>
	<meta charset="utf-8" />
	<link rel="stylesheet" type="text/css" href="style.css" />
</head>
<body>

<div id="header">
	<h1><a href="cooker.cgi">SliTaz Cooker</a></h1>
</div>

<!-- Content -->
<div id="content">
EOT

#
# Load requested page
#

case "${QUERY_STRING}" in
	log=*)
		pkg=${QUERY_STRING#log=}
		if [ -f "$LOGS/$pkg.log" ]; then
			echo "<h2>Log for: $pkg</h2>"
			if fgrep -q "Summary " $LOGS/$pkg.log; then
				echo '<pre>'
				grep -A 8 "^Summary " $LOGS/$pkg.log | sed /^$/d | \
					syntax_highlighter
				echo '</pre>'
				echo '<pre>'
				cat $LOGS/$pkg.log | syntax_highlighter
				echo '</pre>'
			else
				if fgrep -q "cook:$pkg$" $command; then
					echo "<pre>The Cooker is currently cooking: $pkg</pre>"
				fi
				echo '<pre>' && cat $LOGS/$pkg.log | syntax_highlighter
				echo '</pre>'
			fi
		else
			echo "<pre>No log file found for: $pkg</pre>"
		fi ;;
	*)
		cat << EOT
<div style="float: right;">
	<form method="get" action="$SCRIPT_NAME">
		Show log:
		<input type="text" name="log" />
	</form>
</div>

<h2>Summary</h2>
<pre>
Cooked packages  : $(ls $PKGS/*.tazpkg | wc -l)
Packages in wok  : $(ls $WOK | wc -l)
Wok revision     : <a href="http://hg.slitaz.org/wok">$(cd $WOK && hg head --template '{rev}\n')</a>
Commits to cook  : $(cat $commits | wc -l)
Broken packages  : $(cat $broken | wc -l)
</pre>

<div>
Latest logs: <a href="cooker.cgi?log=cookorder">cookorder</a>
<a href="cooker.cgi?log=commits">commits</a>
</div>

<h2>Activity</h2>
<pre>
$(tac $CACHE/activity | sed s"#^\([^']* : \)#<span class='span-date'>\0</span>#"g)
</pre>

<h2>Commits</h2>
<pre>
$(cat $commits)
</pre>

<h2>Broken</h2>
<pre>
$(cat $broken | sed s"#^[^']*#<a href='cooker.cgi?log=\0'>\0</a>#"g)
</pre>

<h2>Bloked</h2>
<pre>
$(cat $blocked | sed s"#^[^']*#<a href='cooker.cgi?log=\0'>\0</a>#"g)
</pre>

<h2>Latest cook</h2>
<pre>
$(list_packages | sed s"#^\([^']* \)#<span class='span-date'>\0</span>#"g)
</pre>
EOT
	;;
esac

# Close xHTML page
cat << EOT
</div>

<div id="footer">
	<a href="cooker.cgi">SliTaz Cooker</a>
</div>

</body>
</html>
EOT

exit 0
