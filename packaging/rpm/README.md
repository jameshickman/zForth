# RPM packaging for zForth

Builds six packages from one spec:

| Package | Contents |
| --- | --- |
| `zforth` | `/usr/bin/zforth`, the Forth standard library in `/usr/share/zforth`, man page |
| `libzforth` | `libzforth.so.0` — the interpreter as a shared library |
| `libzforth-devel` | headers, link symlink, `zforth.pc` |
| `libzforth-notrace` | `libzforth-notrace.so.0` — the same library without the tracing code |
| `libzforth-notrace-devel` | link symlink, `zforth-notrace.pc` (headers come from `libzforth-devel`) |
| `libzforth-static` | `libzforth.a` |

## Which library to link

`libzforth` and `libzforth-notrace` are built from the same source and the same
`zfconf.h`, and differ only in whether `ZF_ENABLE_TRACE` is on. They are
interchangeable at the API and ABI level, since that setting does not appear in
`struct zf_ctx`, and they carry different sonames so both can be installed at
once.

Compiling tracing in costs about 45% of interpreter run time even when tracing
is switched off at run time through the `trace` user variable, because every
trace site still has to test the flag. Link `libzforth` if you want
`zf_host_trace()` output for debugging Forth code; link `libzforth-notrace`
otherwise. The untraced library never calls `zf_host_trace()`, so a program
using it does not have to define that callback.

```sh
cc $(pkg-config --cflags zforth-notrace) prog.c \
   $(pkg-config --libs zforth-notrace) -lm -o prog
```

## Building

Upstream has no tagged releases, so the spec packages a git snapshot pinned by
the `commit` macro at the top of `zforth.spec`.

```sh
sudo dnf install rpm-build rpmdevtools gcc make readline-devel
rpmdev-setuptree

cp packaging/rpm/zforth.1 packaging/rpm/zforth-embed-example.c ~/rpmbuild/SOURCES/
spectool -g -R packaging/rpm/zforth.spec      # fetches the tarball from GitHub
rpmbuild -ba packaging/rpm/zforth.spec
```

Readline is on by default. For a minimal interpreter without line editing or
history, and without the `readline-devel` build dependency:

```sh
rpmbuild -ba --without readline packaging/rpm/zforth.spec
```

To build the snapshot from a local checkout instead of fetching from GitHub:

```sh
commit=$(git rev-parse HEAD)
git archive --format=tar.gz --prefix="zForth-$commit/" \
    -o ~/rpmbuild/SOURCES/zforth-$(git rev-parse --short HEAD).tar.gz HEAD
```

## Installing

Note that `zforth-*` does **not** match the library packages, which are named
`libzforth-*`. Installing that glob alone gives you the interpreter without
`libzforth.so.0` and dnf refuses the transaction. Install them together:

```sh
cd ~/rpmbuild/RPMS/x86_64
sudo dnf install $(ls *zforth-*.rpm | grep -vE 'debuginfo|debugsource' | sed 's|^|./|')
```

Or pick what you need — the runtime alone is just the first two:

```sh
sudo dnf install ./libzforth-0*.rpm ./zforth-0*.rpm            # interpreter
sudo dnf install ./libzforth-devel-0*.rpm                       # to build against it
sudo dnf install ./libzforth-notrace-0*.rpm \
                 ./libzforth-notrace-devel-0*.rpm               # untraced variant
sudo dnf install ./libzforth-static-0*.rpm                      # to link it statically
```

The leading `./` matters: without it dnf treats the argument as a package name
to look up in the repositories rather than a local file.

## Moving to a newer snapshot

Update `commit` and `snapdate` at the top of the spec, add a `%changelog` entry,
then rebuild. `shortcommit` and `Version` follow automatically.

## Using the library

```c
#include <zforth.h>
```

```sh
cc $(pkg-config --cflags zforth) prog.c $(pkg-config --libs zforth) -lm -o prog
```

A complete worked example is installed with the devel package at
`/usr/share/doc/libzforth-devel/zforth-embed-example.c`.

zForth leaves three callbacks for the embedding program to define:

```c
zf_input_state zf_host_sys(zf_ctx *ctx, zf_syscall_id id, const char *last_word);
void           zf_host_trace(zf_ctx *ctx, const char *fmt, va_list va);
zf_cell        zf_host_parse_num(zf_ctx *ctx, const char *buf);
```

They are undefined in `libzforth.so` and bind back to the program at run time,
which only works if the program exports them. `pkg-config --libs zforth`
therefore includes `-Wl,--export-dynamic`; drop it and the program will fail to
start. `libzforth-notrace.so` leaves only the first and last undefined. Upstream's `src/linux/main.c` implements all three for the CLI, if you
want a second reference.

`zfconf.h`, installed alongside `zforth.h`, holds the compile time
configuration: cell type, dictionary size, stack sizes. Those sizes are embedded
in `struct zf_ctx`, so the header is part of the ABI — a program built against a
modified `zfconf.h` will disagree with the installed `libzforth.so` about the
layout of every context. Change it only together with a library rebuild and a
`libmajor` bump.

## Notes on the build

The spec does not use the upstream `Makefile`. That Makefile appends `-O2 -g`
and `-Werror` to `CFLAGS` unconditionally, neither of which belongs in a
distribution build, and it has no install target. The spec invokes the compiler
directly instead, so only the distribution flags apply.

Both shared libraries are built with `-fno-semantic-interposition`. `zf_push()`
and the other stack calls are public API, so under `-fPIC` the compiler
otherwise has to assume the dynamic linker could interpose them, and calls them
through the PLT instead of inlining. That costs the inner interpreter a factor
of two against the same code linked statically. The symbols stay exported; only
`LD_PRELOAD` interposition of them is given up.

The two variants share one `zfconf.h`, so they cannot drift apart in the
dictionary and stack sizes that are baked into `struct zf_ctx`. The header only
defines `ZF_ENABLE_TRACE` if it is not already set, so the untraced build is
just `-DZF_ENABLE_TRACE=0`. If that guard ever goes away upstream the header
would win over the `-D` and the build would quietly produce a second traced
library — which is what the `zf_host_trace()` assertion in `%check` catches.

`%check` does three things: runs the interpreter against the packaged `core.zf`
and compiles a word at run time, confirms both shared libraries export the API
in `zforth.h` and leave only the expected `zf_host_*` callbacks undefined — and
that `libzforth-notrace.so` does not reference `zf_host_trace()` at all, which
is what proves the tracing code really was left out — and builds the shipped
example through `pkg-config` against each of `zforth.pc` and
`zforth-notrace.pc`, the way a consumer of the devel packages would, so a broken
`.pc` fails the build rather than the user.
