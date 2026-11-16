# airrflow -- AlloVista fork

Custom fork of [nf-core/airrflow](https://github.com/nf-core/airrflow) for the AlloVista platform.

For full pipeline documentation, usage, and parameter reference see the upstream repo: <https://nf-co.re/airrflow>

## Run modes: paired-end and single-end

The library layout is selected with `--single_end` (default `false`) and `--library_generation_method`. The modes differ only in pRESTO pre-processing. From VDJ annotation onward they are identical.

| | Paired-end (default) | Single-end (`--single_end true`) | VH:VL (`--library_generation_method vhvl`) |
|---|---|---|---|
| Input | R1 + R2 FASTQ | R1 FASTQ only | R1 (VH) + R2 (VL) FASTQ |
| Read assembly | `AssemblePairs` merges R1/R2 | none | none (chains are independent) |
| Primer masking | C and V both required (order set by `--cprimer_position`) | V required (5'); C **best-effort** (3', reads kept even without a match) | **skipped** (no primers) |
| Collapse | per-sequence | per-sequence | **pair-level** — VH+VL concatenated before CollapseSeq |
| ParseHeaders | `C_PRIMER` + `V_PRIMER` | single `PRIMER` field | metadata only |
| Output | single FASTA | single FASTA | two FASTAs (VH + VL), separate IgBLAST |

The diagrams show the sans-UMI path (`library_generation_method = specific_pcr`). With UMIs, both modes add barcode extraction and `BuildConsensus` before primer masking. Paired-end UMI also adds `PairSeq` and `ClusterSets`.

### Paired-end

```mermaid
flowchart TD
    A[R1 + R2 FASTQ] --> B[FASTP<br/>adapter & quality trim]
    B --> C[GUNZIP]
    C --> D[AssemblePairs<br/>merge R1/R2 into one read]
    D --> E[FilterSeq<br/>quality filter]
    E --> F["MaskPrimers FWD<br/>C primers (cprimer_position=R1)<br/>or V primers (R2)"]
    F --> G["MaskPrimers REV<br/>the other primer set"]
    G --> H[ParseHeaders<br/>C_PRIMER / V_PRIMER + metadata]
    H --> I[CollapseSeq<br/>dedupe identical sequences, DUPCOUNT]
    I --> J[SplitSeq<br/>keep DUPCOUNT >= splitseq_min_count]
    J --> K[[Shared downstream]]
```

### Single-end

```mermaid
flowchart TD
    A[R1 FASTQ] --> B[FASTP<br/>adapter & quality trim]
    B --> C[GUNZIP]
    C --> E[FilterSeq<br/>quality filter]
    E --> F["MaskPrimers FWD<br/>V primers at 5'<br/>non-matching reads dropped"]
    F --> G["MaskPrimers BESTEFF<br/>C primers at 3' (revpr)<br/>pass + fail reads both kept"]
    G --> H[ParseHeaders<br/>PRIMER + metadata]
    H --> I[CollapseSeq<br/>dedupe identical sequences, DUPCOUNT]
    I --> J[SplitSeq<br/>keep DUPCOUNT >= splitseq_min_count]
    J --> K[[Shared downstream]]
```

### VH:VL paired

```mermaid
flowchart TD
    A[R1=VH + R2=VL FASTQ] --> B[FASTP<br/>adapter & quality trim]
    B --> C[GUNZIP]
    C --> D1[FilterSeq VH<br/>quality filter]
    C --> D2[FilterSeq VL<br/>quality filter]
    D1 --> E["pair-hash<br/>intersect IDs, concat VH+VL<br/>store VHLEN in header"]
    D2 --> E
    E --> F[ParseHeaders<br/>metadata only]
    F --> G["CollapseSeq<br/>dedupe identical (VH,VL) tuples"]
    G --> H[SplitSeq<br/>keep DUPCOUNT >= splitseq_min_count]
    H --> I["resplit<br/>split back into VH + VL FASTA<br/>using VHLEN"]
    I --> J1[VH FASTA]
    I --> J2[VL FASTA]
    J1 --> K[[Shared downstream — IgBLAST VH]]
    J2 --> L[[Shared downstream — IgBLAST VL]]
```

### Shared downstream (all modes)

```mermaid
flowchart TD
    A[SplitSeq output FASTA] --> B[AssignGenes<br/>IgBLAST]
    B --> C[MakeDb<br/>AIRR table]
    C --> D[Filter by alignment quality]
    D --> E[ParseDb split<br/>productive only]
    E --> F[Filter junction length mod 3]
    F --> G[Add sample metadata]
    G --> H[CreateGermlines / RemoveChimeric / DetectContamination<br/>optional]
    H --> I[Collapse duplicates]
    I --> J[Clonal analysis & reports]
```

## Customizations

- **VH:VL paired sequencing** -- `--library_generation_method vhvl` for OE-RT-PCR linked VH:VL data (e.g. DeKosky method). R1=VH, R2=VL (pre-split, no primers). FilterSeq runs on each chain independently, then pair-hash concatenates VH+VL for pair-level CollapseSeq (preserving biological pairing). After SplitSeq, resplit produces separate VH and VL FASTAs for independent IgBLAST. Paired sequences share the same `sequence_id` for downstream joining.

- **Single-end support** -- `--single_end` runs a pRESTO branch without pair assembly, with best-effort 3' C-primer masking so reads that miss the C primer are kept.

- **AWS Batch (Fargate) execution profile** -- `aws_batch` and `local` config profiles for Fargate Spot with automatic retries, Wave-augmented containers, and Seqera Platform integration.
- **UMI auto-detect mode (`umi_length = -1`)** -- bypasses explicit UMI offset arithmetic when the offset is already embedded in the primer start position, while still running the full UMI consensus workflow.
- **Barcode truncation step** -- new `PRESTO_TRUNCATE_BARCODE` process trims BARCODE annotations to the declared UMI length after MaskPrimers align, removing stagger contamination before consensus building.
- **Primer field naming** -- MaskPrimers annotates both forward and reverse primer hits under the unified field `PRIMER` (was `FWD_PRIMER` / `REV_PRIMER`).
- **Configurable SplitSeq minimum count** -- the duplicate/consensus count threshold is exposed as `--splitseq_min_count` (default 2).
- **CHANGEO_ASSIGNGENES resource boost** -- IgBLAST gene assignment gets dedicated resources (4 CPUs, 16 GB) and retry-on-failure.
- **`specific_pcr` library method fix** -- correctly passes `umi_length = 0` downstream when `library_generation_method` is `specific_pcr`.
