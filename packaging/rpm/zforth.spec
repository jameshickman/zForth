# zForth has no tagged upstream releases, so this packages a git snapshot.
# To move to a newer snapshot, update commit and snapdate below and refresh
# the tarball with spectool -g.
%global commit          41db72d165c1539d57f3f79970fc57ea881a79dc
%global shortcommit     %(c=%{commit}; echo ${c:0:7})
%global snapdate        20250815

# Upstream ships no soname or ABI policy. The dictionary and stack sizes in
# zfconf.h are compiled into struct zf_ctx, so any change to that header is an
# ABI break: bump libmajor when you touch it.
%global libmajor        0
%global libversion      %{libmajor}.0.0

# Kept separate from Version because "0^20250815git41db72d" is not something
# pkg-config can compare with --atleast-version.
%global pkgconfigver    %{libversion}

%global forthdir        %{_datadir}/%{name}

# Readline gives the interpreter line editing and history. Turn it off for a
# minimal build: rpmbuild --without readline
%bcond readline 1

Name:           zforth
Version:        0^%{snapdate}git%{shortcommit}
Release:        3%{?dist}
Summary:        Small, embeddable Forth interpreter and compiler

License:        MIT
URL:            https://github.com/zevv/zForth
Source0:        %{url}/archive/%{commit}/%{name}-%{shortcommit}.tar.gz
# Written for this package; upstream ships no man page.
Source1:        zforth.1
# Written for this package; shipped as documentation in the devel subpackage.
Source2:        zforth-embed-example.c

BuildRequires:  gcc
%if %{with readline}
BuildRequires:  readline-devel
%endif
BuildRequires:  pkgconfig

Requires:       lib%{name}%{?_isa} = %{version}-%{release}

%description
zForth is a small Forth interpreter and compiler written in ANSI C, meant as a
lightweight scripting language for extending applications on systems with a few
kilobytes of ROM and RAM to spare.

Instead of a fixed cell size the dictionary uses variable length cells, so small
and common numbers take less space, saving 30% to 50% over a conventional
layout. The interpreter runs as a virtual machine with bounds checked memory and
stack access rather than direct host memory access, and all VM state lives in a
single context struct so several instances can run side by side.

This package contains the interactive interpreter and the Forth standard
library. The standard library is not loaded automatically; pass
%{forthdir}/core.zf on the command line to get the basic
words and control structures.

%package -n lib%{name}
Summary:        Embeddable Forth interpreter library

%description -n lib%{name}
The zForth interpreter and compiler as a shared library, for embedding a Forth
scripting environment in a C or C++ program.

%package -n lib%{name}-notrace
Summary:        Embeddable Forth interpreter library, built without tracing

%description -n lib%{name}-notrace
libzforth with the tracing code left out at compile time.

Compiling tracing in costs about 45% of interpreter run time even when it is
switched off at run time through the 'trace' user variable, because every trace
site still has to test the flag. A program that never wants a trace can link
this library instead and does not have to define the zf_host_trace() callback.

Otherwise it is interchangeable with libzforth: same headers, same API, and the
same ABI, since ZF_ENABLE_TRACE does not appear in struct zf_ctx.

%package -n lib%{name}-devel
Summary:        Development files for libzforth
Requires:       lib%{name}%{?_isa} = %{version}-%{release}

%description -n lib%{name}-devel
Headers, the link time symlink and a pkg-config file for building against
libzforth. A worked example is installed as
%{_docdir}/lib%{name}-devel/zforth-embed-example.c.

The library deliberately leaves three callbacks undefined: zf_host_sys(),
zf_host_trace() and zf_host_parse_num(). The embedding program must define them,
and must be linked with -Wl,--export-dynamic so the shared library can resolve
them at run time. The pkg-config file adds that flag for you.

The compile time configuration lives in zfconf.h, installed next to zforth.h.
Because the dictionary and stack sizes there are baked into struct zf_ctx, a
program must be built against the same zfconf.h the library was built with; edit
it only alongside a rebuild of the library itself.

