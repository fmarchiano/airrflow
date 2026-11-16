process VHVL_RESPLIT {
    tag "$meta.id"
    label "process_medium"
    label 'immcantation'

    conda "bioconda::presto=0.7.8"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/10/103c49b8078f59cf606995618535a988c1055c13f06d060bdb5f642c6b217fc6/data' :
        'biocontainers/presto:0.7.8--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("${meta.id}_VH.fasta"), path("${meta.id}_VL.fasta"), emit: fasta
    path("${meta.id}_resplit.log"), emit: logs

    script:
    """
    resplit_vhvl.py ${reads} -o ${meta.id} 2> ${meta.id}_resplit.log
    """
}
