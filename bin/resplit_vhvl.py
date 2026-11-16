#!/usr/bin/env python3
"""
Re-split concatenated VH+VL FASTA/FASTQ back into separate VH and VL files.

Reads the output of pair-hash-vhvl.py after CollapseSeq + SplitSeq and splits
each record using the VHLEN annotation in the header.

Supports both FASTQ and FASTA input (SplitSeq outputs multi-line FASTA).

Usage:
    python3 resplit-vhvl.py paired_atleast-2.fasta --out-prefix sample
"""

import argparse
import gzip
import sys

SEPARATOR_LEN = 0


def open_fq(path, mode="rt"):
    if path.endswith(".gz"):
        return gzip.open(path, mode)
    return open(path, mode)


def parse_vhlen(header):
    for field in header.split("|"):
        if field.startswith("VHLEN="):
            return int(field.split("=", 1)[1])
    return None


def strip_vhlen(header):
    parts = header.split("|")
    parts = [p for p in parts if not p.startswith("VHLEN=")]
    return "|".join(parts)


def read_fasta_records(fh):
    """Yield (header, seq) from multi-line FASTA."""
    header = None
    seq_parts = []
    for line in fh:
        line = line.rstrip("\n")
        if line.startswith(">"):
            if header is not None:
                yield header, "".join(seq_parts)
            header = line
            seq_parts = []
        else:
            seq_parts.append(line)
    if header is not None:
        yield header, "".join(seq_parts)


def read_fastq_records(fh):
    """Yield (header, seq, qual) from FASTQ."""
    while True:
        header = fh.readline()
        if not header:
            return
        seq = fh.readline().rstrip("\n")
        fh.readline()  # +
        qual = fh.readline().rstrip("\n")
        yield header.rstrip("\n"), seq, qual


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="Concatenated FASTA/FASTQ from pair-hash-vhvl.py")
    parser.add_argument("--out-prefix", "-o", required=True, help="Output prefix")
    args = parser.parse_args()

    is_fasta = not args.input.rstrip(".gz").endswith((".fastq", ".fq"))
    ext = "fasta" if is_fasta else "fastq"

    vh_path = f"{args.out_prefix}_VH.{ext}"
    vl_path = f"{args.out_prefix}_VL.{ext}"

    count = 0
    errors = 0

    with open_fq(args.input) as in_fh, \
         open(vh_path, "w") as vh_fh, open(vl_path, "w") as vl_fh:

        if is_fasta:
            for header, seq in read_fasta_records(in_fh):
                vhlen = parse_vhlen(header)
                if vhlen is None:
                    errors += 1
                    if errors <= 3:
                        print(f"WARNING: no VHLEN in header: {header[:80]}", file=sys.stderr)
                    continue
                clean_header = strip_vhlen(header)
                vh_seq = seq[:vhlen]
                vl_seq = seq[vhlen + SEPARATOR_LEN:]
                vh_fh.write(f"{clean_header}\n{vh_seq}\n")
                vl_fh.write(f"{clean_header}\n{vl_seq}\n")
                count += 1
        else:
            for header, seq, qual in read_fastq_records(in_fh):
                vhlen = parse_vhlen(header)
                if vhlen is None:
                    errors += 1
                    if errors <= 3:
                        print(f"WARNING: no VHLEN in header: {header[:80]}", file=sys.stderr)
                    continue
                clean_header = strip_vhlen(header)
                vh_seq = seq[:vhlen]
                vl_seq = seq[vhlen + SEPARATOR_LEN:]
                vh_qual = qual[:vhlen]
                vl_qual = qual[vhlen + SEPARATOR_LEN:]
                vh_fh.write(f"{clean_header}\n{vh_seq}\n+\n{vh_qual}\n")
                vl_fh.write(f"{clean_header}\n{vl_seq}\n+\n{vl_qual}\n")
                count += 1

    print(f"Split {count:,} records into {vh_path} and {vl_path}", file=sys.stderr)
    if errors:
        print(f"Skipped {errors:,} records without VHLEN", file=sys.stderr)


if __name__ == "__main__":
    main()
