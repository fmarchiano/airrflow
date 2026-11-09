process RENAME_FASTQ_SINGLE {
    tag "$meta.id"
    label 'process_low'

    conda "conda-forge::biopython=1.81"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://depot.galaxyproject.org/singularity/biopython:1.81' :
        'biocontainers/biopython:1.81' }"

    input:
    tuple val(meta), path(R1)

    output:
    tuple val(meta), path('*_R1.fastq.gz')   , emit: reads

    script:
    """
    mv "${R1}" "${meta.id}_R1.fastq.gz"
    """
}
