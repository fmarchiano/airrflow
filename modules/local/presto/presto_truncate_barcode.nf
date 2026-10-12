process PRESTO_TRUNCATE_BARCODE {
    tag "$meta.id"
    label "process_low"
    label 'immcantation'

    conda "bioconda::presto=0.7.8"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/10/103c49b8078f59cf606995618535a988c1055c13f06d060bdb5f642c6b217fc6/data' :
        'biocontainers/presto:0.7.8--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(R1), path(R2)
    val(umi_length)

    output:
    tuple val(meta), path("*_R1_trunc.fastq"), path("*_R2_trunc.fastq"), emit: reads

    script:
    // Truncate BARCODE annotation to umi_length characters in FASTQ headers.
    // pRESTo header format: @SEQID FIELD1=VAL1|FIELD2=VAL2|...
    // No-op on reads without BARCODE field.
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
    }' ${R1} > ${meta.id}_R1_trunc.fastq

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
    }' ${R2} > ${meta.id}_R2_trunc.fastq
    """
}
