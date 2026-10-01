# Fragments: zrs vs zng (positive)

Verdicts live in `config/similarity_verdicts.toml` under `[zrs_zng]` keyed by fragment id; allowed values: `RFC-forced`, `idiomatic-inevitable`, `suspicious`.

## 1. `dabc8acdca72` (54 tokens)

Verdict: (none yet)

zrs: `src/crc32/vpclmulqdq.rs` lines 123-130

```
            zmm_crc0 = _mm512_clmulepi64_epi128(zmm_crc0, zmm_fold4, 0x10);
            zmm_crc0 = _mm512_ternarylogic_epi32(zmm_crc0, z0, zmm_crc3, 0x96);

            // zmm_crc0 -> xmm_crc[0, 1, 2, 3]
            *xmm_crc0 = _mm512_extracti32x4_epi32(zmm_crc0, 0);
            *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
            *xmm_crc2 = _mm512_extracti32x4_epi32(zmm_crc0, 2);
            *xmm_crc3 = _mm512_extracti32x4_epi32(zmm_crc0, 3);
```

zng: `arch/x86/crc32_fold_vpclmulqdq_tpl.h` lines 97-104

```
    zmm_crc0 = _mm512_clmulepi64_epi128(zmm_crc0, zmm_fold4, 0x10);
    zmm_crc0 = _mm512_ternarylogic_epi32(zmm_crc0, z0, zmm_crc3, 0x96);

    // zmm_crc0 -> xmm_crc[0, 1, 2, 3]
    *xmm_crc0 = _mm512_extracti32x4_epi32(zmm_crc0, 0);
    *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
    *xmm_crc2 = _mm512_extracti32x4_epi32(zmm_crc0, 2);
    *xmm_crc3 = _mm512_extracti32x4_epi32(zmm_crc0, 3);
```

## 2. `afe189fc7a91` (49 tokens)

Verdict: (none yet)

zrs: `src/adler32.rs` lines 68-73

```
    let mut sum2 = rem * sum1;
    sum2 %= BASE;
    sum1 += (adler2 & 0xffff) + BASE - 1;
    sum2 += ((adler1 >> 16) & 0xffff) + ((adler2 >> 16) & 0xffff) + BASE - rem;

    if sum1 >= BASE {
```

zng: `adler32.c` lines 45-49

```
    sum2 = rem * sum1;
    sum2 %= BASE;
    sum1 += (adler2 & 0xffff) + BASE - 1;
    sum2 += ((adler1 >> 16) & 0xffff) + ((adler2 >> 16) & 0xffff) + BASE - rem;
    if (sum1 >= BASE) sum1 -= BASE;
```

## 3. `78f50b558493` (35 tokens)

Verdict: (none yet)

zrs: `src/crc32/vpclmulqdq.rs` lines 124-129

```
            zmm_crc0 = _mm512_ternarylogic_epi32(zmm_crc0, z0, zmm_crc3, 0x96);

            // zmm_crc0 -> xmm_crc[0, 1, 2, 3]
            *xmm_crc0 = _mm512_extracti32x4_epi32(zmm_crc0, 0);
            *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
            *xmm_crc2 = _mm512_extracti32x4_epi32(zmm_crc0, 2);
```

zng: `arch/x86/crc32_fold_vpclmulqdq_tpl.h` lines 101-104

```
    *xmm_crc0 = _mm512_extracti32x4_epi32(zmm_crc0, 0);
    *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
    *xmm_crc2 = _mm512_extracti32x4_epi32(zmm_crc0, 2);
    *xmm_crc3 = _mm512_extracti32x4_epi32(zmm_crc0, 3);
```

## 4. `78f50b558493` (35 tokens)

Verdict: (none yet)

zrs: `src/crc32/vpclmulqdq.rs` lines 127-130

```
            *xmm_crc0 = _mm512_extracti32x4_epi32(zmm_crc0, 0);
            *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
            *xmm_crc2 = _mm512_extracti32x4_epi32(zmm_crc0, 2);
            *xmm_crc3 = _mm512_extracti32x4_epi32(zmm_crc0, 3);
```

zng: `arch/x86/crc32_fold_vpclmulqdq_tpl.h` lines 98-103

```
    zmm_crc0 = _mm512_ternarylogic_epi32(zmm_crc0, z0, zmm_crc3, 0x96);

    // zmm_crc0 -> xmm_crc[0, 1, 2, 3]
    *xmm_crc0 = _mm512_extracti32x4_epi32(zmm_crc0, 0);
    *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
    *xmm_crc2 = _mm512_extracti32x4_epi32(zmm_crc0, 2);
```

