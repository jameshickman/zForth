/*
 * Regression tests for the dictionary bound.
 *
 * ZF_ENABLE_BOUNDARY_CHECKS is what keeps a running program inside its own
 * dictionary, which is the property an embedder relies on when it runs Forth
 * it did not write. These tests drive an address past the end of the
 * dictionary through each of the three paths that reach it -- the instruction
 * fetch, a load and a store -- and require ZF_ABORT_OUTSIDE_MEM every time.
 *
 * The instruction fetch is the interesting one. ctx->ip is not derived solely
 * from the interpreter's own control flow: PRIM_EXIT takes it from the return
 * stack and >r pushes an arbitrary cell there, so ordinary Forth reaches an
 * out of range ip without any host help:
 *
 *     : evil 4096 >r ;   evil
 *
 * That path was briefly unchecked, when the single byte opcode decode was
 * moved inline into run() and stopped going through dict_get_bytes(). An
 * address just past the end reads adjacent members of struct zf_ctx, so it
 * neither crashes nor produces wrong output -- the interpreter simply carried
 * on and returned ZF_OK. Nothing in forth/ noticed, trace output included.
 * Hence a test that asserts the abort code rather than the output.
 *
 * Build and run with 'make test' from the top of the tree.
 */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "zforth.h"

/* Minimal host. The tests never print or parse anything interesting; the
 * callbacks exist because the library leaves them to the embedder. */
zf_input_state zf_host_sys(zf_ctx *ctx, zf_syscall_id id, const char *last_word)
{
	(void)last_word;
	switch (id) {
	case ZF_SYSCALL_EMIT:
	case ZF_SYSCALL_PRINT:
		(void)zf_pop(ctx);
		break;
	default:
		break;
	}
	return ZF_INPUT_INTERPRET;
}

zf_cell zf_host_parse_num(zf_ctx *ctx, const char *buf)
{
	char *end;
	double v = strtod(buf, &end);
	if (*end != '\0') zf_abort(ctx, ZF_ABORT_NOT_A_WORD);
	return (zf_cell)v;
}

void zf_host_trace(zf_ctx *ctx, const char *fmt, va_list va)
{
	(void)ctx; (void)fmt; (void)va;
}

static zf_ctx ctx;
static int failures;

static const char *result_name(zf_result r)
{
	switch (r) {
	case ZF_OK:                    return "ZF_OK";
	case ZF_ABORT_INTERNAL_ERROR:  return "ZF_ABORT_INTERNAL_ERROR";
	case ZF_ABORT_OUTSIDE_MEM:     return "ZF_ABORT_OUTSIDE_MEM";
	case ZF_ABORT_DSTACK_UNDERRUN: return "ZF_ABORT_DSTACK_UNDERRUN";
	case ZF_ABORT_DSTACK_OVERRUN:  return "ZF_ABORT_DSTACK_OVERRUN";
	case ZF_ABORT_RSTACK_UNDERRUN: return "ZF_ABORT_RSTACK_UNDERRUN";
	case ZF_ABORT_RSTACK_OVERRUN:  return "ZF_ABORT_RSTACK_OVERRUN";
	case ZF_ABORT_NOT_A_WORD:      return "ZF_ABORT_NOT_A_WORD";
	case ZF_ABORT_COMPILE_ONLY_WORD: return "ZF_ABORT_COMPILE_ONLY_WORD";
	case ZF_ABORT_INVALID_SIZE:    return "ZF_ABORT_INVALID_SIZE";
	case ZF_ABORT_DIVISION_BY_ZERO: return "ZF_ABORT_DIVISION_BY_ZERO";
	case ZF_ABORT_INVALID_USERVAR: return "ZF_ABORT_INVALID_USERVAR";
	case ZF_ABORT_EXTERNAL:        return "ZF_ABORT_EXTERNAL";
	default:                       return "unknown";
	}
}

static void fresh(void)
{
	memset(&ctx, 0, sizeof ctx);
	zf_init(&ctx, 0);
	zf_bootstrap(&ctx);
}

