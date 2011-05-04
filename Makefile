# Makefile for SliTaz Cooker.
#

PREFIX?=/usr
DESTDIR?=

all:

install:
	install -m 0777 cook $(DESTDIR)$(PREFIX)/bin
	install -m 0777 cooker $(DESTDIR)$(PREFIX)/bin
	install -m 0644 cook.conf $(DESTDIR)/etc/slitaz
	install -m 0644 cook.site $(DESTDIR)/etc/slitaz
	install -m 0777 -d $(DESTDIR)/var/www/cooker
	install -m 0777 -d $(DESTDIR)$(PREFIX)/share/cook
	install -m 0644 web/* $(DESTDIR)/var/www/cooker
	cp -r data/* $(DESTDIR)$(PREFIX)/share/cook

uninstall:
	rm -f \
		$(DESTDIR)$(PREFIX)/bin/cook \
		$(DESTDIR)$(PREFIX)/bin/cooker \
		$(DESTDIR)/etc/slitaz/cook*.* \
		$(DESTDIR)/var/www/cooker
