process VHVL_CLASSIFY {
    tag "$meta.id"
    label "process_medium"
    label 'immcantation'

    input:
    tuple val(meta), path(r1), path(r2)
    path(motifs)

    output:
    // ponytail: hardcoded VH/VL — generalize output globs when adding TCR library type
    tuple val(meta), path("${meta.id}_VH.fastq"), path("${meta.id}_VL.fastq"), emit: reads
    path("${meta.id}_classify_stats.tsv"), emit: stats
    path("${meta.id}_classify.log"), emit: logs

    script:
    """
    classify_paired_reads.py ${r1} ${r2} --motifs ${motifs} --out-prefix ${meta.id} 2> ${meta.id}_classify.log
    """
}
