"""Tests for classify_paired_reads.py — pure-logic, no I/O."""

import io
import os
import re
import tempfile
import textwrap

import pytest

# Import from the same directory
import sys
sys.path.insert(0, os.path.dirname(__file__))
from classify_paired_reads import parse_motifs, classify_read, revcomp, main


@pytest.fixture
def vhvl_motif_file(tmp_path):
    p = tmp_path / "vhvl.fasta"
    p.write_text(textwrap.dedent("""\
        >VH JH_FR4_core antisense
        GACGGTGACC
        >VH JH_WGQG_CG antisense
        CGCCCCA
        >VH JH_WGQG_GG antisense
        GGCCCCA
        >VL JL_lambda_FR4_core antisense
        GACAGTGACC
        >VL JL_FGXG antisense ~
        CC[TC]TG[ACGT]CC[AG][AG]A
    """))
    return str(p)


@pytest.fixture
def tcrab_motif_file(tmp_path):
    p = tmp_path / "tcrab.fasta"
    p.write_text(textwrap.dedent("""\
        >TRA TRAJ_core antisense ~
        GAC[AC]GTGACC
        >TRB TRBJ_core antisense ~
        GAC[AC]GTGACC[AT]G
        >TRB TRBJ_FGXG antisense ~
        CC[TC]TG[ACGT]CC[AG][AG]A
    """))
    return str(p)


class TestParseMotifs:
    def test_vhvl_has_two_chains(self, vhvl_motif_file):
        motifs, chains = parse_motifs(vhvl_motif_file)
        assert chains == ["VH", "VL"]
        assert len(motifs["VH"]) == 3
        assert len(motifs["VL"]) == 2

    def test_tcrab_has_two_chains(self, tcrab_motif_file):
        motifs, chains = parse_motifs(tcrab_motif_file)
        assert chains == ["TRA", "TRB"]


class TestClassifyRead:
    def test_vh_jh_exact(self, vhvl_motif_file):
        motifs, chains = parse_motifs(vhvl_motif_file)
        seq = "AAAA" + "GACGGTGACC" + "A" * 66
        assert classify_read(seq, motifs, chains) == "VH"

    def test_vh_wgqg(self, vhvl_motif_file):
        motifs, chains = parse_motifs(vhvl_motif_file)
        seq = "AAAA" + "CGCCCCA" + "A" * 69
        assert classify_read(seq, motifs, chains) == "VH"

    def test_vl_lambda(self, vhvl_motif_file):
        motifs, chains = parse_motifs(vhvl_motif_file)
        seq = "AAAA" + "GACAGTGACC" + "A" * 66
        assert classify_read(seq, motifs, chains) == "VL"

    def test_vl_fgxg_regex(self, vhvl_motif_file):
        motifs, chains = parse_motifs(vhvl_motif_file)
        # CCTGACCAAA matches CC[TC]TG[ACGT]CC[AG][AG]A
        seq = "AAAA" + "CCTTGACCAAA" + "A" * 65
        assert classify_read(seq, motifs, chains) == "VL"

    def test_unclassified(self, vhvl_motif_file):
        motifs, chains = parse_motifs(vhvl_motif_file)
        seq = "A" * 80
        assert classify_read(seq, motifs, chains) == "?"

    def test_both_match_more_vh_wins(self, vhvl_motif_file):
        motifs, chains = parse_motifs(vhvl_motif_file)
        # Has both JH_FR4_core + JH_WGQG (2 VH hits) and JL_lambda (1 VL hit)
        seq = "GACGGTGACC" + "CGCCCCA" + "GACAGTGACC" + "A" * 53
        assert classify_read(seq, motifs, chains) == "VH"

    def test_motif_outside_window_ignored(self, vhvl_motif_file):
        motifs, chains = parse_motifs(vhvl_motif_file)
        seq = "A" * 80 + "GACGGTGACC"
        assert classify_read(seq, motifs, chains) == "?"

    def test_tcr_tra(self, tcrab_motif_file):
        motifs, chains = parse_motifs(tcrab_motif_file)
        # GACAGTGACC matches GAC[AC]GTGACC (TRA) but not TRBJ patterns
        seq = "AAAA" + "GACAGTGACC" + "A" * 66
        assert classify_read(seq, motifs, chains) == "TRA"


class TestRevcomp:
    def test_basic(self):
        assert revcomp("ACGT") == "ACGT"
        assert revcomp("AAAA") == "TTTT"
        assert revcomp("ATCG") == "CGAT"


def _write_fastq(path, records):
    """Write list of (header, seq, qual) to a FASTQ file."""
    with open(path, "w") as fh:
        for header, seq, qual in records:
            fh.write(f"@{header}\n{seq}\n+\n{qual}\n")


