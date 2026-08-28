BIN	:= zforth
SRC	:= main.c zforth.c

OBJS    := $(subst .c,.o, $(SRC))
DEPS    := $(subst .c,.d, $(SRC))

CC	:= $(CROSS)gcc

VPATH   := ../zforth
CFLAGS	+= -I. -I../zforth
CFLAGS  += -O2 -g -pedantic -MMD
CFLAGS  += -Wall -Wextra -Werror -Wno-unused-parameter -Wno-clobbered -Wno-unused-result
LDFLAGS	+= -g

# AddressSanitizer costs significant run time, so it is opt-in: 'make asan=1'
ifdef asan
CFLAGS	+= -fsanitize=address
LDFLAGS	+= -fsanitize=address
endif

LIBS	+= -lm

ifndef noreadline
LIBS	+= -lreadline
CFLAGS	+= -DUSE_READLINE
endif


# Shared libraries. Two variants are built from the same source and the same
# zfconf.h: libzforth has the tracing code compiled in, libzforth-notrace does
# not. Compiling tracing in costs about 45% of interpreter run time even when it
# is switched off at run time through the 'trace' user variable, because every
# trace site still has to test it, and reading it means going through
# ctx->uservar, which aliases ctx->dict and so cannot be held in a register.
# Programs that never need a trace should link the notrace variant.
#
# The two are interchangeable at the API and ABI level: ZF_ENABLE_TRACE does not
# appear in struct zf_ctx. They carry different sonames so both can be installed
# side by side and each program can pick one.
#
# Neither library defines zf_host_sys(), zf_host_trace() or zf_host_parse_num().
# The embedding program supplies those, and must be linked with
# -Wl,--export-dynamic so the library can resolve them at run time.

LIBMAJOR   := 0
LIBVERSION := $(LIBMAJOR).0.0

LIBNAME    := libzforth
LIBNAME_NT := libzforth-notrace

LIBS_SO    := $(LIBNAME).so.$(LIBVERSION) $(LIBNAME_NT).so.$(LIBVERSION)

all: $(BIN)

libs: $(LIBS_SO)

$(BIN): $(OBJS)
	$(CC) $(LDFLAGS) -o $@ $(OBJS) $(LIBS)

# zf_push() and friends are part of the public API, so under -fPIC the compiler
# must assume the dynamic linker could interpose them and calls them through the
# PLT instead of inlining. That doubles the run time of the library relative to
# the same code linked statically. -fno-semantic-interposition allows the
# library to bind to its own definitions; the symbols are still exported for
# callers, only LD_PRELOAD interposition of them is given up.
PICFLAGS := -fPIC -DPIC -fno-semantic-interposition

# -MMD would have both rules writing the same .d file, so it is dropped here.
zforth.pic.o: ../zforth/zforth.c
	$(CC) $(filter-out -MMD,$(CFLAGS)) $(PICFLAGS) -c -o $@ $<

zforth-notrace.pic.o: ../zforth/zforth.c
	$(CC) $(filter-out -MMD,$(CFLAGS)) $(PICFLAGS) -DZF_ENABLE_TRACE=0 -c -o $@ $<

$(LIBNAME).so.$(LIBVERSION): zforth.pic.o
	$(CC) $(LDFLAGS) -shared -Wl,-soname,$(LIBNAME).so.$(LIBMAJOR) -o $@ $< -lm
	ln -sf $@ $(LIBNAME).so.$(LIBMAJOR)
	ln -sf $@ $(LIBNAME).so

$(LIBNAME_NT).so.$(LIBVERSION): zforth-notrace.pic.o
	$(CC) $(LDFLAGS) -shared -Wl,-soname,$(LIBNAME_NT).so.$(LIBMAJOR) -o $@ $< -lm
	ln -sf $@ $(LIBNAME_NT).so.$(LIBMAJOR)
	ln -sf $@ $(LIBNAME_NT).so

clean:
	rm -f $(BIN) $(OBJS) $(DEPS)
	rm -f zforth.pic.o zforth-notrace.pic.o
	rm -f $(LIBNAME).so* $(LIBNAME_NT).so*

lint:
	lint -i /opt/flint/supp/lnt -i ..\\zforth -i src -w2 co-gcc.lnt \
		-e537 -e451 -e524 -e534 -e641 -e661 -e64 \
		$(SRC)

.PHONY: all libs clean lint

-include $(DEPS)
