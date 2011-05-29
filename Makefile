# Makefile for SliTaz Cooker.
#

PREFIX?=/usr
DESTDIR?=

all:

install:
	install -m 0777 -d $(DESTDIR)/etc/slitaz
	install -m 0777 -d $(DESTDIR)$(PREFIX)/bin
	install -m 0777 -d $(DESTDIR)/var/www/cgi-bin/cooker
	install -m 0777 -d $(DESTDIR)$(PREFIX)/share/applications
	install -m 0777 -d $(DESTDIR)$(PREFIX)/share/cook
	install -m 0777 -d $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0777 cook $(DESTDIR)$(PREFIX)/bin
	install -m 0777 cooker $(DESTDIR)$(PREFIX)/bin
	install -m 0644 cook.conf $(DESTDIR)/etc/slitaz
	install -m 0644 cook.site $(DESTDIR)/etc/slitaz
	install -m 0644 web/* $(DESTDIR)/var/www/cgi-bin/cooker
	cp -r data/*.desktop $(DESTDIR)$(PREFIX)/share/applications
	cp -r data/* $(DESTDIR)$(PREFIX)/share/cook
	rm $(DESTDIR)$(PREFIX)/share/cook/*.desktop
	cp -r doc/* $(DESTDIR)$(PREFIX)/share/doc/cookutils
	cp -r README $(DESTDIR)$(PREFIX)/share/doc/cookutils
	cp -r init.d $(DESTDIR)/etc

uninstall:
	rm -rf \
		$(DESTDIR)$(PREFIX)/bin/cook \
		$(DESTDIR)$(PREFIX)/bin/cooker \
		$(DESTDIR)/etc/slitaz/cook.* \
		$(DESTDIR)/var/www/cgi-bin/cooker