/* Run 'src' on a clean VM and require it to end with 'want'. */
static void expect(const char *what, const char *src, zf_result want)
{
	zf_result got;
	fresh();
	got = zf_eval(&ctx, src);
	if (got == want) {
		printf("  ok    %-34s %s\n", what, result_name(got));
	} else {
		printf("  FAIL  %-34s expected %s, got %s\n",
		       what, result_name(want), result_name(got));
		failures++;
	}
}

/* As above, but the offending code is compiled into a word first, so the abort
 * comes out of run() rather than out of the outer interpreter. */
static void expect_word(const char *what, const char *body, zf_result want)
{
	char buf[256];
	zf_result got;
	fresh();
	snprintf(buf, sizeof buf, ": evil %s ;", body);
	got = zf_eval(&ctx, buf);
	if (got != ZF_OK) {
		printf("  FAIL  %-34s could not define: %s\n", what, result_name(got));
		failures++;
		return;
	}
	got = zf_eval(&ctx, "evil");
	if (got == want) {
		printf("  ok    %-34s %s\n", what, result_name(got));
	} else {
		printf("  FAIL  %-34s expected %s, got %s\n",
		       what, result_name(want), result_name(got));
		failures++;
	}
}

int main(void)
{
	char buf[160];
	const zf_addr past[] = {
		ZF_DICT_SIZE,          /* first byte past the end: reads into struct
		                        * zf_ctx itself, so it is quiet rather than
		                        * fatal -- the case a crash-based test misses */
		ZF_DICT_SIZE + 4,
		ZF_DICT_SIZE + 256,
		ZF_DICT_SIZE * 2,
		100000,                /* far enough out to leave the object entirely */
	};
	size_t i;

	/* A regression here does not necessarily abort cleanly -- an unchecked
	 * fetch far enough past the dictionary leaves the object entirely and
	 * takes the process with it. Unbuffered output means the last line
	 * printed still names the case that died. */
	setvbuf(stdout, NULL, _IONBF, 0);

	printf("dictionary bounds (ZF_DICT_SIZE=%d)\n", (int)ZF_DICT_SIZE);

	/* Control: the harness must be able to report success, or every
	 * assertion below would pass on a VM that aborts unconditionally. */
	expect("in-bounds code still runs", ": ok 2 2 + drop ; ok", ZF_OK);

	/* The instruction fetch. >r plants the address, the implicit EXIT at the
	 * end of the word loads it into ip, and the next fetch must refuse it. */
	for (i = 0; i < sizeof past / sizeof *past; i++) {
		char name[64];
		snprintf(name, sizeof name, "fetch at ip=%lu", (unsigned long)past[i]);
		snprintf(buf, sizeof buf, "%lu >r", (unsigned long)past[i]);
		expect_word(name, buf, ZF_ABORT_OUTSIDE_MEM);
	}

	/* Loads and stores reach the dictionary through the same bound. @@ and
	 * !! are the primitives behind core.zf's @ and !, taking an explicit
	 * size so the test does not have to load core.zf; size 2 is a single
	 * byte, which puts the tightest possible probe on the boundary. The
	 * in-bounds control sits a little inside the end rather than on the last
	 * byte: the check is 'addr < ZF_DICT_SIZE - len', so the final len bytes
	 * are conservatively unreachable and the exact cutoff is not the point
	 * being tested here. */
	snprintf(buf, sizeof buf, "%lu 2 @@ drop", (unsigned long)(ZF_DICT_SIZE - 16));
	expect("load inside the dictionary", buf, ZF_OK);

	for (i = 0; i < sizeof past / sizeof *past; i++) {
		char name[64];
		snprintf(name, sizeof name, "load at addr=%lu", (unsigned long)past[i]);
		snprintf(buf, sizeof buf, "%lu 2 @@", (unsigned long)past[i]);
		expect(name, buf, ZF_ABORT_OUTSIDE_MEM);

		snprintf(name, sizeof name, "store at addr=%lu", (unsigned long)past[i]);
		snprintf(buf, sizeof buf, "1 %lu 2 !!", (unsigned long)past[i]);
		expect(name, buf, ZF_ABORT_OUTSIDE_MEM);
	}

	if (failures) {
		printf("\n%d failure(s)\n", failures);
		return 1;
	}
	printf("\nall passed\n");
	return 0;
}
