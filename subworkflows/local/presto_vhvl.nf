include { GUNZIP                as GUNZIP_VHVL                 } from '../../modules/local/gunzip'
include { FASTQC_POSTASSEMBLY   as FASTQC_POSTASSEMBLY_VHVL   } from '../../modules/local/fastqc_postassembly'
include { FASTP                                                } from '../../modules/nf-core/fastp/main'

include { PRESTO_FILTERSEQ_POSTASSEMBLY as PRESTO_FILTERSEQ_VHVL_VH } from '../../modules/local/presto/presto_filterseq_postassembly'
include { PRESTO_FILTERSEQ_POSTASSEMBLY as PRESTO_FILTERSEQ_VHVL_VL } from '../../modules/local/presto/presto_filterseq_postassembly'
include { PRESTO_PARSEHEADERS_METADATA  as PRESTO_PARSEHEADERS_METADATA_VHVL } from '../../modules/local/presto/presto_parseheaders_metadata'
include { PRESTO_COLLAPSESEQ            as PRESTO_COLLAPSESEQ_VHVL  } from '../../modules/local/presto/presto_collapseseq'
include { PRESTO_SPLITSEQ               as PRESTO_SPLITSEQ_VHVL     } from '../../modules/local/presto/presto_splitseq'
include { VHVL_PAIR_HASH                                             } from '../../modules/local/vhvl_pair_hash'
include { VHVL_RESPLIT                                               } from '../../modules/local/vhvl_resplit'


workflow PRESTO_VHVL {
    take:
    ch_reads         // channel: [ val(meta), [ R1, R2 ] ]  R1=VH, R2=VL
    ch_adapter_fasta // channel: [ adapters.fasta ]
    save_trimmed
    filterseq_q

    main:
    ch_versions = channel.empty()

    // Fastp
    save_merged = false
    FASTP (
        ch_reads,
        ch_adapter_fasta,
        save_trimmed,
        save_merged
    )
    ch_versions = ch_versions.mix(FASTP.out.versions)

    // Gunzip paired R1+R2
    ch_gunzip = FASTP.out.reads.map{ meta, reads -> [meta, reads[0], reads[1]] }
    GUNZIP_VHVL ( ch_gunzip )

    // FilterSeq on VH (R1) independently
    ch_vh = GUNZIP_VHVL.out.reads.map{ meta, r1, r2 -> [meta, r1] }
    PRESTO_FILTERSEQ_VHVL_VH ( ch_vh, filterseq_q )

    // FilterSeq on VL (R2) independently
    ch_vl = GUNZIP_VHVL.out.reads.map{ meta, r1, r2 -> [meta, r2] }
    PRESTO_FILTERSEQ_VHVL_VL ( ch_vl, filterseq_q )

    // Pair-hash: intersect IDs, concatenate VH+VL, store VHLEN
    ch_pair_input = PRESTO_FILTERSEQ_VHVL_VH.out.reads
        .join(PRESTO_FILTERSEQ_VHVL_VL.out.reads)
        .map{ meta, vh, vl -> [meta, vh, vl] }
    VHVL_PAIR_HASH ( ch_pair_input )

    // Generate QC stats on paired data
    FASTQC_POSTASSEMBLY_VHVL ( VHVL_PAIR_HASH.out.reads )

    // Annotate metadata (sample_id, subject_id, species, locus)
    PRESTO_PARSEHEADERS_METADATA_VHVL ( VHVL_PAIR_HASH.out.reads )

    // CollapseSeq on concatenated (VH,VL) tuples
    PRESTO_COLLAPSESEQ_VHVL ( PRESTO_PARSEHEADERS_METADATA_VHVL.out.reads )

    // SplitSeq DUPCOUNT >= 2
    PRESTO_SPLITSEQ_VHVL ( PRESTO_COLLAPSESEQ_VHVL.out.reads )

    // Re-split concatenated FASTA back into VH + VL
    VHVL_RESPLIT ( PRESTO_SPLITSEQ_VHVL.out.fasta )

    // Emit VH and VL as separate channel entries for independent IgBLAST
    ch_fasta = VHVL_RESPLIT.out.fasta.flatMap{ meta, vh, vl ->
        def meta_vh = meta.clone()
        meta_vh.sample_id = meta.id
        meta_vh.id = "${meta.id}_VH"
        def meta_vl = meta.clone()
        meta_vl.sample_id = meta.id
        meta_vl.id = "${meta.id}_VL"
        [ [meta_vh, vh], [meta_vl, vl] ]
    }

    emit:
    fasta = ch_fasta
    versions = ch_versions
    fastp_reads_json = FASTP.out.json.collect{ meta, json -> json }
    fastp_reads_html = FASTP.out.html.collect{ meta, html -> html }
    fastqc_postassembly_gz = FASTQC_POSTASSEMBLY_VHVL.out.zip
    presto_filterseq_logs = PRESTO_FILTERSEQ_VHVL_VH.out.logs
    presto_collapseseq_logs = PRESTO_COLLAPSESEQ_VHVL.out.logs.collect()
    presto_splitseq_logs = PRESTO_SPLITSEQ_VHVL.out.logs.collect()
}
