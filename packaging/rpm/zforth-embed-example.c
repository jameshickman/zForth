/*
 * Minimal example of embedding zForth in a C program.
 *
 *   cc $(pkg-config --cflags zforth) zforth-embed-example.c \
 *      $(pkg-config --libs zforth) -lm -o example
 *
 * The -Wl,--export-dynamic in `pkg-config --libs` is not optional: libzforth
 * calls back into the three zf_host_* functions below, and cannot find them
 * unless the executable exports its dynamic symbols.
 *
 * Only the kernel primitives are available here. Words like `.` and `if` live
 * in core.zf, which is installed in /usr/share/zforth and can be read in with
 * zf_eval() a line at a time.
 */

#include <stdio.h>
#include <math.h>

#include <zforth.h>

/*
 * Called when the interpreter hits the `sys` word. Calls 0 to 2 are the core
 * ones every host should handle; ZF_SYSCALL_USER and up are yours to define.
 */

zf_input_state zf_host_sys(zf_ctx *ctx, zf_syscall_id id, const char *last_word)
{
	switch((int)id) {

		case ZF_SYSCALL_EMIT:
			putchar((char)zf_pop(ctx));
			break;

		case ZF_SYSCALL_PRINT:
			printf(ZF_CELL_FMT " ", zf_pop(ctx));
			break;

		case ZF_SYSCALL_TELL: {
			zf_cell len = zf_pop(ctx);
			zf_cell addr = zf_pop(ctx);
			if(addr >= ZF_DICT_SIZE - len) {
				zf_abort(ctx, ZF_ABORT_OUTSIDE_MEM);
			}
			void *buf = (uint8_t *)zf_dump(ctx, NULL) + (int)addr;
			(void)fwrite(buf, 1, len, stdout);
			break;
		}

		case ZF_SYSCALL_USER + 0:
			zf_push(ctx, sin(zf_pop(ctx)));
			break;

		default:
			fprintf(stderr, "unhandled syscall %d\n", id);
			break;
	}

	return ZF_INPUT_INTERPRET;
}

/*
 * Only reached when tracing is enabled, either by passing a nonzero trace
 * argument to zf_init() or by setting the `trace` user variable.
 */

void zf_host_trace(zf_ctx *ctx, const char *fmt, va_list va)
{
	vfprintf(stderr, fmt, va);
}

/*
 * Called for every word the dictionary does not recognise. Abort if it is not
 * a number either.
 */

zf_cell zf_host_parse_num(zf_ctx *ctx, const char *buf)
{
	zf_cell v;
	int n = 0;

	if(sscanf(buf, ZF_SCAN_FMT "%n", &v, &n) != 1 || buf[n] != '\0') {
		zf_abort(ctx, ZF_ABORT_NOT_A_WORD);
	}

	return v;
}

int main(void)
{
	/* struct zf_ctx holds the dictionary and both stacks, so it is large;
	 * keep it off the stack. Several instances can run side by side. */

	static zf_ctx ctx;

	zf_init(&ctx, 0);
	zf_bootstrap(&ctx);

	if(zf_eval(&ctx, ": square dup * ; 7 square 1 sys") != ZF_OK) {
		fprintf(stderr, "evaluation failed\n");
		return 1;
	}

	printf("\n");
	return 0;
}
