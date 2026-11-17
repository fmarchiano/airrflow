#!/usr/bin/env python3
"""Classify paired-end emulsion-linked reads by chain using J-motif patterns.

Generalized port of allovista's infra/split-vhvl-reads.py. Reads a motif FASTA
where each entry's header starts with a chain label (VH, VL, TRA, TRB, ...).
Sequences are literal substring patterns; a trailing ~ on the header line marks
the sequence as a regex instead.

Classification:
  - Search the first 80 bp of each antisense read against all motifs
  - Only chain-A motifs match → chain A; only chain-B → chain B
  - Both chains match → chain with more motif hits wins (tie: first chain in file)
  - Neither → unclassified (?)

Mate rescue: one classified + one ? → unclassified gets opposite chain.
Chimeric discard: both reads same chain → both discarded.
All classified reads are reverse-complemented.

Output:
  {prefix}_{chainA}.fastq  — chain A reads, revcomped
  {prefix}_{chainB}.fastq  — chain B reads, revcomped
  {prefix}_classify_stats.tsv — per-category counts + pair breakdown
"""

import argparse
import gzip
import re
import sys
from collections import Counter

COMP = str.maketrans("ACGTNacgtn", "TGCANtgcan")
SEARCH_WINDOW = 80


def revcomp(seq):
    return seq.translate(COMP)[::-1]


def parse_motifs(path):
    """Parse motif FASTA. Returns {chain: [(pattern_fn, name), ...]} and ordered chain list."""
    motifs = {}
    chains_seen = []
    name = None
    chain = None
    is_regex = False

    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                parts = line[1:].split()
                chain = parts[0]
                name = " ".join(parts[1:]).rstrip("~").strip()
                is_regex = line.rstrip().endswith("~")
                if chain not in motifs:
                    motifs[chain] = []
                    chains_seen.append(chain)
            elif chain is not None:
                seq = line.strip()
                if is_regex:
                    pat = re.compile(seq)
                    motifs[chain].append((lambda w, p=pat: bool(p.search(w)), name))
                else:
                    motifs[chain].append((lambda w, s=seq: s in w, name))

    if len(chains_seen) != 2:
        raise ValueError(f"Motif file must define exactly 2 chains, got {chains_seen}")
    return motifs, chains_seen


def classify_read(seq, motifs, chains):
    """Classify one read. Returns chain label or '?'."""
    window = seq[:SEARCH_WINDOW]
    hits = {}
    for chain in chains:
        count = sum(1 for fn, _ in motifs[chain] if fn(window))
        if count > 0:
            hits[chain] = count

    if len(hits) == 0:
        return "?"
    if len(hits) == 1:
        return next(iter(hits))
    # Both chains matched — prefer the one with more hits; tie → first chain
    max_hits = max(hits.values())
    for chain in chains:
        if hits.get(chain) == max_hits:
            return chain
    return chains[0]


def read_fastq_record(fh):
    header = fh.readline()
    if not header:
        return None
    seq = fh.readline().rstrip("\n")
    plus = fh.readline()
    qual = fh.readline().rstrip("\n")
    return header.rstrip("\n"), seq, plus.rstrip("\n"), qual


def open_fq(path, mode="rt"):
    if path.endswith(".gz"):
        return gzip.open(path, mode)
    return open(path, mode)


def write_record(fh, header, seq, plus, qual):
    fh.write(f"{header}\n{revcomp(seq)}\n{plus}\n{qual[::-1]}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("r1", help="R1 FASTQ (plain or gzipped)")
    parser.add_argument("r2", help="R2 FASTQ (plain or gzipped)")
    parser.add_argument("--motifs", "-m", required=True, help="Motif FASTA file")
    parser.add_argument("--out-prefix", "-o", required=True, help="Output file prefix")
    args = parser.parse_args()

    motifs, chains = parse_motifs(args.motifs)
    chain_a, chain_b = chains
    opposite = {chain_a: chain_b, chain_b: chain_a}

    outs = {
        chain_a: open(f"{args.out_prefix}_{chain_a}.fastq", "w"),
        chain_b: open(f"{args.out_prefix}_{chain_b}.fastq", "w"),
    }

    stats = Counter()
    pair_classes = Counter()

    with open_fq(args.r1) as fh1, open_fq(args.r2) as fh2:
        while True:
            rec1 = read_fastq_record(fh1)
            rec2 = read_fastq_record(fh2)
            if rec1 is None or rec2 is None:
                break

            header1, seq1, plus1, qual1 = rec1
            header2, seq2, plus2, qual2 = rec2

            c1 = classify_read(seq1, motifs, chains)
            c2 = classify_read(seq2, motifs, chains)

            # Mate rescue
            if c1 != "?" and c2 == "?":
                c2 = opposite.get(c1, "?")
            elif c2 != "?" and c1 == "?":
                c1 = opposite.get(c2, "?")

            pair_classes[(c1, c2)] += 1

            # Chimeric: both reads same chain
            if c1 == c2 and c1 != "?":
                stats["chimeric"] += 2
                continue

            # Unclassified: both reads unknown
            if c1 == "?" and c2 == "?":
                stats["unclassified"] += 2
                continue

            for header, seq, plus, qual, cls in [
                (header1, seq1, plus1, qual1, c1),
                (header2, seq2, plus2, qual2, c2),
            ]:
                write_record(outs[cls], header, seq, plus, qual)
                stats[cls] += 1

    for fh in outs.values():
        fh.close()

    total = sum(stats.values())
    with open(f"{args.out_prefix}_classify_stats.tsv", "w") as sf:
        sf.write("category\tcount\tpercent\n")
        for k in [chain_a, chain_b, "chimeric", "unclassified"]:
            pct = 100 * stats[k] / total if total else 0
            sf.write(f"{k}\t{stats[k]}\t{pct:.1f}\n")
        sf.write(f"total_reads\t{total}\t100.0\n")
        sf.write(f"\npair_classification\tcount\n")
        for (c1, c2), n in pair_classes.most_common():
            sf.write(f"R1={c1},R2={c2}\t{n}\n")

    print(f"Done. {total:,} reads processed.", file=sys.stderr)
    for k in [chain_a, chain_b, "chimeric", "unclassified"]:
        print(f"  {k}: {stats[k]:,} ({100*stats[k]/total:.1f}%)" if total else f"  {k}: 0", file=sys.stderr)


if __name__ == "__main__":
    main()