%package -n lib%{name}-notrace-devel
Summary:        Development files for libzforth-notrace
Requires:       lib%{name}-notrace%{?_isa} = %{version}-%{release}
Requires:       lib%{name}-devel%{?_isa} = %{version}-%{release}

%description -n lib%{name}-notrace-devel
The link time symlink and a pkg-config file for building against
libzforth-notrace. The headers come from lib%{name}-devel; both libraries are
built from the same zforth.h and zfconf.h.

%package -n lib%{name}-static
Summary:        Static build of libzforth
Requires:       lib%{name}-devel%{?_isa} = %{version}-%{release}

%description -n lib%{name}-static
The static version of libzforth, for embedding the interpreter without a runtime
dependency on the shared library.

%prep
%autosetup -n zForth-%{commit}

%build
# The upstream Makefile appends -Os -g, -Werror and an AddressSanitizer build to
# CFLAGS and LDFLAGS unconditionally, none of which belongs in a distribution
# package. The compiler is driven directly here so only the distribution flags
# are in effect.
CFLAGS="%{build_cflags} -Isrc/zforth -Isrc/linux"
LDFLAGS="%{build_ldflags}"

# zf_push() and the other stack calls are public API, so under -fPIC the
# compiler has to assume the dynamic linker could interpose them and calls them
# through the PLT rather than inlining, which costs the inner interpreter a
# factor of two against the same code linked statically.
# -fno-semantic-interposition lets the library bind to its own definitions. The
# symbols stay exported for callers; only LD_PRELOAD interposition of them is
# given up.
PICFLAGS="-fPIC -DPIC -fno-semantic-interposition"

# Shared library
%{__cc} $CFLAGS $PICFLAGS -c src/zforth/zforth.c -o zforth.shared.o
%{__cc} $LDFLAGS -shared -Wl,-soname,lib%{name}.so.%{libmajor} \
        -o lib%{name}.so.%{libversion} zforth.shared.o
ln -s lib%{name}.so.%{libversion} lib%{name}.so.%{libmajor}
ln -s lib%{name}.so.%{libversion} lib%{name}.so

# Untraced shared library, for programs that never want a trace. The
# configuration header is derived from the one the traced build uses rather than
# duplicated, so the two cannot drift apart in the dictionary and stack sizes
# that are baked into struct zf_ctx. The copy goes first on the include path.
mkdir -p notrace
sed -e 's/^\(#define[[:space:]]\{1,\}ZF_ENABLE_TRACE[[:space:]]\{1,\}\)1$/\10/' \
        src/linux/zfconf.h > notrace/zfconf.h
grep -q '^#define[[:space:]]\{1,\}ZF_ENABLE_TRACE[[:space:]]\{1,\}0$' notrace/zfconf.h || \
        { echo "could not switch tracing off in zfconf.h" >&2; exit 1; }

NTCFLAGS="%{build_cflags} -Inotrace -Isrc/zforth -Isrc/linux"
%{__cc} $NTCFLAGS $PICFLAGS -c src/zforth/zforth.c -o zforth-notrace.shared.o
%{__cc} $LDFLAGS -shared -Wl,-soname,lib%{name}-notrace.so.%{libmajor} \
        -o lib%{name}-notrace.so.%{libversion} zforth-notrace.shared.o
ln -s lib%{name}-notrace.so.%{libversion} lib%{name}-notrace.so.%{libmajor}
ln -s lib%{name}-notrace.so.%{libversion} lib%{name}-notrace.so

# Static library
%{__cc} $CFLAGS -c src/zforth/zforth.c -o zforth.static.o
%{__ar} rcs lib%{name}.a zforth.static.o

# Interpreter. --export-dynamic exports the zf_host_* callbacks defined in
# main.c so the shared library can bind to them.
%{__cc} $CFLAGS %{?with_readline:-DUSE_READLINE} -c src/linux/main.c -o main.o
%{__cc} $LDFLAGS -Wl,--export-dynamic -o %{name} main.o \
        -L. -l%{name} %{?with_readline:-lreadline} -lm

# One pkg-config file per library. They differ only in which library they name,
# so they are generated from the same template.
for variant in "" "-notrace"; do
cat > %{name}$variant.pc <<EOF
prefix=%{_prefix}
exec_prefix=%{_exec_prefix}
libdir=%{_libdir}
includedir=%{_includedir}