## 5. `ef1dbb00a14f` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512.rs` lines 133-142

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/loongarch/adler32_lasx.c` lines 104-112

```
        vs2 = __lasx_xvadd_w(vs2, vs3);

        adler0 = partial_hsum256(vs1) % BASE;
        adler1 = hsum256(vs2) % BASE;
    }

    adler = adler0 | (adler1 << 16);

    if (len) {
```

## 6. `982fd67bbc7a` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512.rs` lines 133-142

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/x86/adler32_avx2.c` lines 122-165

```
        vs2 = _mm256_add_epi32(vs2, vs3);

        /* The compiler is generating the following sequence for this integer modulus
         * when done the scalar way, in GPRs:

         adler = (s1_unpack[0] % BASE) + (s1_unpack[1] % BASE) + (s1_unpack[2] % BASE) + (s1_unpack[3] % BASE) +
                 (s1_unpack[4] % BASE) + (s1_unpack[5] % BASE) + (s1_unpack[6] % BASE) + (s1_unpack[7] % BASE);

         mov    $0x80078071,%edi // move magic constant into 32 bit register %edi
         ...
         vmovd  %xmm1,%esi // move vector lane 0 to 32 bit register %esi
         mov    %rsi,%rax  // zero-extend this value to 64 bit precision in %rax
         imul   %rdi,%rsi // do a signed multiplication with magic constant and vector element
         shr    $0x2f,%rsi // shift right by 47
         imul   $0xfff1,%esi,%esi // do a signed multiplication with value truncated to 32 bits with 0xfff1
         sub    %esi,%eax // subtract lower 32 bits of original vector value from modified one above
         ...
         // repeats for each element with vpextract instructions

         This is tricky with AVX2 for a number of reasons:
             1.) There's no 64 bit multiplication instruction, but there is a sequence to get there
             2.) There's ways to extend vectors to 64 bit precision, but no simple way to truncate
                 back down to 32 bit precision later (there is in AVX512)
             3.) Full width integer multiplications aren't cheap

         We can, however, do a relatively cheap sequence for horizontal sums.
         Then, we simply do the integer modulus on the resulting 64 bit GPR, on a scalar value. It was
         previously thought that casting to 64 bit precision was needed prior to the horizontal sum, but
         that is simply not the case, as NMAX is defined as the maximum number of scalar sums that can be
         performed on the maximum possible inputs before overflow
         */


         /* In AVX2-land, this trip through GPRs will probably be unavoidable, as there's no cheap and easy
          * conversion from 64 bit integer to 32 bit (needed for the inexpensive modulus with a constant).
          * This casting to 32 bit is cheap through GPRs (just register aliasing). See above for exactly
          * what the compiler is doing to avoid integer divisions. */
         adler0 = partial_hsum256(vs1) % BASE;
         adler1 = hsum256(vs2) % BASE;
    }
