#!/usr/bin/make

all: check # mago_test

check:
	set -e; \
	find . -name 'test_*.py' | \
	while read file; do \
	    if [ -x $$file ]; then \
		if grep -q Gtk $$file; then \
			echo "*** RUNNING $$file (under xvfb-run)"; \
			xvfb-run python $$file; \
			sleep 1; \
			xvfb-run python3 $$file; \
		else \
			echo "*** RUNNING $$file"; \
			python $$file ; \
			python3 $$file ; \
		fi; \
	    fi; \
	done

mago_test:
	#MAGO_SHARE=./mago/ mago -f basic.xml
	MAGO_SHARE=./mago/ mago --log-level=debug -f basic.xml

