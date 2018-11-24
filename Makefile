# Makefile for SliTaz Cooker.
#

PREFIX  ?= /usr
DESTDIR ?=
LINGUAS ?= fr ja pt_BR ru zh_CN zh_TW
VERSION := $(shell grep ^VERSION cook | cut -d'=' -f2)

all:

install: install-cook install-libcook install-cross
uninstall: uninstall-cook uninstall-libcook uninstall-cross

# Cook

install-cook:
	install -m 0755 -d $(DESTDIR)/etc/slitaz
	install -m 0755 -d $(DESTDIR)/etc/init.d
	install -m 0755 -d $(DESTDIR)/bin
	install -m 0755 -d $(DESTDIR)$(PREFIX)/bin
	install -m 0755 -d $(DESTDIR)$(PREFIX)/libexec/cookutils
	install -m 0755 -d $(DESTDIR)/var/www/cgi-bin/cooker
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/applications
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/cook/cooktest
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0755 uname            $(DESTDIR)/bin
	install -m 0755 cook             $(DESTDIR)$(PREFIX)/bin
	install -m 0755 cooks            $(DESTDIR)$(PREFIX)/bin
	install -m 0755 fix-desktop-file $(DESTDIR)$(PREFIX)/bin
	install -m 0755 cooker           $(DESTDIR)$(PREFIX)/bin
	install -m 0755 cookiso          $(DESTDIR)$(PREFIX)/bin
	install -m 0755 cooklinux        $(DESTDIR)$(PREFIX)/bin
	install -m 0755 modules/pkgdb \
					modules/compressor \
					modules/deps \
					modules/mk_pkg_receipt \
					modules/pack \
					modules/precheck \
					modules/postcheck \
					modules/langdesc \
									 $(DESTDIR)$(PREFIX)/libexec/cookutils
	install -m 0644 cook.conf        $(DESTDIR)/etc/slitaz
	install -m 0644 cook.site        $(DESTDIR)/etc/slitaz
	install -m 0644 web/*            $(DESTDIR)/var/www/cgi-bin/cooker
	install -m 0644 data/*.desktop   $(DESTDIR)$(PREFIX)/share/applications
	install -m 0644 data/cooklist    $(DESTDIR)$(PREFIX)/share/cook
	install -m 0644 data/receipt     $(DESTDIR)$(PREFIX)/share/cook
	install -m 0644 data/cooktest/*  $(DESTDIR)$(PREFIX)/share/cook/cooktest
	install -m 0644 doc/*            $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0644 README           $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0755 init.d/cooker    $(DESTDIR)/etc/init.d
	chmod 0755 $(DESTDIR)/var/www/cgi-bin/cooker/*.cgi
	sed -i "s|@@PREFIX@@|$(PREFIX)|g" \
		$(DESTDIR)$(PREFIX)/bin/cook \
		$(DESTDIR)$(PREFIX)/libexec/cookutils/pack

uninstall-cook:
	rm -rf \
		$(DESTDIR)/bin/uname \
		$(DESTDIR)$(PREFIX)/bin/cook \
		$(DESTDIR)$(PREFIX)/bin/cooks \
		$(DESTDIR)$(PREFIX)/bin/fix-desktop-file \
		$(DESTDIR)$(PREFIX)/bin/cooker \
		$(DESTDIR)$(PREFIX)/bin/cookiso \
		$(DESTDIR)$(PREFIX)/bin/cooklinux \
		$(DESTDIR)$(PREFIX)/libexec/cookutils \
		$(DESTDIR)$(PREFIX)/share/cook \
		$(DESTDIR)/etc/slitaz/cook.* \
		$(DESTDIR)/var/www/cooker

# Libcook

install-libcook:
	install -m 0755 -d $(DESTDIR)$(PREFIX)/lib/slitaz
	install -m 0755 lib/libcook.sh $(DESTDIR)$(PREFIX)/lib/slitaz

uninstall-libcook:
	rm -f $(DESTDIR)$(PREFIX)/lib/slitaz/libcook.sh

# Cross

install-cross:
	install -m 0755 -d $(DESTDIR)$(PREFIX)/bin
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/cross
	install -m 0755 -d $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0755 cross             $(DESTDIR)$(PREFIX)/bin
	install -m 0644 doc/cross.txt     $(DESTDIR)$(PREFIX)/share/doc/cookutils
	install -m 0644 data/cross-*.conf $(DESTDIR)$(PREFIX)/share/cross

uninstall-cross:
	rm -rf \
		$(DESTDIR)$(PREFIX)/bin/cross \
		$(DESTDIR)$(PREFIX)/share/cross \
		$(DESTDIR)$(PREFIX)/share/doc/cookutils/cross.txt

# i18n

pot:
	xgettext -o po/cook.pot -kaction -ktitle -k_ -k_n -k_p:1,2 -L Shell -cL10n \
		--copyright-holder="SliTaz Association" \
		--package-name="Cook" \
		--package-version="$(VERSION)" \
		./cook ./modules.pkgdb

msgmerge:
	@for l in $(LINGUAS); do \
		echo -n "Updating $$l po file."; \
		msgmerge -U po/$$l.po po/cook.pot; \
	done;

msgfmt:
	@for l in $(LINGUAS); do \
		echo "Compiling $$l mo file..."; \
		mkdir -p po/mo/$$l/LC_MESSAGES; \
		msgfmt -o po/mo/$$l/LC_MESSAGES/cook.mo po/$$l.po; \
	done;

# Clean source

clean:
	rm -rf po/mo
	rm -f po/*.mo
	rm -f po/*.*~

help:
	@echo "make"
	@echo "    install         | uninstall         - all"
	@echo "    install-cook    | uninstall-cook    - cook"
	@echo "    install-libcook | uninstall-libcook - libcook"
	@echo "    install-cross   | uninstall-cross   - cross"
	@echo "    pot | msgmerge | msgfmt | clean     - i18n"