```

## 7. `1fa0d710db49` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512.rs` lines 133-142

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/x86/adler32_avx512.c` lines 83-92

```
        vs2 = _mm512_add_epi32(vs2, vs3);

        adler0 = partial_hsum(vs1) % BASE;
        adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
    }

    adler = adler0 | (adler1 << 16);

    /* Process tail (len < 64). */
    if (len) {
```

## 8. `a87861f95a91` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512.rs` lines 133-142

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/x86/adler32_avx512_vnni.c` lines 96-105

```
        vs2 = _mm512_add_epi32(vs2, vs2_1);

        adler0 = partial_hsum(vs1) % BASE;
        adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
    }

    adler = adler0 | (adler1 << 16);

    /* Process tail (len < 64). */
    if (len) {
```

## 9. `a87861f95a91` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512.rs` lines 133-142

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/x86/adler32_avx512_vnni.c` lines 194-203

```
        vs2 = _mm256_add_epi32(vs2, vs2_1);

        adler0 = partial_hsum256(vs1) % BASE;
        adler1 = hsum256(vs2) % BASE;
    }

    adler = adler0 | (adler1 << 16);

    /* Process tail (len < 64). */
    if (len) {
```

## 10. `5f36f859a428` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512_vnni.rs` lines 115-124

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/loongarch/adler32_lasx.c` lines 104-112

```
        vs2 = __lasx_xvadd_w(vs2, vs3);

        adler0 = partial_hsum256(vs1) % BASE;
        adler1 = hsum256(vs2) % BASE;
    }

    adler = adler0 | (adler1 << 16);

    if (len) {
```

## 11. `348b6270dd51` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512_vnni.rs` lines 115-124

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/x86/adler32_avx2.c` lines 122-165

```
        vs2 = _mm256_add_epi32(vs2, vs3);

        /* The compiler is generating the following sequence for this integer modulus
         * when done the scalar way, in GPRs:

         adler = (s1_unpack[0] % BASE) + (s1_unpack[1] % BASE) + (s1_unpack[2] % BASE) + (s1_unpack[3] % BASE) +
                 (s1_unpack[4] % BASE) + (s1_unpack[5] % BASE) + (s1_unpack[6] % BASE) + (s1_unpack[7] % BASE);

         mov    $0x80078071,%edi // move magic constant into 32 bit register %edi
         ...
         vmovd  %xmm1,%esi // move vector lane 0 to 32 bit register %esi
         mov    %rsi,%rax  // zero-extend this value to 64 bit precision in %rax
         imul   %rdi,%rsi // do a signed multiplication with magic constant and vector element
         shr    $0x2f,%rsi // shift right by 47
         imul   $0xfff1,%esi,%esi // do a signed multiplication with value truncated to 32 bits with 0xfff1
         sub    %esi,%eax // subtract lower 32 bits of original vector value from modified one above
         ...
         // repeats for each element with vpextract instructions

         This is tricky with AVX2 for a number of reasons:
             1.) There's no 64 bit multiplication instruction, but there is a sequence to get there
             2.) There's ways to extend vectors to 64 bit precision, but no simple way to truncate
                 back down to 32 bit precision later (there is in AVX512)
             3.) Full width integer multiplications aren't cheap

         We can, however, do a relatively cheap sequence for horizontal sums.
         Then, we simply do the integer modulus on the resulting 64 bit GPR, on a scalar value. It was
         previously thought that casting to 64 bit precision was needed prior to the horizontal sum, but
         that is simply not the case, as NMAX is defined as the maximum number of scalar sums that can be
         performed on the maximum possible inputs before overflow
         */


         /* In AVX2-land, this trip through GPRs will probably be unavoidable, as there's no cheap and easy
          * conversion from 64 bit integer to 32 bit (needed for the inexpensive modulus with a constant).
          * This casting to 32 bit is cheap through GPRs (just register aliasing). See above for exactly
          * what the compiler is doing to avoid integer divisions. */
         adler0 = partial_hsum256(vs1) % BASE;
         adler1 = hsum256(vs2) % BASE;
    }
