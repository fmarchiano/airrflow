process PRESTO_TRUNCATE_BARCODE_SINGLE {
    tag "$meta.id"
    label "process_low"
    label 'immcantation'

    conda "bioconda::presto=0.7.8"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/10/103c49b8078f59cf606995618535a988c1055c13f06d060bdb5f642c6b217fc6/data' :
        'biocontainers/presto:0.7.8--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(R1)
    val(umi_length)

    output:
    tuple val(meta), path("*_trunc.fastq"), emit: reads

    script:
    """
    awk -v len=${umi_length} '{
        if (NR%4==1) {
            while (match(\$0, /BARCODE=[^|]*/)) {
                val = substr(\$0, RSTART+8, RLENGTH-8)
                if (length(val) > len) {
                    \$0 = substr(\$0, 1, RSTART+7) substr(val, 1, len) substr(\$0, RSTART+RLENGTH)
                }
                break
            }
        }
        print
    }' ${R1} > ${meta.id}_trunc.fastq
    """
}