Name: zforth$variant
Description: Small, embeddable Forth interpreter and compiler${variant:+, without tracing}
URL: %{url}
Version: %{pkgconfigver}
# --export-dynamic is required: libzforth calls back into zf_host_sys(),
# zf_host_trace() and zf_host_parse_num(), which the program provides.
# libzforth-notrace does not call zf_host_trace(), but a program that defines it
# anyway still links.
Libs: -L\${libdir} -lzforth$variant -Wl,--export-dynamic
Libs.private: -lm
Cflags: -I\${includedir}/zforth
EOF
done

%install
install -Dpm 0755 %{name} %{buildroot}%{_bindir}/%{name}

install -Dpm 0755 lib%{name}.so.%{libversion} \
        %{buildroot}%{_libdir}/lib%{name}.so.%{libversion}
ln -s lib%{name}.so.%{libversion} \
        %{buildroot}%{_libdir}/lib%{name}.so.%{libmajor}
ln -s lib%{name}.so.%{libversion} %{buildroot}%{_libdir}/lib%{name}.so

install -Dpm 0755 lib%{name}-notrace.so.%{libversion} \
        %{buildroot}%{_libdir}/lib%{name}-notrace.so.%{libversion}
ln -s lib%{name}-notrace.so.%{libversion} \
        %{buildroot}%{_libdir}/lib%{name}-notrace.so.%{libmajor}
ln -s lib%{name}-notrace.so.%{libversion} \
        %{buildroot}%{_libdir}/lib%{name}-notrace.so

install -Dpm 0644 lib%{name}.a %{buildroot}%{_libdir}/lib%{name}.a

install -Dpm 0644 src/zforth/zforth.h %{buildroot}%{_includedir}/%{name}/zforth.h
install -pm 0644 src/linux/zfconf.h %{buildroot}%{_includedir}/%{name}/zfconf.h

install -Dpm 0644 %{name}.pc %{buildroot}%{_libdir}/pkgconfig/%{name}.pc
install -pm 0644 %{name}-notrace.pc \
        %{buildroot}%{_libdir}/pkgconfig/%{name}-notrace.pc