```

## 12. `b63c9fe2dd81` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512_vnni.rs` lines 115-124

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/x86/adler32_avx512.c` lines 83-92

```
        vs2 = _mm512_add_epi32(vs2, vs3);

        adler0 = partial_hsum(vs1) % BASE;
        adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
    }

    adler = adler0 | (adler1 << 16);

    /* Process tail (len < 64). */
    if (len) {
```

## 13. `d0cc23f89594` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512_vnni.rs` lines 115-124

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/x86/adler32_avx512_vnni.c` lines 96-105

```
        vs2 = _mm512_add_epi32(vs2, vs2_1);

        adler0 = partial_hsum(vs1) % BASE;
        adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
    }

    adler = adler0 | (adler1 << 16);

    /* Process tail (len < 64). */
    if (len) {
```

## 14. `d0cc23f89594` (34 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx512_vnni.rs` lines 115-124

```
                vs2 = _mm512_add_epi32(vs2, vs2_1);

                adler0 = partial_hsum(vs1) % BASE;
                adler1 = _mm512_reduce_add_epu32(vs2) % BASE;
            }

            adler = adler0 | (adler1 << 16);

            /* Process tail (len < 64). */
            if !src.is_empty() {
```

zng: `arch/x86/adler32_avx512_vnni.c` lines 194-203

```
        vs2 = _mm256_add_epi32(vs2, vs2_1);

        adler0 = partial_hsum256(vs1) % BASE;
        adler1 = hsum256(vs2) % BASE;
    }

    adler = adler0 | (adler1 << 16);

    /* Process tail (len < 64). */
    if (len) {
```

## 15. `5d8abec91746` (25 tokens)

Verdict: (none yet)

zrs: `src/crc32/vpclmulqdq.rs` lines 124-128

```
            zmm_crc0 = _mm512_ternarylogic_epi32(zmm_crc0, z0, zmm_crc3, 0x96);

            // zmm_crc0 -> xmm_crc[0, 1, 2, 3]
            *xmm_crc0 = _mm512_extracti32x4_epi32(zmm_crc0, 0);
            *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
```

zng: `arch/x86/crc32_fold_vpclmulqdq_tpl.h` lines 102-104

```
    *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
    *xmm_crc2 = _mm512_extracti32x4_epi32(zmm_crc0, 2);
    *xmm_crc3 = _mm512_extracti32x4_epi32(zmm_crc0, 3);
```

## 16. `5d8abec91746` (25 tokens)

Verdict: (none yet)

zrs: `src/crc32/vpclmulqdq.rs` lines 128-130

```
            *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
            *xmm_crc2 = _mm512_extracti32x4_epi32(zmm_crc0, 2);
            *xmm_crc3 = _mm512_extracti32x4_epi32(zmm_crc0, 3);
```

zng: `arch/x86/crc32_fold_vpclmulqdq_tpl.h` lines 98-102

```
    zmm_crc0 = _mm512_ternarylogic_epi32(zmm_crc0, z0, zmm_crc3, 0x96);

    // zmm_crc0 -> xmm_crc[0, 1, 2, 3]
    *xmm_crc0 = _mm512_extracti32x4_epi32(zmm_crc0, 0);
    *xmm_crc1 = _mm512_extracti32x4_epi32(zmm_crc0, 1);
```

## 17. `87375ec87b3b` (24 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx2.rs` lines 132-138

```
            vs2 = _mm256_add_epi32(vsum2, vs2);
            vs1_0 = vs1;
        }

        /* Defer the multiplication with 32 to outside of the loop */
        vs3 = _mm256_slli_epi32(vs3, 5);
        vs2 = _mm256_add_epi32(vs2, vs3);
```

zng: `arch/loongarch/adler32_lasx.c` lines 98-104

```
            vs2 = __lasx_xvadd_w(vsum2, vs2);
            vs1_0 = vs1;
        }

        /* Defer the multiplication with 32 to outside of the loop */
        vs3 = __lasx_xvslli_w(vs3, 5);
        vs2 = __lasx_xvadd_w(vs2, vs3);
```

## 18. `330bfb297371` (24 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx2.rs` lines 132-138

```
            vs2 = _mm256_add_epi32(vsum2, vs2);
            vs1_0 = vs1;
        }

        /* Defer the multiplication with 32 to outside of the loop */
        vs3 = _mm256_slli_epi32(vs3, 5);
        vs2 = _mm256_add_epi32(vs2, vs3);
```

zng: `arch/x86/adler32_avx2.c` lines 116-122

```
            vs2 = _mm256_add_epi32(vsum2, vs2);
            vs1_0 = vs1;
        }

        /* Defer the multiplication with 32 to outside of the loop */
        vs3 = _mm256_slli_epi32(vs3, 5);
        vs2 = _mm256_add_epi32(vs2, vs3);
```

## 19. `39c1747b9096` (24 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx2.rs` lines 132-138

```
            vs2 = _mm256_add_epi32(vsum2, vs2);
            vs1_0 = vs1;
        }

        /* Defer the multiplication with 32 to outside of the loop */
        vs3 = _mm256_slli_epi32(vs3, 5);
        vs2 = _mm256_add_epi32(vs2, vs3);
```

zng: `arch/x86/adler32_avx512.c` lines 78-83

```
            vs2 = _mm512_add_epi32(vsum2, vs2);
            vs1_0 = vs1;
        }

        vs3 = _mm512_slli_epi32(vs3, 6);
        vs2 = _mm512_add_epi32(vs2, vs3);
```

## 20. `a9f6b3a3a4de` (24 tokens)

Verdict: (none yet)

zrs: `src/adler32/avx2.rs` lines 132-138

```
            vs2 = _mm256_add_epi32(vsum2, vs2);
            vs1_0 = vs1;
        }

        /* Defer the multiplication with 32 to outside of the loop */
        vs3 = _mm256_slli_epi32(vs3, 5);
        vs2 = _mm256_add_epi32(vs2, vs3);
```

zng: `arch/x86/adler32_ssse3.c` lines 137-142

```
            vs2 = _mm_add_epi32(vsum2, vs2);
            vs1_0 = vs1;
        }

        vs3 = _mm_slli_epi32(vs3, 4);
        vs2 = _mm_add_epi32(vs2, vs3);
```