class TestEndToEnd:
    def test_basic_classification(self, vhvl_motif_file, tmp_path):
        r1 = str(tmp_path / "R1.fastq")
        r2 = str(tmp_path / "R2.fastq")
        prefix = str(tmp_path / "out")

        vh_seq = "GACGGTGACC" + "A" * 70
        vl_seq = "GACAGTGACC" + "A" * 70
        qual = "I" * 80

        # Pair 1: R1=VH, R2=VL — normal pair
        _write_fastq(r1, [("read1", vh_seq, qual)])
        _write_fastq(r2, [("read1", vl_seq, qual)])

        sys.argv = ["classify_paired_reads.py", r1, r2, "--motifs", vhvl_motif_file, "--out-prefix", prefix]
        main()

        with open(f"{prefix}_VH.fastq") as fh:
            vh_content = fh.read()
        with open(f"{prefix}_VL.fastq") as fh:
            vl_content = fh.read()
        assert "@read1" in vh_content
        assert "@read1" in vl_content

    def test_mate_rescue(self, vhvl_motif_file, tmp_path):
        r1 = str(tmp_path / "R1.fastq")
        r2 = str(tmp_path / "R2.fastq")
        prefix = str(tmp_path / "out")

        vh_seq = "GACGGTGACC" + "A" * 70
        unknown_seq = "A" * 80
        qual = "I" * 80

        # R1 is VH, R2 is unclassified → R2 rescued as VL
        _write_fastq(r1, [("read1", vh_seq, qual)])
        _write_fastq(r2, [("read1", unknown_seq, qual)])

        sys.argv = ["classify_paired_reads.py", r1, r2, "--motifs", vhvl_motif_file, "--out-prefix", prefix]
        main()

        with open(f"{prefix}_VH.fastq") as fh:
            assert "@read1" in fh.read()
        with open(f"{prefix}_VL.fastq") as fh:
            assert "@read1" in fh.read()

    def test_chimeric_discarded(self, vhvl_motif_file, tmp_path):
        r1 = str(tmp_path / "R1.fastq")
        r2 = str(tmp_path / "R2.fastq")
        prefix = str(tmp_path / "out")

        vh_seq = "GACGGTGACC" + "A" * 70
        qual = "I" * 80

        # Both reads are VH → chimeric, discarded
        _write_fastq(r1, [("read1", vh_seq, qual)])
        _write_fastq(r2, [("read1", vh_seq, qual)])

        sys.argv = ["classify_paired_reads.py", r1, r2, "--motifs", vhvl_motif_file, "--out-prefix", prefix]
        main()

        with open(f"{prefix}_VH.fastq") as fh:
            assert fh.read() == ""
        with open(f"{prefix}_VL.fastq") as fh:
            assert fh.read() == ""

        stats = open(f"{prefix}_classify_stats.tsv").read()
        assert "chimeric\t2" in stats

    def test_both_unclassified_discarded(self, vhvl_motif_file, tmp_path):
        r1 = str(tmp_path / "R1.fastq")
        r2 = str(tmp_path / "R2.fastq")
        prefix = str(tmp_path / "out")

        unknown_seq = "A" * 80
        qual = "I" * 80

        _write_fastq(r1, [("read1", unknown_seq, qual)])
        _write_fastq(r2, [("read1", unknown_seq, qual)])

        sys.argv = ["classify_paired_reads.py", r1, r2, "--motifs", vhvl_motif_file, "--out-prefix", prefix]
        main()

        with open(f"{prefix}_VH.fastq") as fh:
            assert fh.read() == ""
        with open(f"{prefix}_VL.fastq") as fh:
            assert fh.read() == ""

        stats = open(f"{prefix}_classify_stats.tsv").read()
        assert "unclassified\t2" in stats

    def test_reads_are_revcomped(self, vhvl_motif_file, tmp_path):
        r1 = str(tmp_path / "R1.fastq")
        r2 = str(tmp_path / "R2.fastq")
        prefix = str(tmp_path / "out")

        vh_seq = "GACGGTGACC" + "A" * 70
        vl_seq = "GACAGTGACC" + "C" * 70
        qual = "I" * 80

        _write_fastq(r1, [("read1", vh_seq, qual)])
        _write_fastq(r2, [("read1", vl_seq, qual)])

        sys.argv = ["classify_paired_reads.py", r1, r2, "--motifs", vhvl_motif_file, "--out-prefix", prefix]
        main()

        with open(f"{prefix}_VH.fastq") as fh:
            lines = fh.read().strip().split("\n")
            output_seq = lines[1]
            assert output_seq == revcomp(vh_seq)

    def test_stats_file(self, vhvl_motif_file, tmp_path):
        r1 = str(tmp_path / "R1.fastq")
        r2 = str(tmp_path / "R2.fastq")
        prefix = str(tmp_path / "out")

        vh_seq = "GACGGTGACC" + "A" * 70
        vl_seq = "GACAGTGACC" + "A" * 70
        qual = "I" * 80

        _write_fastq(r1, [("read1", vh_seq, qual), ("read2", vh_seq, qual)])
        _write_fastq(r2, [("read1", vl_seq, qual), ("read2", vh_seq, qual)])

        sys.argv = ["classify_paired_reads.py", r1, r2, "--motifs", vhvl_motif_file, "--out-prefix", prefix]
        main()

        stats = open(f"{prefix}_classify_stats.tsv").read()
        assert "VH\t" in stats
        assert "VL\t" in stats
        assert "total_reads\t" in stats
