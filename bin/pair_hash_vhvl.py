#!/usr/bin/env python3
"""
Concatenate paired VH + VL FASTQs into a single FASTQ for pair-level CollapseSeq.

Reads VH and VL post-FilterSeq FASTQs and outputs a single FASTQ where each
record is VH_seq + VL_seq (no separator). Only reads present in BOTH files are
output (FilterSeq may drop different reads from each chain). The VH length is
stored as VHLEN=N in the pRESTO header annotation so resplit-vhvl.py can undo it.

Usage:
    python3 pair-hash-vhvl.py VH_primers-pass.fastq VL_primers-pass.fastq -o paired.fastq
"""

import argparse
import gzip
import sys

SEPARATOR = ""
SEP_QUAL = ""


def open_fq(path, mode="rt"):
    if path.endswith(".gz"):
        return gzip.open(path, mode)
    return open(path, mode)


def read_record(fh):
    header = fh.readline()
    if not header:
        return None
    seq = fh.readline().rstrip("\n")
    plus = fh.readline()
    qual = fh.readline().rstrip("\n")
    return header.rstrip("\n"), seq, plus.rstrip("\n"), qual


def parse_read_id(header):
    return header.split()[0]


def index_fastq(path):
    """Load all records into a dict keyed by read ID."""
    idx = {}
    with open_fq(path) as fh:
        while True:
            rec = read_record(fh)
            if rec is None:
                break
            rid = parse_read_id(rec[0])
            idx[rid] = rec
    return idx


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vh", help="VH post-MaskPrimers FASTQ")
    parser.add_argument("vl", help="VL post-MaskPrimers FASTQ")
    parser.add_argument("-o", "--output", required=True, help="Output concatenated FASTQ")
    args = parser.parse_args()

    out_open = gzip.open if args.output.endswith(".gz") else open
    out_mode = "wt" if args.output.endswith(".gz") else "w"

    print("Indexing VL file...", file=sys.stderr)
    vl_idx = index_fastq(args.vl)
    print(f"  {len(vl_idx):,} VL records indexed", file=sys.stderr)

    paired = 0
    vh_only = 0

    print("Streaming VH file and pairing...", file=sys.stderr)
    with open_fq(args.vh) as vh_fh, out_open(args.output, out_mode) as out_fh:
        while True:
            vh = read_record(vh_fh)
            if vh is None:
                break

            vh_id = parse_read_id(vh[0])
            vl = vl_idx.pop(vh_id, None)
            if vl is None:
                vh_only += 1
                continue

            concat_seq = vh[1] + SEPARATOR + vl[1]
            concat_qual = vh[3] + SEP_QUAL + vl[3]
            header = vh[0] + f"|VHLEN={len(vh[1])}"

            out_fh.write(f"{header}\n{concat_seq}\n+\n{concat_qual}\n")
            paired += 1

    vl_only = len(vl_idx)
    total = paired + vh_only + vl_only
    print(f"Done. {paired:,} paired ({100*paired/total:.1f}%), "
          f"{vh_only:,} VH-only, {vl_only:,} VL-only dropped", file=sys.stderr)


if __name__ == "__main__":
    main()
