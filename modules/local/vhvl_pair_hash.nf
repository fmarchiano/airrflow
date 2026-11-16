process VHVL_PAIR_HASH {
    tag "$meta.id"
    label "process_high"
    label 'immcantation'

    conda "bioconda::presto=0.7.8"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/10/103c49b8078f59cf606995618535a988c1055c13f06d060bdb5f642c6b217fc6/data' :
        'biocontainers/presto:0.7.8--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(vh_reads, stageAs: 'vh_*'), path(vl_reads, stageAs: 'vl_*')

    output:
    tuple val(meta), path("${meta.id}_paired.fastq"), emit: reads
    path("${meta.id}_pair_hash.log"), emit: logs

    script:
    """
    pair_hash_vhvl.py ${vh_reads} ${vl_reads} -o ${meta.id}_paired.fastq 2> ${meta.id}_pair_hash.log
    """
}
