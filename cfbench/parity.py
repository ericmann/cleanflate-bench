"""The SPEC 2.4 feature-parity note that accompanies every table and figure."""

PARITY_NOTE = (
    "Parity note: cleanflate implements decompression only, with no SIMD, no unsafe and no C ABI; "
    "the comparators implement compression and some have SIMD paths, hardware CRC and ABI "
    "compatibility, so no comparison here is apples-to-apples."
)


def with_context(machine: str, variant: str) -> str:
    """The parity note followed by the machine and build-variant labels."""
    return f"{PARITY_NOTE} Machine {machine}, variant {variant}."
