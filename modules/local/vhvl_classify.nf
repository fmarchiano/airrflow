process VHVL_CLASSIFY {
    tag "$meta.id"
    label "process_medium"
    label 'immcantation'

    conda "bioconda::presto=0.7.8"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/10/103c49b8078f59cf606995618535a988c1055c13f06d060bdb5f642c6b217fc6/data' :
        'biocontainers/presto:0.7.8--pyhdfd78af_0' }"

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
