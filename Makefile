# Makefile for SliTaz Cooker.
#

PREFIX?=/usr
DESTDIR?=

all:

install: install-cook install-libcook install-cross
uninstall: uninstall-cook uninstall-libcook uninstall-cross

# Cook

install-cook:
	install -m 0755 -d $(DESTDIR)/etc/slitaz
	install -m 0755 -d $(DESTDIR)/etc/init.d
	install -m 0755 -d $(DESTDIR)$(PREFIX)/bin
	install -m 0755 -d $(DESTDIR)/var/www/cgi-bin/cooker
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/applications
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/cook/cooktest
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0755 cook $(DESTDIR)$(PREFIX)/bin
	install -m 0755 cooker $(DESTDIR)$(PREFIX)/bin
	install -m 0755 cookiso $(DESTDIR)$(PREFIX)/bin
	install -m 0644 cook.conf $(DESTDIR)/etc/slitaz
	install -m 0644 cook.site $(DESTDIR)/etc/slitaz
	install -m 0644 web/* $(DESTDIR)/var/www/cgi-bin/cooker
	install -m 0644 data/*.desktop $(DESTDIR)$(PREFIX)/share/applications
	install -m 0644 data/cooklist $(DESTDIR)$(PREFIX)/share/cook
	install -m 0644 data/receipt $(DESTDIR)$(PREFIX)/share/cook
	install -m 0644 data/cooktest/* $(DESTDIR)$(PREFIX)/share/cook/cooktest
	install -m 0644 doc/* $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0644 README $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0755 init.d/cooker $(DESTDIR)/etc/init.d
	chmod 0755 $(DESTDIR)/var/www/cgi-bin/cooker/*.cgi

uninstall-cook:
	rm -rf \
		$(DESTDIR)$(PREFIX)/bin/cook \
		$(DESTDIR)$(PREFIX)/bin/cooker \
		$(DESTDIR)/etc/slitaz/cook.* \
		$(DESTDIR)/var/www/cooker

# Libcook

install-libcook:
	install -m 0755 -d $(DESTDIR)$(PREFIX)/lib/slitaz
	install -m 0755 lib/libcook.sh $(DESTDIR)$(PREFIX)/lib/slitaz
	install -m 0755 lib/libcookorder.sh $(DESTDIR)$(PREFIX)/lib/slitaz

uninstall-libcook:
	rm -f $(DESTDIR)$(PREFIX)/lib/slitaz/libcook.sh
	rm -f $(DESTDIR)$(PREFIX)/lib/slitaz/libcookorder.sh
# Cross

install-cross:
	install -m 0755 -d $(DESTDIR)/etc/slitaz
	install -m 0755 -d $(DESTDIR)$(PREFIX)/bin
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0755 cross $(DESTDIR)$(PREFIX)/bin
	install -m 0644 cross.conf $(DESTDIR)/etc/slitaz
	install -m 0644 doc/cross.txt $(DESTDIR)$(PREFIX)/share/doc/cookutils

uninstall-cross:
	rm -rf \
		$(DESTDIR)$(PREFIX)/bin/cross \
		$(DESTDIR)/etc/slitaz/cross.conf \
		$(DESTDIR)$(PREFIX)/share/doc/cookutils/cross.txt
