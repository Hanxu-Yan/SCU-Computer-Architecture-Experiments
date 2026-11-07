/* Source-instrumented array accesses, not a hardware/ISA trace.
 * Logical addresses are fixed to make runs independent of ASLR and allocator.
 * Initialization, checks, loop indices, stack and instruction fetch are excluded.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { N = 128, REPEATS = 4, TILE = 8 };
static uint32_t a[N * N], b[N * N];
static FILE *trace;
static const uint64_t BASE_A = 0x100000, BASE_B = 0x200000;

static uint32_t load_a(int index) {
    fprintf(trace, "R 0x%llx 4\n", (unsigned long long)(BASE_A + 4ULL * index));
    return a[index];
}
static void store_b(int index, uint32_t value) {
    fprintf(trace, "W 0x%llx 4\n", (unsigned long long)(BASE_B + 4ULL * index));
    b[index] = value;
}
int main(int argc, char **argv) {
    if (argc != 3) { fprintf(stderr, "usage: kernels MODE OUTPUT.trace\n"); return 2; }
    const char *mode = argv[1];
    if (strcmp(mode, "row_scan") && strcmp(mode, "column_scan") &&
        strcmp(mode, "transpose_naive") && strcmp(mode, "transpose_tiled")) return 2;
    trace = fopen(argv[2], "w");
    if (!trace) { perror("fopen"); return 2; }
    for (int i = 0; i < N * N; ++i) a[i] = (uint32_t)((i * 17 + 3) % 1009);
    uint64_t checksum = 0, expected = 0;
    for (int i = 0; i < N * N; ++i) expected += a[i];
    for (int r = 0; r < REPEATS; ++r) {
        if (!strcmp(mode, "row_scan")) {
            for (int i = 0; i < N; ++i)
                for (int j = 0; j < N; ++j) checksum += load_a(i * N + j);
        } else if (!strcmp(mode, "column_scan")) {
            for (int j = 0; j < N; ++j)
                for (int i = 0; i < N; ++i) checksum += load_a(i * N + j);
        } else if (!strcmp(mode, "transpose_naive")) {
            for (int i = 0; i < N; ++i)
                for (int j = 0; j < N; ++j) store_b(j * N + i, load_a(i * N + j));
        } else {
            for (int ii = 0; ii < N; ii += TILE)
                for (int jj = 0; jj < N; jj += TILE)
                    for (int i = ii; i < ii + TILE; ++i)
                        for (int j = jj; j < jj + TILE; ++j)
                            store_b(j * N + i, load_a(i * N + j));
        }
    }
    if (fclose(trace)) { perror("fclose"); return 2; }
    if (strstr(mode, "transpose")) {
        for (int i = 0; i < N; ++i)
            for (int j = 0; j < N; ++j) {
                if (b[j * N + i] != a[i * N + j]) {
                    fprintf(stderr, "transpose validation failed\n"); return 1;
                }
                checksum += b[j * N + i];
            }
        if (checksum != expected) return 1;
    } else if (checksum != expected * REPEATS) return 1;
    printf("{\"kernel\":\"%s\",\"N\":%d,\"repeats\":%d,\"tile\":%d,"
           "\"checksum\":%llu,\"validated\":true}\n",
           mode, N, REPEATS, TILE, (unsigned long long)checksum);
    return 0;
}
