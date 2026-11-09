process PRESTO_FILTERSEQ_SINGLE {
    tag "$meta.id"
    label "process_medium"
    label 'immcantation'

    conda "bioconda::presto=0.7.8"
    container "${ workflow.containerEngine == 'singularity' && !task.ext.singularity_pull_docker_container ?
        'https://community-cr-prod.seqera.io/docker/registry/v2/blobs/sha256/10/103c49b8078f59cf606995618535a988c1055c13f06d060bdb5f642c6b217fc6/data' :
        'biocontainers/presto:0.7.8--pyhdfd78af_0' }"

    input:
    tuple val(meta), path(R1)
    val filterseq_q

    output:
    tuple val(meta), path("*R1_quality-pass.fastq") ,  emit: reads
    path "*_command_log_R1.txt" , emit: logs
    tuple val("${task.process}"), val('presto'), eval('FilterSeq.py --version | grep -o "[0-9][0-9.]*" | head -n 1'), emit: versions_presto, topic: versions
    path "*.tab" , emit: log_tab

    script:
    """
    FilterSeq.py quality -s $R1 -q ${filterseq_q} --outname ${meta.id}_R1 --log ${R1.baseName}_R1.log --nproc ${task.cpus} > ${meta.id}_command_log_R1.txt
    ParseLog.py -l ${R1.baseName}_R1.log -f ID QUALITY

    """
}
