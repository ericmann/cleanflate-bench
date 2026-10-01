/* Minimal zlib stdin->stdout decompressor over zlib-ng's native API, for the size comparison. */
#include <stdio.h>
#include <string.h>
#include <zlib-ng.h>

#define BUF (64 * 1024)

int main(void) {
    static unsigned char in[BUF], out[BUF];
    zng_stream s;
    int rc = Z_OK;
    memset(&s, 0, sizeof s);
    if (zng_inflateInit2(&s, 15) != Z_OK) {
        fprintf(stderr, "error: inflateInit2 failed\n");
        return 1;
    }
    for (;;) {
        size_t n = fread(in, 1, BUF, stdin);
        if (n == 0) break;
        s.next_in = in;
        s.avail_in = (unsigned)n;
        do {
            s.next_out = out;
            s.avail_out = BUF;
            rc = zng_inflate(&s, Z_NO_FLUSH);
            if (rc != Z_OK && rc != Z_STREAM_END && rc != Z_BUF_ERROR) {
                fprintf(stderr, "error: inflate failed (%d)\n", rc);
                zng_inflateEnd(&s);
                return 1;
            }
            if (fwrite(out, 1, BUF - s.avail_out, stdout) != BUF - s.avail_out) {
                fprintf(stderr, "error: write failed\n");
                zng_inflateEnd(&s);
                return 1;
            }
        } while (rc != Z_STREAM_END && (s.avail_in != 0 || s.avail_out == 0));
        if (rc == Z_STREAM_END) break;
    }
    zng_inflateEnd(&s);
    if (rc != Z_STREAM_END) {
        fprintf(stderr, "error: truncated input\n");
        return 1;
    }
    return 0;
}
