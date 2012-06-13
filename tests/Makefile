#!/usr/bin/make

all: check # mago_test

check:
	set -e; \
	find . -name 'test_*.py' | \
	while read file; do \
	    if [ -x $$file ]; then \
		echo "*** RUNNING $$file"; \
		if grep -q Gtk $$file; then \
			xvfb-run python $$file; \
			xvfb-run python3 $$file; \
		else \
	    		python $$file ; \
	    		python3 $$file ; \
		fi; \
	    fi; \
	done

mago_test:
	#MAGO_SHARE=./mago/ mago -f basic.xml
	MAGO_SHARE=./mago/ mago --log-level=debug -f basic.xml

