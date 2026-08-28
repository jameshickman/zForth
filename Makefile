

CC ?= cc

# Same warning set as src/linux/Makefile, so the test does not build under
# looser rules than the interpreter it exercises.
TEST_CFLAGS = -I src/linux -I src/zforth -O2 -g -pedantic \
              -Wall -Wextra -Werror -Wno-unused-parameter -Wno-clobbered \
              -Wno-unused-result

all:
	make -C src/linux

# Tests for behaviour the snippets in forth/ cannot express. Those are checked
# by eye against their output; these assert the abort code an operation
# returns, which is the only way to see a missing bounds check -- an unchecked
# access near the end of the dictionary reads adjacent members of struct
# zf_ctx and produces perfectly normal output.
test: test/test_bounds
	./test/test_bounds

test/test_bounds: test/test_bounds.c src/zforth/zforth.c src/zforth/zforth.h \
                  src/linux/zfconf.h
	$(CC) $(TEST_CFLAGS) -o $@ test/test_bounds.c src/zforth/zforth.c -lm

clean:
	make -C src/linux clean
	make -C src/atmega8 clean
	rm -f test/test_bounds

.PHONY: all test clean
