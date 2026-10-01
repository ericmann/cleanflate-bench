# Fragments: cf vs zng (test)

Verdicts live in `config/similarity_verdicts.toml` under `[cf_zng]` keyed by fragment id; allowed values: `RFC-forced`, `idiomatic-inevitable`, `suspicious`.

## 1. `b0caee6591b9` (15 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 193-195

```
            *cell = crc32_slice_entry(b, k);
            b += 1;
            cells = cells_tail;
```

zng: `arch/power/crc32_power8.c` lines 347-350

```
                vconst1 = vec_ld(offset, vcrc_const);
                offset += 16;

                v0 = vec_xor(v0, va0);
```

## 2. `7805fdfa615a` (14 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 75-79

```
            s1 += byte as u32;
            s2 += s1;
        }
        s1 %= ADLER_MOD;
        s2 %= ADLER_MOD;
```

zng: `adler32_p.h` lines 32-36

```
        adler += *buf++;
        sum2 += adler;
    }
    adler %= BASE;
    sum2 %= BASE;            /* only added so many BASE's */
```

## 3. `7805fdfa615a` (14 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 75-79

```
            s1 += byte as u32;
            s2 += s1;
        }
        s1 %= ADLER_MOD;
        s2 %= ADLER_MOD;
```

zng: `adler32_p.h` lines 44-48

```
        adler += *dst++;
        sum2 += adler;
    }
    adler %= BASE;
    sum2 %= BASE;            /* only added so many BASE's */
```

## 4. `12a4e5fcb0d1` (14 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 75-79

```
            s1 += byte as u32;
            s2 += s1;
        }
        s1 %= ADLER_MOD;
        s2 %= ADLER_MOD;
```

zng: `arch/riscv/adler32_rvv.c` lines 118-123

```
        adler += *src++;
        sum2 += adler;
    }

    sum2 %= BASE;
    adler %= BASE;
```

## 5. `c0acca3d333b` (14 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 248-250

```
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
    crc32_update_bytewise(crc, tail)
```

zng: `arch/x86/chorba_sse41.c` lines 226-230

```
        STORE4(in12, in34, in56, in78, bitbuf300);
    }

    /* Second half of stores bubbled out */
    _mm_store_si128(bitbuf144, buf144);
```

## 6. `73ce714ff815` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 193-195

```
            *cell = crc32_slice_entry(b, k);
            b += 1;
            cells = cells_tail;
```

zng: `arch/power/crc32_power8.c` lines 282-284

```
                    vconst1 = vec_ld(offset, vcrc_const);
                    offset += 16;
                    GROUP_ENDING_NOP;
```

## 7. `137400c9c73f` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 193-195

```
            *cell = crc32_slice_entry(b, k);
            b += 1;
            cells = cells_tail;
```

zng: `arch/x86/crc32_fold_pclmulqdq_tpl.h` lines 73-75

```
                xmm_crc3 = _mm_xor_si128(xmm_crc3, xmm_t0);
                src += 16;
                len -= 16;
```

## 8. `eea6b5a6cca9` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 247-249

```
    for chunk in chunks {
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
```

zng: `arch/generic/crc32_chorba_c.c` lines 1478-1481

```
    } else {
        // Process too short lengths using crc32_braid
        c = crc32_braid_internal(c, buf, len);
    }
```

## 9. `493d6867ba5c` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 247-249

```
    for chunk in chunks {
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
```

zng: `arch/x86/chorba_sse2.c` lines 865-867

```
        {
            c = chorba_small_nondestructive_sse2(c, aligned_buf, len);
        }
```

## 10. `493d6867ba5c` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 247-249

```
    for chunk in chunks {
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
```

zng: `arch/x86/chorba_sse2.c` lines 868-871

```
    } else {
        // Process too short lengths using crc32_braid
        c = crc32_braid_internal(c, buf, len);
    }
```

## 11. `bdfa48f8ac1f` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 247-249

```
    for chunk in chunks {
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
```

zng: `arch/x86/chorba_sse41.c` lines 323-325

```
        if (len > CHORBA_MEDIUM_LOWER_THRESHOLD && len <= CHORBA_MEDIUM_UPPER_THRESHOLD) {
            c = crc32_chorba_32768_nondestructive_sse41(c, aligned_buf, len);
        } else {
```

## 12. `bdfa48f8ac1f` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 247-249

```
    for chunk in chunks {
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
```

zng: `arch/x86/chorba_sse41.c` lines 325-327

```
        } else {
            c = chorba_small_nondestructive_sse2(c, aligned_buf, len);
        }
```

## 13. `bdfa48f8ac1f` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 247-249

```
    for chunk in chunks {
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
```

zng: `arch/x86/chorba_sse41.c` lines 328-331

```
    } else {
        // Process too short lengths using crc32_braid
        c = crc32_braid_internal(c, buf, len);
    }
```

## 14. `47758e020694` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 248-250

```
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
    crc32_update_bytewise(crc, tail)
```

zng: `arch/power/crc32_power8.c` lines 77-80

```
        crc = crc32_align(crc, p, tail);
    }

out:
```

## 15. `ecb4487212c9` (13 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 248-250

```
        crc = crc32_fold_chunk(tables, crc, chunk);
    }
    crc32_update_bytewise(crc, tail)
```

zng: `arch/x86/chorba_sse41.c` lines 222-225

```
            READ4_WITHXOR(n, o, p, buf210, in23, in45, in67, in8_, bitbuf210);
        }

        STORE4(m, n, o, p, bitbuf210);
```

## 16. `9185085c6604` (13 tokens)

Verdict: (none yet)

cf: `src/zlib.rs` lines 196-198

```
                            self.adler.update(sink.written_since(before));
                            pos += consumed;
                            out_pos += produced;
```

zng: `arch/riscv/chunkset_rvv.c` lines 98-100

```
    memcpy(out, from, sizeof(chunk_t));
    out += align;
    from += align;
```

## 17. `19367dd87eae` (12 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 193-195

```
            *cell = crc32_slice_entry(b, k);
            b += 1;
            cells = cells_tail;
```

zng: `arch/arm/adler32_neon.c` lines 95-97

```
            vst1q_u8(dst, d0);
            dst += 16;
            uint16x8_t adler;
```

## 18. `8d0c4d22a329` (12 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 193-194

```
            *cell = crc32_slice_entry(b, k);
            b += 1;
```

zng: `arch/power/adler32_power8.c` lines 100-102

```
            vs2 = vec_add(vsum2, vs2);

            buf += 16;
```

## 19. `8d0c4d22a329` (12 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 193-194

```
            *cell = crc32_slice_entry(b, k);
            b += 1;
```

zng: `arch/power/adler32_power8.c` lines 135-137

```
            vs2 = vec_add(vsum2, vs2);

            buf += 16;
```

## 20. `5181651efc73` (12 tokens)

Verdict: (none yet)

cf: `src/checksum.rs` lines 247-248

```
    for chunk in chunks {
        crc = crc32_fold_chunk(tables, crc, chunk);
```

zng: `arch/generic/crc32_chorba_c.c` lines 1460-1461

```
        if (algn_diff) {
            c = crc32_braid_internal(c, buf, algn_diff);
```
