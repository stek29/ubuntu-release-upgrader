#!/usr/bin/make

all: check # mago_test

check:
	find . -name 'test_*.py' | \
	while read file; do \
	    if [ -x $$file ]; then \
	    	python $$file ; \
	    fi \
	done

mago_test:
	#MAGO_SHARE=./mago/ mago -f basic.xml
	MAGO_SHARE=./mago/ mago --log-level=debug -f basic.xml

