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
		-e s"#ftp://\([^']*\).*#<a href='\0'>\0</a>#"g	\
		-e s"#http://\([^']*\).*#<a href='\0'>\0</a>#"g \
		-e s"#^\#\([^']*\)#<span class='sh-comment'>\0</span>#"g 
		#-e s"#\"\([^']*\)\"#<span class='sh-val'>\0</span>#"g
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
	pkg=*)
		pkg=${QUERY_STRING#pkg=}
		log=$LOGS/$pkg.log
		echo "<h2>Package: $pkg</h2>"

		# Package info
		if [ -f "$wok/$pkg/receipt" ]; then
			. $wok/$pkg/receipt
			tazpkg=$PKGS/$pkg-${VERSION}.tazpkg
			if [ -f "$tazpkg" ]; then
				
				cooked=$(stat -c '%y' $tazpkg | cut -d . -f 1 | sed s/:[0-9]*$//)
				echo $cooked
			fi
			echo "<a href='cooker.cgi?receipt=$pkg'>receipt</a>"
		else
			echo "<p>No package named: $pkg<p>"
		fi

		# Check for a log file and display summary if exist.
		if [ -f "$log" ]; then
			if fgrep -q "Summary " $LOGS/$pkg.log; then
				if fgrep -q "cook:$pkg$" $command; then
					echo "<pre>The Cooker is currently cooking: $pkg</pre>"
				else
					echo "<h3>Cook summary</h3>"
					echo '<pre>'
					grep -A 8 "^Summary " $LOGS/$pkg.log | sed /^$/d | \
						syntax_highlighter
					echo '</pre>'
				fi
			fi
			if fgrep -q "ERROR:" $LOGS/$pkg.log; then
				fgrep "ERROR:" $LOGS/$pkg.log
			fi
			echo "<h3>Cook log</h3>"
			echo '<pre>'
			cat $log | syntax_highlighter
			echo '</pre>'
		else
			echo "<pre>No log: $pkg</pre>"
		fi ;;
	log=*)
		log=${QUERY_STRING#log=}
		file=$LOGS/$log.log
		echo "<h2>Log for: $log</h2>"
		if [ -f "$LOGS/$log.log" ]; then
			echo '<pre>'
			cat $file | syntax_highlighter
			echo '</pre>'
		else
			echo "<pre>No log for: $log</pre>"
		fi ;;
	receipt=*)
		pkg=${QUERY_STRING#receipt=}
		echo "<h2>Receipt: $pkg</h2>"
		if [ -f "$wok/$pkg/receipt" ]; then
			echo '<pre>'
			cat $wok/$pkg/receipt | syntax_highlighter
			echo '</pre>'
		else
			echo "<pre>No receipt for: $log</pre>"
		fi ;;
	*)
		cat << EOT
<div style="float: right;">
	<form method="get" action="$SCRIPT_NAME">
		Package:
		<input type="text" name="pkg" />
	</form>
</div>

<h2>Summary</h2>
<pre>
Running command  : $([ -s "$command" ] && cat $command || echo "Not running")
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
$(tac $CACHE/activity | sed s"#^\([^']* : \)#<span class='log-date'>\0</span>#"g)
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