# Forth standard library and examples
install -dm 0755 %{buildroot}%{forthdir}
install -pm 0644 forth/*.zf %{buildroot}%{forthdir}/

install -Dpm 0644 %{SOURCE2} \
        %{buildroot}%{_docdir}/lib%{name}-devel/zforth-embed-example.c

install -Dpm 0644 %{SOURCE1} %{buildroot}%{_mandir}/man1/%{name}.1
sed -i -e 's|%%DATADIR%%|%{forthdir}|g' \
       -e 's|%%DOCDIR%%|%{_docdir}/%{name}|g' \
       %{buildroot}%{_mandir}/man1/%{name}.1

%check
# The interpreter is useless without core.zf, so exercise the pair: compile a
# word at run time, call it, and check what lands on the stack. core.zf prints
# a line of its own while loading, so match a line rather than the whole output.
export LD_LIBRARY_PATH=$PWD
out=$(echo ': double 2 * ; 21 double . cr' | \
      ./%{name} -q %{buildroot}%{forthdir}/core.zf | tr -d ' \r')
echo "$out" | grep -qx 42 || { echo "smoke test failed, got: '$out'" >&2; exit 1; }

# libzforth is expected to leave exactly the three zf_host_* callbacks to the
# program that embeds it. Anything else unresolved in the zf_ namespace means
# the library was built or linked wrong.
export LC_ALL=C
for sym in zf_host_sys zf_host_trace zf_host_parse_num; do
  nm -D --undefined-only lib%{name}.so.%{libversion} | grep -qw "$sym" || \
    { echo "expected callback $sym is not undefined in the library" >&2; exit 1; }
done
for lib in lib%{name} lib%{name}-notrace; do
  stray=$(nm -D --undefined-only $lib.so.%{libversion} | awk '{print $NF}' | \
          grep '^zf_' | grep -v '^zf_host_' || :)
  test -z "$stray" || \
    { echo "unexpected undefined zf_ symbols in $lib: $stray" >&2; exit 1; }
done

# The untraced library still needs the other two callbacks, but must not refer
# to zf_host_trace() at all. If it does, the tracing code was compiled in after
# all and the sed in %%build silently did nothing.
for sym in zf_host_sys zf_host_parse_num; do
  nm -D --undefined-only lib%{name}-notrace.so.%{libversion} | grep -qw "$sym" || \
    { echo "expected callback $sym is not undefined in libzforth-notrace" >&2; exit 1; }
done
nm -D --undefined-only lib%{name}-notrace.so.%{libversion} | \
    grep -qw zf_host_trace && \
  { echo "libzforth-notrace still references zf_host_trace" >&2; exit 1; } || :

# The two libraries must be built from the same struct zf_ctx, or a program
# compiled against the shared headers would be wrong for one of them.
for lib in lib%{name} lib%{name}-notrace; do
  nm -D --defined-only $lib.so.%{libversion} | grep -qw zf_init || \
    { echo "$lib does not export zf_init" >&2; exit 1; }
done

# Build the shipped example against the headers and pkg-config file exactly as
# a user of the devel package would, so a broken zforth.pc fails the build.
# Both pkg-config files get the same treatment, so a broken zforth-notrace.pc
# or a library the example cannot link against fails the build too.
export PKG_CONFIG_PATH=%{buildroot}%{_libdir}/pkgconfig
export PKG_CONFIG_SYSROOT_DIR=%{buildroot}
export LD_LIBRARY_PATH=%{buildroot}%{_libdir}:$LD_LIBRARY_PATH
for pc in zforth zforth-notrace; do
  %{__cc} %{build_cflags} $(pkg-config --cflags $pc) %{SOURCE2} \
          $(pkg-config --libs $pc) -lm -o example-check
  test "$(./example-check | tr -d ' \r')" = "49" || \
    { echo "example program built against $pc did not print 49" >&2; exit 1; }
done

# The API the header advertises must actually be exported.
for lib in lib%{name} lib%{name}-notrace; do
  for sym in zf_init zf_bootstrap zf_eval zf_dump zf_abort zf_push zf_pop \
             zf_pick zf_uservar_set zf_uservar_get; do
    nm -D --defined-only $lib.so.%{libversion} | grep -qw "$sym" || \
      { echo "$sym is missing from $lib" >&2; exit 1; }
  done
done

%files
%license LICENSE
%doc README.md forth/README
%{_bindir}/%{name}
%{_mandir}/man1/%{name}.1*
%dir %{forthdir}
%{forthdir}/*.zf

%files -n lib%{name}
%license LICENSE
%{_libdir}/lib%{name}.so.%{libmajor}
%{_libdir}/lib%{name}.so.%{libversion}

%files -n lib%{name}-notrace
%license LICENSE
%{_libdir}/lib%{name}-notrace.so.%{libmajor}
%{_libdir}/lib%{name}-notrace.so.%{libversion}

%files -n lib%{name}-devel
%dir %{_docdir}/lib%{name}-devel
%doc %{_docdir}/lib%{name}-devel/zforth-embed-example.c
%dir %{_includedir}/%{name}
%{_includedir}/%{name}/zforth.h
%{_includedir}/%{name}/zfconf.h
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%files -n lib%{name}-notrace-devel
%{_libdir}/lib%{name}-notrace.so
%{_libdir}/pkgconfig/%{name}-notrace.pc

%files -n lib%{name}-static
%{_libdir}/lib%{name}.a

%changelog
* Thu Aug 27 2026 James Hickman <jameshickman0077@gmail.com> - 0^20250815git41db72d-2
- Rebuild with readline enabled, giving the interpreter line editing and history

* Thu Aug 27 2026 James Hickman <jameshickman0077@gmail.com> - 0^20250815git41db72d-1
- Initial package of the 41db72d snapshot
- Split out libzforth, libzforth-devel and libzforth-static for embedding
- Build with distribution flags instead of the upstream ASan/-Werror Makefile
