<meta charset="UTF-8">

index.cgi readme
================

This CGI script is intended to be used on the Lighttpd powered SliTaz web
server. The configuration uses the modules:

  * mod_rewrite:  to have cacheable, reusable, human friendly URIs
  * mod_compress: to save traffic

Examples of human friendly URIs:

  * /busybox                   : the page contains all about busybox package
  * /busybox/receipt           : the page with the busybox's receipt
  * /busybox/files             : the page with the file listing
  * /busybox/file/bin/busybox  : get the specified file
  * /get/busybox-1.26.2.tazpkg : get the specified package

Example of traffic saving:

  * glibc.log in plain form:      8.3 MB
  * glibc.log in compressed form: 0.3 MB (3% of the original size)


Notes about logs
----------------

Single resource should be associated with the discrete URI. But due to log
rotation, glibc.log.2 become glibc.log.3 after package rebuilding. In such
situation:

  1. we can't point to the specified log and line within it (URI changed);
  2. caching will fail, already cached log change the name.

The solution implemented is virtually append log name with the UNIX timestamp
of last modification of the log instead of sequental numbers. So, for example,
'glibc.log.2' will virtually became 'glibc.log.1482699768'. To found the matched
log we need to cycle among ten or less 'glibc.log*' physical files and compare
the files modification date with date in question.


Full list of implemented human friendly URIs
--------------------------------------------

URI syntax             | Description                            | URI example
-----------------------|----------------------------------------|-----------------------
/                      | cooker home page                       | /
/‹pkg›                 | brief info about ‹pkg›                 | /busybox
/‹pkg›/receipt         | display ‹pkg› receipt                  | /busybox/receipt
/‹pkg›/description     | display ‹pkg› description              | /busybox/description
/‹pkg›/stuff/‹stuff›   | display ‹stuff› file                   | /busybox/stuff/www/httpd/404.html
/‹pkg›/files           | display ‹pkg› files list               | /busybox/files
/‹pkg›/file/‹file›     | get the ‹file› from the ‹pkg›          | /busybox/file/bin/busybox
/get/‹package.tazpkg›  | get the specified ‹package.tazpkg›     | /get/busybox-1.26.2.tazpkg
/src/‹tarball›         | get the specified sources ‹tarball›    | /src/busybox-1.26.2.tar.bz2
/‹pkg›/man             | list of man pages, display default one | /cmark/man
/‹pkg›/man/‹page›      | display specified man ‹page›           | /cmark/man/cmark.1
.                      | .                                      | /man-db/man/es/mandb.8
/‹pkg›/doc             | list of existing documentation files   | .
/‹pkg›/doc/‹doc›       | display specified documentation file   | .
/‹pkg›/info            | list of existing info files            | .
/‹pkg›/info/‹info›     | display specified info file            | .
/‹pkg›/log             | display the latest cooking log         | /busybox/log
/‹pkg›/log/‹timestamp› | display the specified cooking log      | /busybox/log/1482700678


((unfinished))
