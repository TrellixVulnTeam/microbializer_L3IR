"""
script_name.py /Users/Oren/Dropbox/Projects/microbializer/data_for_test_cds/ /Users/Oren/Dropbox/Projects/microbializer/output_examples/mock_output/ orenavram@gmail.com -q pupko
"""


def notify_admin(meta_output_dir, meta_output_url, run_number, CONSTS):
    email = 'NO_EMAIL'
    user_email_path = os.path.join(meta_output_dir, 'user_email.txt')
    if os.path.exists(user_email_path):
        with open(user_email_path) as f:
            email = f.read().rstrip()
    error_log_path = 'NO_ERROR_LOG'
    tmp = [file for file in os.listdir(meta_output_dir) if file.endswith('.err')]
    if len(tmp) > 0:
        error_log_path = tmp[0]
    # Send me a notification email every time there's a failure
    send_email(smtp_server=CONSTS.SMTP_SERVER,
               sender=CONSTS.ADMIN_EMAIL,
               receiver=CONSTS.OWNER_EMAIL,
               subject=f'{CONSTS.WEBSERVER_NAME} job {run_number} by {email} has been failed: ',
               content=f"{email}\n\n{os.path.join(meta_output_url, 'output.html')}\n\n"
               f"{os.path.join(meta_output_url, 'cgi_debug.txt')}\n\n"
               f"{os.path.join(meta_output_url, error_log_path)}\n\n"
               f"{os.path.join(meta_output_dir, error_log_path)}")

def edit_progress(output_html_path, progress=None, active=True):
    result = ''
    with open(output_html_path) as f:
        for line in f:
            if 'progress-bar' in line:
                if progress:
                    line = line.split('style')[0]  # <div class="progress-bar ... style="width:0%">\n
                    line += f'style="width:{progress}%">\n'
                if not active:
                    line = line.replace(' active', '')  # <div class="progress-bar progress-bar-striped bg-success active" ...
            result += line

    with open(output_html_path, 'w') as f:
        f.write(result)

def add_results_to_final_dir(source, final_output_dir):
    dest = os.path.join(final_output_dir, os.path.split(source)[1])
    logger.info(f'Moving {source} TO {dest}')

    try:
        #shutil.move(source, dest) # TODO: change to move!!
        shutil.copytree(source, dest)
    except FileExistsError:
        pass
    return dest


try:
    import argparse
    import sys
    import os
    import tarfile
    import shutil

    print(os.getcwd())
    print(f'sys.path is\n{sys.path}')

    if os.path.exists('/bioseq'):  # remote run
        remote_run = True
        sys.path.append('/bioseq/microbializer/auxiliaries')
        sys.path.append('/bioseq/microbializer/cgi')
        sys.path.append('/bioseq/bioSequence_scripts_and_constants/') #ADD file_writer
    else:
        # local run
        remote_run = False
        sys.path.append('../auxiliaries')
        sys.path.append('../cgi')

    print(f'sys.path is\n{sys.path}')

    import file_writer #ADD file_writer
    from email_sender import send_email
    from pipeline_auxiliaries import *
    from plots_generator import *

    import WEBSERVER_CONSTANTS as CONSTS

    from html_editor import edit_success_html, edit_failure_html

    start = time()

    parser = argparse.ArgumentParser()
    parser.add_argument('contigs_dir', help='path to a folder with the genomic sequences. This folder may be zipped, as well the files in it.',
                        type=lambda path: path.rstrip('/') if os.path.exists(path) else parser.error(f'{path} does not exist!'))
    parser.add_argument('output_dir', help='directory where the output files will be written to',
                        type=lambda path: path.rstrip('/'))
    parser.add_argument('email', help='A notification will be sent once the pipeline is done',
                        default=CONSTS.OWNER_EMAIL)
    parser.add_argument('--identity_cutoff', default=80, type=lambda x: eval(x),
                        help='minimum required percent of identity level (lower values will be filtered out)')
    parser.add_argument('--e_value_cutoff', default=0.01, type=lambda x: eval(x), # if 0 <= eval(x) <= 100 else parser.error(f"Can't use {x} as percent!"),
                        help='maxmimum permitted e-value (0 <= e_value_cutoff <= 1; higher values will be filtered out).')
    parser.add_argument('--core_minimal_percentage', default=99.9, type=lambda x: eval(x), # if 0 <= eval(x) <= 100 else parser.error(f"Can't use {x} as percent!"),
                        help='the minimum required percent of gene members that is needed to be considered a core gene. For example: (1) 100 means that for a gene to be considered core, all strains should have a member in the group.\n(2) 50 means that for a gene to be considered core, at least half of the strains should have a member in the group.\n(3) 0 means that every gene should be considered as a core gene.')
    parser.add_argument('-q', '--queue_name', help='The cluster to which the job(s) will be submitted to',
                        choices=['pupkoweb', 'pupko', 'itaym', 'lilach', 'bioseq', 'bental', 'oren.q', 'bioseq20.q'], default='pupkoweb')
    parser.add_argument('--dummy_delimiter',
                        help='The queue does not "like" very long commands. A dummy delimiter is used to break each row into different commands of a single job',
                        default='!@#')
    parser.add_argument('--src_dir', help='source code directory', type=lambda s: s.rstrip('/'), default='/bioseq/microbializer/pipeline')
    parser.add_argument('-v', '--verbose', help='Increase output verbosity', action='store_true')
    args = parser.parse_args()

    import logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('main')

    logger.info(args)

    create_dir(args.output_dir)

    meta_output_dir = os.path.join(os.path.split(args.output_dir)[0])
    logger.info(f'meta_output_dir is: {meta_output_dir}')

    run_number = os.path.join(os.path.split(meta_output_dir)[1])
    logger.info(f'run_number is {run_number}')

    output_html_path = os.path.join(meta_output_dir, 'output.html')
    logger.info(f'output_html_path is {output_html_path}')

    output_url = os.path.join(CONSTS.WEBSERVER_RESULTS_URL, run_number, 'output.html')
    logger.info(f'output_url is {output_url}')

    meta_output_url = os.path.join(CONSTS.WEBSERVER_RESULTS_URL, run_number)

    error_file_path = os.path.join(args.output_dir, 'error.txt')

    tmp_dir = os.path.join(args.output_dir, 'tmp_dir')
    create_dir(tmp_dir)

    done_files_dir = os.path.join(args.output_dir, 'done')
    create_dir(done_files_dir)

    data_path = args.contigs_dir
    logger.info(f'data_path is: {data_path}')

    # extract zip and detect data folder
    if not os.path.isdir(data_path):
        unzipping_data_path = os.path.join(meta_output_dir, 'data')
        if tarfile.is_tarfile(data_path):
            with tarfile.open(data_path, 'r:gz') as f:
                f.extractall(path=unzipping_data_path) # unzip tar folder to parent dir
            # data_path = data_path.split('.tar')[0] # e.g., /groups/pupko/orenavr2/microbializer/example_data.tar.gz
            # logger.info(f'Updated data_path is:\n{data_path}')
        else:
            shutil.unpack_archive(data_path, extract_dir=unzipping_data_path) # unzip tar folder to parent dir
            # data_path = os.path.join(meta_output_dir, 'data') # e.g., /groups/pupko/orenavr2/microbializer/example_data.tar.gz
            # logger.info(f'Updated data_path is:\n{data_path}')

        file = [x for x in os.listdir(unzipping_data_path) if not x.startswith(('_', '.'))][0]
        logger.info(f'first file in {unzipping_data_path} is:\n{file}')
        if os.path.isdir(os.path.join(unzipping_data_path, file)):
            data_path = os.path.join(unzipping_data_path, file)
            file = [x for x in os.listdir(data_path) if not x.startswith(('_', '.'))][0]
            if os.path.isdir(os.path.join(data_path, file)):
                assert ValueError('More than a 2-levels folder...')
        else:
            data_path = unzipping_data_path

    logger.info(f'Updated data_path is:\n{data_path}')
    logger.info(f'data_path contains:\n{os.listdir(data_path)}')

    for file in os.listdir(data_path):
        file_path = os.path.join(data_path, file)
        if file_path.endswith('gz'): # gunzip gz files in $data_path if any
            subprocess.run(f'gunzip -f {file_path}', shell=True)


    # 1.	extract_orfs_sequences.py
    # Input: (1) an input path for a fasta file with contigs/full genome (2) an output file path (with a suffix as follows: i_genes.fasta. especially relevant for the wrapper).
    # Output: a fasta file where under each header, there’s a single gene.
    # Can be parallelized on cluster
    # Prodigal ignores newlines in the middle of a sequence, namely, >bac1\nAAA\nAA\nTTT >bac1\nAAAAATTT will be analyzed identically.
    step = '01'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_ORFs'
    script_path = os.path.join(args.src_dir, 'extract_orfs_sequences.py')
    num_of_expected_results = 0
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_extract_orfs.txt')
    if not os.path.exists(done_file_path):
        logger.info('Extracting ORFs...')
        for fasta_file in os.listdir(data_path):
            if fasta_file.startswith(('.', '_')):
                logger.warning(f'Skipping system file: {os.path.join(data_path, fasta_file)}')
                continue
            fasta_file_prefix = os.path.splitext(fasta_file)[0]
            output_file_name = f'{fasta_file_prefix}.{dir_name}'
            output_coord_name = f'{fasta_file_prefix}.gene_coordinates'
            params = [os.path.join(data_path, fasta_file),
                      os.path.join(pipeline_step_output_dir, output_file_name),
                      os.path.join(pipeline_step_output_dir, output_coord_name)] #Shir - path to translated sequences file
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                 queue_name=args.queue_name, required_modules_as_list=[CONSTS.PRODIGAL])
            num_of_expected_results += 1
        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=10)


    # 2.  create_mmseqs2_DB.py
    # Input: path to gene file to create DB from
    # Output: DB of the input file for mmseqs2
    # Can be parallelized on cluster
    step = '02'
    logger.info(f'Step {step}: {"_"*100}')
    ORFs_dir = previous_pipeline_step_output_dir = pipeline_step_output_dir
    dir_name = f'{step}_dbs'
    script_path = os.path.join(args.src_dir, 'create_mmseqs2_DB.py')
    num_of_expected_results = 0
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_create_DB.txt')
    num_of_cmds_per_job = 1
    num_of_aggregated_params = 0
    more_cmds = [] # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info('Creating DBs...')
        for fasta_file in os.listdir(previous_pipeline_step_output_dir):
            file_path = os.path.join(previous_pipeline_step_output_dir, fasta_file)
            fasta_file_prefix = os.path.splitext(fasta_file)[0]
            output_file_name = f'{fasta_file_prefix}'
            if num_of_aggregated_params > 0:  # params was already defined for this job batch. Save it before overridden
                more_cmds.append(params)

            output_prefix = os.path.join(pipeline_step_output_dir, output_file_name)
            params = [file_path,
                      output_prefix,
                      output_prefix, #instead of tmp_dir
                      '-t'] #translate to peptides #TODO: Should we let the user decide?

            num_of_aggregated_params += 1
            if num_of_aggregated_params == num_of_cmds_per_job:
                submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=fasta_file_prefix,
                                     queue_name=args.queue_name, more_cmds=more_cmds, required_modules_as_list=[CONSTS.GCC])
                num_of_expected_results += 1
                num_of_aggregated_params = 0
                more_cmds = []

        if num_of_aggregated_params>0:
            #don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=fasta_file_prefix,
                                 queue_name=args.queue_name, more_cmds=more_cmds, required_modules_as_list=[CONSTS.GCC])
            num_of_expected_results += 1

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=15)


    # 3.	mmseqs2_all_vs_all.py
    # Input: (1) 2 input paths for 2 (different) genome files (query and target), g1 and g2
    #        (2) an output file path (with a suffix as follows: i_vs_j.tsv. especially relevant for the wrapper).
    # Output: a tsv file where the first column contains g1 genes and the second column includes the corresponding best match.
    # Precisely, for each gene x in g1, query x among all the genes of g2. Let y be the gene in g2 that is the most similar to x among all g2 genes. Append a row to the output file with: ‘{x}\t{y}’.
    # Can be parallelized on cluster
    step = '03'
    logger.info(f'Step {step}: {"_"*100}')
    previous_pipeline_step_output_dir = pipeline_step_output_dir
    dir_name = f'{step}_all_vs_all_analysis'
    script_path = os.path.join(args.src_dir, 'mmseqs2_all_vs_all.py')
    num_of_expected_results = 0
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_all_vs_all.txt')
    num_of_cmds_per_job = 200
    num_of_aggregated_params = 0
    more_cmds = [] # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info(f'Querying all VS all (using mmseqs2)...')
        for query_db_name in os.listdir(ORFs_dir):
            fasta_file_path = os.path.join(ORFs_dir, query_db_name)
            strain1_name = os.path.splitext(query_db_name)[0]
            for target_db_name in os.listdir(ORFs_dir):
                strain2_name = os.path.splitext(target_db_name)[0]

                if strain1_name == strain2_name:
                    continue # no need to query strain against itself
                logger.debug(f'{"#"*100}\nQuerying {strain1_name} against {strain2_name}')

                query_dna_db = os.path.splitext(os.path.join(previous_pipeline_step_output_dir, query_db_name))[0]
                query_aa_db = query_dna_db + '_aa'

                target_dna_db = os.path.splitext(os.path.join(previous_pipeline_step_output_dir, target_db_name))[0]
                target_aa_db = target_dna_db + '_aa'

                aln_db = os.path.join(pipeline_step_tmp_dir, f'{strain1_name}_vs_{strain2_name}.alnDB')
                aln_offsetted_db = os.path.join(pipeline_step_tmp_dir, f'{strain1_name}_vs_{strain2_name}.alnOffsettedDB')

                output_file_name = f'{strain1_name}_vs_{strain2_name}.m8'
                output_file_path = os.path.join(pipeline_step_output_dir, output_file_name)

                if num_of_aggregated_params > 0:
                    # params was already defined for this job batch. Save it before overridden
                    more_cmds.append(params)
                params = [query_dna_db, query_aa_db, target_dna_db,
                          target_aa_db, aln_db, aln_offsetted_db,
                          pipeline_step_tmp_dir, output_file_path]
                          #, f';!@#ls -1 {pipeline_step_output_dir} | grep "{strain1_name}_vs_{strain2_name}" | grep -v m8 | xargs rm']

                num_of_aggregated_params += 1
                if num_of_aggregated_params == num_of_cmds_per_job:
                    submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                         queue_name=args.queue_name, more_cmds=more_cmds, required_modules_as_list=[CONSTS.GCC])
                    num_of_expected_results += 1
                    num_of_aggregated_params = 0
                    more_cmds = []

        if num_of_aggregated_params>0:
            #don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                 queue_name=args.queue_name, more_cmds=more_cmds, required_modules_as_list=[CONSTS.GCC])
            num_of_expected_results += 1

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=20)


    # 4.	filter_blast.py
    # Input: (1) a path for a i_vs_j.tsv file (2) an output path (with a suffix as follows: i_vs_j_filtered.tsv. especially relevant for the wrapper).
    # Output: the same format of the input file containing only pairs that passed the filtration. For each row in the input file (pair of genes), apply the following filters:
    # 1. at least X% similarity
    # 2. at least X% of the length
    # 3.# write each pair to the output file if it passed all the above filters.
    # Can be parallelized on cluster
    step = '04'
    logger.info(f'Step {step}: {"_"*100}')
    previous_pipeline_step_output_dir = pipeline_step_output_dir
    dir_name = f'{step}_blast_filtered'
    script_path = os.path.join(args.src_dir, 'filter_blast_results.py')
    num_of_expected_results = 0
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_filter_blast_results.txt')
    num_of_cmds_per_job = 50
    num_of_aggregated_params = 0
    more_cmds = []  # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info('Filtering all vs all results...\n')
        logger.debug(f'Filtering the following files:\n' + '\n'.join(x for x in os.listdir(previous_pipeline_step_output_dir)))
        for blast_results_file in os.listdir(previous_pipeline_step_output_dir):
            fasta_file_prefix = os.path.splitext(blast_results_file)[0]
            output_file_name = f'{fasta_file_prefix}.{dir_name}'
            if num_of_aggregated_params > 0:  # params was already defined for this job batch. Save it before overridden
                more_cmds.append(params)

            params = [os.path.join(previous_pipeline_step_output_dir, blast_results_file),
                      os.path.join(pipeline_step_output_dir, output_file_name),
                      f'--identity_cutoff {args.identity_cutoff/100}', # needs to be normaized between 0 and 1
                      f'--e_value_cutoff {args.e_value_cutoff}']

            num_of_aggregated_params += 1
            if num_of_aggregated_params == num_of_cmds_per_job:
                submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                     queue_name=args.queue_name, more_cmds=more_cmds)
                num_of_expected_results += 1
                num_of_aggregated_params = 0
                more_cmds = []

        if num_of_aggregated_params > 0:
            # don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                 queue_name=args.queue_name, more_cmds=more_cmds)
            num_of_expected_results += 1

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=25)


    # 5.	find_reciprocal_hits.py
    # Input: (1) a path for a i_vs_j.blast_filtered file and a path for a j_vs_i.blast_filtered file (2) an output path (with a suffix as follows: i_vs_j_reciprocal_hits.tsv
    # Output: a tab delimited file containing only reciprocal best-hit pairs and their bit score from blast, i.e., if x’s best hit was y in the first file with bit score z, x\ty\tz will appear in the output file only if y’s best hit in the other file will be x.
    # Can be parallelized on cluster
    step = '05'
    logger.info(f'Step {step}: {"_"*100}')
    previous_pipeline_step_output_dir = pipeline_step_output_dir
    dir_name = f'{step}_reciprocal_hits'
    script_path = os.path.join(args.src_dir, 'find_reciprocal_hits.py')
    num_of_expected_results = 0
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_find_reciprocal_hits.txt')
    num_of_cmds_per_job = 10
    num_of_aggregated_params = 0
    more_cmds = []  # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info('Extracting reciprocal hits...')
        for blast_filtered_results_file in os.listdir(previous_pipeline_step_output_dir):
            file_name_prefix = os.path.splitext(blast_filtered_results_file)[0]
            strain1, strain2 = file_name_prefix.split('_vs_')[:2]
            logger.debug(f'\nstrain1: {strain1}\nstrain2: {strain2}')
            if strain1<strain2:
                # avoid both strain1,strain2 and strain2,strain1
                reciprocal_file_name_prefix = "_vs_".join([strain2, strain1])
                reciprocal_file_name = reciprocal_file_name_prefix + os.path.splitext(blast_filtered_results_file)[1]
                output_file_name = f'{file_name_prefix}.{dir_name}'
                if num_of_aggregated_params > 0:  # params was already defined for this job batch. Save it before overridden
                    more_cmds.append(params)
                params = [os.path.join(previous_pipeline_step_output_dir, blast_filtered_results_file),
                          os.path.join(previous_pipeline_step_output_dir, reciprocal_file_name),
                          os.path.join(pipeline_step_output_dir, output_file_name)]
                num_of_aggregated_params += 1
                if num_of_aggregated_params == num_of_cmds_per_job:
                    submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                         queue_name=args.queue_name, more_cmds=more_cmds)
                    num_of_expected_results += 1
                    num_of_aggregated_params = 0
                    more_cmds = []

        if num_of_aggregated_params > 0:
            # don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                 queue_name=args.queue_name, more_cmds=more_cmds)
            num_of_expected_results += 1

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=30)


    # 6. concatenate_reciprocal_hits
    # Input: path to folder with all reciprocal hits files
    # Output: concatenated file of all reciprocal hits files
    # CANNOT be parallelized on cluster
    step = '06'
    logger.info(f'Step {step}: {"_"*100}')
    all_reciprocal_hits_file = os.path.join(args.output_dir, 'concatenated_all_reciprocal_hits.txt')
    done_file_path = os.path.join(done_files_dir, f'{step}_concatenate_reciprocal_hits.txt')
    if not os.path.exists(done_file_path):
        logger.info('Concatenating reciprocal hits...')
        cmd = f'cat {pipeline_step_output_dir}/*.{dir_name} > {all_reciprocal_hits_file}'
        logger.info(f'Calling:\n{cmd}')
        subprocess.run(cmd, shell = True)
        # No need to wait...
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')


    # 7.	construct_putative_orthologs_table.py
    # Input: (1) a path for a i_vs_j_reciprocal_hits.tsv file (2) a path for a putative orthologs file (with a single line).
    # Output: updates the table with the info from the reciprocal hit file.
    # CANNOT be parallelized on cluster
    step = '07'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_putative_table'
    script_path = os.path.join(args.src_dir, 'construct_putative_orthologs_table.py')
    num_of_expected_results = 0
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    putative_orthologs_table_path = os.path.join(pipeline_step_output_dir, 'putative_orthologs_table.txt')
    done_file_path = os.path.join(done_files_dir, f'{step}_construct_putative_orthologs_table.txt')
    if not os.path.exists(done_file_path):
        logger.info('Constructing putative orthologs table...')
        job_name = os.path.split(script_path)[-1]
        params = [all_reciprocal_hits_file,
                  putative_orthologs_table_path]
        submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=job_name,
                             queue_name=args.queue_name)
        num_of_expected_results = 1
        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=35)


    # # 6.	split_putative_orthologs_table
    # # Input: (1) a path for a putative orthologs table (each row in this table is a putative orthologous group) (2) an output_path to a directory.
    # # Output: each line is written to a separate file in the output directory.
    # # Can be parallelized on cluster (better as a subprocess)
    # logger.info(f'Step 6: {"_"*100}')
    # dir_name = 'splitted_putative_orthologs_table'
    # # script_path = os.path.join(args.src_dir, '..', 'auxiliaries', 'file_writer.py')
    # # num_of_expected_results = 0
    # pipeline_step_output_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)[0]  # pipeline_step_tmp_dir is not needed
    # done_file_path = os.path.join(done_files_dir, '6_split_putative_orthologs_table.txt')
    # if not os.path.exists(done_file_path):
    #     logger.info('Splitting putative orthologs table...')
    #     with open(putative_orthologs_table_path) as f:
    #         header = f.readline()
    #         lines = ''
    #         i = 0
    #         for line in f:
    #             lines += line
    #             i += 1
    #             if i % 100 == 0:
    #                 out_file = os.path.join(pipeline_step_output_dir, (line.split(',')[0]) + '.' + dir_name)
    #                 # subprocess.call(['python', script_path, out_file,'--content' ,line])
    #                 file_writer.write_to_file(out_file, header+lines)
    #                 lines = ''
    #         if lines: # write last rows (maybe we didn't reach 100...)
    #             out_file = os.path.join(pipeline_step_output_dir, (line.split(',')[0]) + '.' + dir_name)
    #             file_writer.write_to_file(out_file, header+lines)
    #         # wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
    #
    #     file_writer.write_to_file(done_file_path)
    # else:
    #     logger.info(f'done file {done_file_path} already exists.\nSkipping step...')


    # 8   prepare_files_for_mcl.py
    # Input: (1) a path for a concatenated all reciprocal hits file (2) a path for a putative orthologs file (3) a path for an output folder
    # Output: an input file for MCL for each putative orthologs group
    # CANNOT be parallelized on cluster (if running on the concatenated file)
    step = '08'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_mcl_input_files'
    script_path = os.path.join(args.src_dir, 'prepare_files_for_mcl.py')
    num_of_expected_results = 1 # a single job that prepares all the files
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_prepare_files_for_mcl.txt')
    if not os.path.exists(done_file_path):
        logger.info('Preparing files for MCL...')
        job_name = os.path.split(script_path)[-1]
        params = [all_reciprocal_hits_file,
                  putative_orthologs_table_path,
                  pipeline_step_output_dir]
        submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=job_name, queue_name=args.queue_name)
        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=40)


    # 9.	run_mcl.py
    # Input: (1) a path to an MCL input file (2) a path to MCL's output.
    # Output: MCL analysis.
    # Can be parallelized on cluster
    step = '09'
    logger.info(f'Step {step}: {"_"*100}')
    previous_pipeline_step_output_dir = pipeline_step_output_dir
    dir_name = f'{step}_mcl_analysis'
    script_path = os.path.join(args.src_dir, 'run_mcl.py')
    num_of_expected_results = 0
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_run_mcl.txt')
    num_of_cmds_per_job = 100
    num_of_aggregated_params = 0
    more_cmds = [] # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info('Executing MCL...')
        for putative_orthologs_group in os.listdir(previous_pipeline_step_output_dir):
            putative_orthologs_group_prefix = os.path.splitext(putative_orthologs_group)[0]
            output_file_name = f'{putative_orthologs_group_prefix}.{dir_name}'
            if num_of_aggregated_params > 0:
                # params was already defined for this job batch. Save it before overridden
                more_cmds.append(params)
            params = [os.path.join(previous_pipeline_step_output_dir, putative_orthologs_group),
                      os.path.join(pipeline_step_output_dir, output_file_name)]
            num_of_aggregated_params += 1
            if num_of_aggregated_params == num_of_cmds_per_job:
                submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                     queue_name=args.queue_name, required_modules_as_list=[CONSTS.MCL],
                                     more_cmds=more_cmds)
                num_of_expected_results += 1
                num_of_aggregated_params = 0
                more_cmds = []

        if num_of_aggregated_params>0:
            #don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=output_file_name,
                                 queue_name=args.queue_name, required_modules_as_list=[CONSTS.MCL],
                                 more_cmds=more_cmds)
            num_of_expected_results += 1

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=45)


    # 10.	verify_cluster.py
    # Input: (1) mcl analysis file (2) a path to which the file will be moved if relevant (3) optional: maximum number of clusters allowed [default=1]
    # Output: filter irrelevant clusters by moving the relevant to an output directory
    # Can be parallelized on cluster
    step = '10'
    logger.info(f'Step {step}: {"_"*100}')
    previous_pipeline_step_output_dir = pipeline_step_output_dir
    dir_name = f'{step}_verified_clusters'
    script_path = os.path.join(args.src_dir, 'verify_cluster.py')
    num_of_expected_results = 0
    pipeline_step_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_verify_cluster.txt')
    num_of_cmds_per_job = 100
    num_of_aggregated_params = 0
    more_cmds = [] # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info('Verifying clusters...')
        for putative_orthologs_group in os.listdir(previous_pipeline_step_output_dir):
            putative_orthologs_group_prefix = os.path.splitext(putative_orthologs_group)[0]
            job_name = os.path.split(putative_orthologs_group_prefix)[-1]
            if num_of_aggregated_params > 0:
                # params was already defined for this job batch. Save it before overridden
                more_cmds.append(params)
            params = [os.path.join(previous_pipeline_step_output_dir, putative_orthologs_group),
                      os.path.join(pipeline_step_output_dir, putative_orthologs_group)]
            num_of_aggregated_params += 1
            if num_of_aggregated_params == num_of_cmds_per_job:
                submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=job_name,
                                     queue_name=args.queue_name, more_cmds=more_cmds)
                num_of_expected_results += 1
                num_of_aggregated_params = 0
                more_cmds = []

        if num_of_aggregated_params>0:
            #don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=job_name,
                                 queue_name=args.queue_name, more_cmds=more_cmds)
            num_of_expected_results += 1

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=50)


    # 11.	construct_final_orthologs_table.py
    # Input: (1) a path for directory with all the verified OGs (2) an output path to a final OGs table.
    # Output: aggregates all the well-clustered OGs to the final table.
    step = '11'
    logger.info(f'Step {step}: {"_"*100}')
    previous_pipeline_step_output_dir = pipeline_step_output_dir
    dir_name = f'{step}_final_table'
    script_path = os.path.join(args.src_dir, 'construct_final_orthologs_table.py')
    num_of_expected_results = 1 # a single job that prepares all the files
    final_orthologs_table_path, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    final_orthologs_table_file_path = os.path.join(final_orthologs_table_path, 'final_orthologs_table.csv')
    phyletic_patterns_path = os.path.join(final_orthologs_table_path, 'phyletic_pattern.fas')
    done_file_path = os.path.join(done_files_dir, f'{step}_construct_final_orthologs_table.txt')
    if not os.path.exists(done_file_path):
        logger.info('Constructing final orthologs table...')
        job_name = os.path.split(final_orthologs_table_file_path)[-1]
        params = [putative_orthologs_table_path,
                  previous_pipeline_step_output_dir,
                  final_orthologs_table_file_path,
                  phyletic_patterns_path]
        submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=job_name, queue_name=args.queue_name)
        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=55)


    # 12.	extract_orthologs_sequences.py
    # Input: (1) a row from the final orthologs table (2) a path for a directory where the genes files are at (3) a path for an output file.
    # Output: write the sequences of the orthologs group to the output file.
    step = '12'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_orthologs_groups_dna_sequences'
    script_path = os.path.join(args.src_dir, 'extract_orthologs_sequences.py')
    num_of_expected_results = 0
    orthologs_dna_sequences_dir_path, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    num_of_strains_path = os.path.join(final_orthologs_table_path, 'num_of_strains.txt')
    done_file_path = os.path.join(done_files_dir, f'{step}_extract_orthologs_sequences.txt')
    num_of_cmds_per_job = 100
    num_of_aggregated_params = 0
    more_cmds = [] # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info(f'There are {len(os.listdir(previous_pipeline_step_output_dir))} verified clusters in {previous_pipeline_step_output_dir}.')
        logger.info('Extracting orthologs groups sequences according to final orthologs table...')
        logger.debug(f'The verified clusters in {previous_pipeline_step_output_dir} are the following:')
        logger.debug(os.listdir(previous_pipeline_step_output_dir))
        # og_number = 0
        with open(final_orthologs_table_file_path) as f:
            header_line = f.readline()
            first_delimiter_index = header_line.index(',')
            final_table_header = header_line.rstrip()[first_delimiter_index + 1:] #remove "OG_name"
            for line in f:
                first_delimiter_index = line.index(',')
                og_name = line[:first_delimiter_index]
                cluster_members = line.rstrip()[first_delimiter_index+1:] #remove "OG_name"
                output_file_name = og_name
                # og_number += 1
                if num_of_aggregated_params > 0:
                    # params was already defined for this job batch. Save it before overridden
                    more_cmds.append(params)
                params = [ORFs_dir,
                          f'"{final_table_header}"',  # should be flanked by quotes because it might contain spaces...
                          f'"{cluster_members}"',  # should be flanked by quotes because it might contain spaces...
                          os.path.join(orthologs_dna_sequences_dir_path, f'{output_file_name}_dna.fas')]
                num_of_aggregated_params += 1
                logger.debug(f'num_of_aggregated_params: {num_of_aggregated_params} of {num_of_cmds_per_job}')
                if num_of_aggregated_params == num_of_cmds_per_job:
                    submit_pipeline_step(script_path, params, pipeline_step_tmp_dir,
                                         job_name=output_file_name,
                                         queue_name=args.queue_name,
                                         more_cmds=more_cmds)
                    num_of_expected_results += 1
                    num_of_aggregated_params = 0
                    more_cmds = []

        if num_of_aggregated_params>0:
            #don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir,
                                 job_name=output_file_name,
                                 queue_name=args.queue_name,
                                 more_cmds=more_cmds)
            num_of_expected_results += 1

        # extract number of strains for core genome analysis later on
        num_of_strains = len(final_table_header.split(','))
        with open(num_of_strains_path, 'w') as f:
            f.write(f'{num_of_strains}\n')

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=60)


    # 13.  create_mmseqs2_DB.py
    # Input: path to orfs file to create DB from
    # Output: translated proteins
    # Can be parallelized on cluster
    step = '13'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_orthologs_groups_aa_sequences'
    script_path = os.path.join(args.src_dir, 'create_mmseqs2_DB.py')
    num_of_expected_results = 0
    orthologs_aa_sequences_dir_path, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_create_DB.txt')
    num_of_cmds_per_job = 100
    num_of_aggregated_params = 0
    more_cmds = [] # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info('Translating orthologs groups sequences...')
        for fasta_file in os.listdir(orthologs_dna_sequences_dir_path):
            file_path = os.path.join(orthologs_dna_sequences_dir_path, fasta_file)
            output_path = os.path.join(orthologs_aa_sequences_dir_path, fasta_file.replace('_dna.fas', ''))
            tmp_path = os.path.join(pipeline_step_tmp_dir, fasta_file.replace('_dna.fas', ''))

            job_name = f'{os.path.splitext(fasta_file)[0]}_to_aa'
            if num_of_aggregated_params > 0:  # params was already defined for this job batch. Save it before overridden
                more_cmds.append(params)
            params = [file_path,
                      output_path,
                      tmp_path,
                      '-c'] # translate dna and convert to fasta  #TODO: Should we let the user decide?
            num_of_aggregated_params += 1
            if num_of_aggregated_params == num_of_cmds_per_job:
                submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name,
                                     queue_name=args.queue_name, more_cmds=more_cmds, required_modules_as_list=[CONSTS.GCC])
                num_of_expected_results += 1
                num_of_aggregated_params = 0
                more_cmds = []

        if num_of_aggregated_params>0:
            #don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name,
                                 queue_name=args.queue_name, more_cmds=more_cmds, required_modules_as_list=[CONSTS.GCC])
            num_of_expected_results += 1

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results, error_file_path)

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=65)


    # 14.	align_orthologs_group.py
    # Input: TODO
    # Output: TODO
    step = '14'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_aligned_aa_orthologs_groups'
    script_path = os.path.join(args.src_dir, 'align_orthologs_group.py')
    num_of_expected_results = 0
    aa_alignments_path, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_aligned_aa_orthologs_groups.txt')
    num_of_cmds_per_job = 100
    num_of_aggregated_params = 0
    more_cmds = [] # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info('Aligning orthologs groups...')
        og_files = [x for x in os.listdir(orthologs_aa_sequences_dir_path) if x.endswith('fas')]
        for og_file in og_files:
            og_path = os.path.join(orthologs_aa_sequences_dir_path, og_file)
            og_file_prefix = os.path.splitext(og_file)[0]
            alignment_path = os.path.join(aa_alignments_path, f'{og_file_prefix}_mafft.fas')
            if num_of_aggregated_params > 0:
                # params was already defined for this job batch. Save it before overridden
                more_cmds.append(params)
            params = [og_path, alignment_path]
            num_of_aggregated_params += 1
            if num_of_aggregated_params == num_of_cmds_per_job:
                submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=og_file_prefix,
                                     queue_name=args.queue_name, required_modules_as_list=[CONSTS.MAFFT],
                                     more_cmds=more_cmds)
                num_of_expected_results += 1
                num_of_aggregated_params = 0
                more_cmds = []

        if num_of_aggregated_params>0:
            #don't forget the last batch!!
            submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name=og_file_prefix,
                                 queue_name=args.queue_name, required_modules_as_list=[CONSTS.MAFFT],
                                 more_cmds=more_cmds)
            num_of_expected_results += 1

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results,
                         error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=70)


    #15.	extract aligned core genome.py IN FACT, THE CORE PROTEOME IS EXTRACTED
    step = '15'
    logger.info(f'Step {step}: {"_" * 100}')
    dir_name = f'{step}_aligned_core_proteome'
    script_path = os.path.join(args.src_dir, 'extract_core_genome.py')
    num_of_expected_results = 1
    aligned_core_proteome_path, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_extract_aligned_core_proteome.txt')
    aligned_core_proteome_file_path = os.path.join(aligned_core_proteome_path, 'aligned_core_proteome.fas')
    core_ogs_names_file_path = os.path.join(aligned_core_proteome_path, 'core_ortholog_groups_names.txt')
    if not os.path.exists(done_file_path):
        logger.info('Extracting aligned core proteome...')
        with open(num_of_strains_path) as f:
            num_of_strains = f.read().rstrip()

        params = [aa_alignments_path, num_of_strains,
                  aligned_core_proteome_file_path,
                  core_ogs_names_file_path,
                  f'--core_minimal_percentage {args.core_minimal_percentage}']  # how many members induce a core group?
        submit_pipeline_step(script_path, params, pipeline_step_tmp_dir, job_name='core_proteome',
                             queue_name=args.queue_name)

        wait_for_results(os.path.split(script_path)[-1], pipeline_step_tmp_dir, num_of_expected_results,
                         error_file_path)
        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=75)


    # 16.	reconstruct_species_phylogeny.py
    step = '16'
    logger.info(f'Step {step}: {"_" * 100}')
    dir_name = f'{step}_species_phylogeny'
    script_path = os.path.join(args.src_dir, 'reconstruct_species_phylogeny.py')
    num_of_expected_results = 1
    phylogeny_path, phylogeny_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    phylogenetic_raw_tree_path = os.path.join(phylogeny_path, 'species_tree.txt')
    done_file_path = os.path.join(done_files_dir, f'{step}_reconstruct_species_phylogeny.txt')
    if not os.path.exists(done_file_path):
        logger.info('Reconstructing species phylogeny...')

        params = [aligned_core_proteome_file_path,
                  phylogenetic_raw_tree_path,
                  '--model PROTGAMMAILG']
        submit_pipeline_step(script_path, params, phylogeny_tmp_dir, job_name='tree_reconstruction',
                             queue_name=args.queue_name, required_modules_as_list=[CONSTS.RAXML])

        # no need to wait now. Wait before plotting the tree!

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=80)


    # 17.	extract_orfs_statistics.py
    # Input: TODO
    # Output: TODO
    step = '17'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_orfs_statistics'
    script_path = os.path.join(args.src_dir, 'extract_orfs_statistics.py')
    num_of_expected_orfs_results = 0
    orfs_statistics_path, orfs_statistics_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_extract_orfs_statistics.txt')
    num_of_cmds_per_job = 100
    num_of_aggregated_params = 0
    more_cmds = []  # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info('Collecting orfs counts...')

        for file in os.listdir(ORFs_dir):
            orf_path = os.path.join(ORFs_dir, file)
            strain_name = os.path.splitext(file)[0]
            orfs_count_output_path = os.path.join(orfs_statistics_path, f'{strain_name}.orfs_count')
            gc_content_output_path = os.path.join(orfs_statistics_path, f'{strain_name}.gc_content')

            if num_of_aggregated_params > 0:
                # params was already defined for this job batch. Save it before overridden
                more_cmds.append(params)
            # args.orf_path, args.orfs_counts_output_path, args.orfs_gc_output_path
            params = [orf_path, orfs_count_output_path, gc_content_output_path]
            num_of_aggregated_params += 1
            if num_of_aggregated_params == num_of_cmds_per_job:
                submit_pipeline_step(script_path, params, orfs_statistics_tmp_dir,
                                     job_name=f'{strain_name}_orfs_stats',
                                     queue_name=args.queue_name, more_cmds=more_cmds)
                num_of_expected_orfs_results += 1
                num_of_aggregated_params = 0
                more_cmds = []

        if num_of_aggregated_params > 0:
            # don't forget the last batch!!
            submit_pipeline_step(script_path, params, orfs_statistics_tmp_dir,
                                 job_name=f'{strain_name}_orfs_stats',
                                 queue_name=args.queue_name, more_cmds=more_cmds)
            num_of_expected_orfs_results += 1

        # no need to wait now. Wait before plotting the statistics!

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=85)


    # 18.	induce_dna_msa_by_aa_msa.py
    # Input: TODO
    # Output: TODO
    step = '18'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_induce_dna_msa_by_aa_msa'
    script_path = os.path.join(args.src_dir, 'induce_dna_msa_by_aa_msa.py')
    num_of_expected_induced_results = 0
    dna_alignments_path, induced_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    done_file_path = os.path.join(done_files_dir, f'{step}_aligned_dna_orthologs_groups.txt')
    num_of_cmds_per_job = 100
    num_of_aggregated_params = 0
    more_cmds = [] # a list of lists. Each sublist contain different parameters set for the same script to reduce the total number of jobs
    if not os.path.exists(done_file_path):
        logger.info(f'Inducing dna alignments...\n(from {aa_alignments_path})')
        for og_file in os.listdir(aa_alignments_path):
            aa_alignment_path = os.path.join(aa_alignments_path, og_file)
            dna_unaligned_path = os.path.join(orthologs_dna_sequences_dir_path, og_file.replace('aa_mafft', 'dna'))
            dna_induced_alignment_path = os.path.join(dna_alignments_path, og_file.replace('aa_mafft','dna_induced'))
            # logger.info(f'og_file=\n{og_file}')
            # logger.info(f'aa_alignment_path=\n{aa_alignments_path}')
            # logger.info(f'orthologs_dna_sequences_dir_path=\n{orthologs_dna_sequences_dir_path}')
            # logger.info(f'dna_unaligned_path=\n{dna_unaligned_path}')
            # logger.info(f'dna_induced_alignment_path=\n{dna_induced_alignment_path}')

            if num_of_aggregated_params > 0:
                # params was already defined for this job batch. Save it before overridden
                more_cmds.append(params)
            params = [aa_alignment_path, dna_unaligned_path, dna_induced_alignment_path]
            num_of_aggregated_params += 1
            if num_of_aggregated_params == num_of_cmds_per_job:
                submit_pipeline_step(script_path, params, induced_tmp_dir, job_name=f'induced_{og_file}',
                                     queue_name=args.queue_name, more_cmds=more_cmds)
                num_of_expected_induced_results += 1
                num_of_aggregated_params = 0
                more_cmds = []

        if num_of_aggregated_params>0:
            #don't forget the last batch!!
            submit_pipeline_step(script_path, params, induced_tmp_dir, job_name=f'induced_{og_file}',
                                 queue_name=args.queue_name, more_cmds=more_cmds)
            num_of_expected_induced_results += 1

        # no need to wait now. Wait before moving the results dir!

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')


    # 19.	extract_groups_sizes_frequency
    # Input: TODO
    # Output: TODO
    step = '19'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_groups_sizes_frequency'
    group_sizes_path, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    groups_sizes_frequency_file_prefix = os.path.join(group_sizes_path, 'groups_sizes_frequency')
    done_file_path = os.path.join(done_files_dir, f'{step}_extract_groups_sizes_frequency.txt')
    if not os.path.exists(done_file_path):
        logger.info('Collecting sizes...')

        group_sizes = []
        with open(final_orthologs_table_file_path) as f:
            final_table_header = f.readline().rstrip()
            for line in f:
                cluster_members = line.rstrip()
                size = sum(bool(item) for item in cluster_members.split(','))  # count non empty entries
                size -= 1 # don't count group name
                group_sizes.append(str(size))

        groups_sizes_frequency_raw_file_path = groups_sizes_frequency_file_prefix + '.txt'
        with open(groups_sizes_frequency_raw_file_path, 'w') as f:
            f.write('\n'.join(group_sizes)) #f.write('\n'.join([f'{size},{group_size_to_counts_dict[size]}' for size in group_size_to_counts_dict]))

        groups_sizes_frequency_png_file_path = groups_sizes_frequency_file_prefix + '.png'
        generate_bar_plot(groups_sizes_frequency_raw_file_path, groups_sizes_frequency_png_file_path,
            xlabel='\nOrthologs group size', ylabel='Counts\n')

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=90)


    # 20.	plot_orfs_statistics
    # Input: TODO
    # Output: TODO
    step = '20'
    logger.info(f'Step {step}: {"_"*100}')
    dir_name = f'{step}_orfs_plots'
    orfs_plots_path, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, dir_name)
    orfs_counts_frequency_file = os.path.join(orfs_plots_path, 'orfs_counts.txt')
    orfs_gc_content_file = os.path.join(orfs_plots_path, 'orfs_gc_contents.txt')
    done_file_path = os.path.join(done_files_dir, f'{step}_plot_orfs_statistics.txt')
    if not os.path.exists(done_file_path):

        wait_for_results('extract_orfs_statistics.py', orfs_statistics_tmp_dir,
                         num_of_expected_orfs_results, error_file_path=error_file_path)

        logger.info('Concatenating orfs counts...')
        cmd = f'cat {orfs_statistics_path}/*.orfs_count > {orfs_counts_frequency_file}'
        subprocess.run(cmd, shell = True)

        logger.info('Concatenating orfs gc contents...')
        cmd = f'cat {orfs_statistics_path}/*.gc_content > {orfs_gc_content_file}'
        subprocess.run(cmd, shell = True)

        # No need to wait...

        logger.info('Ploting violines...')
        orfs_counts_frequency_png_file_path = orfs_counts_frequency_file.replace('txt', 'png')
        generate_boxplot(orfs_counts_frequency_file, orfs_counts_frequency_png_file_path,
                         xlabel='\nORFs count per genome', dpi=100)

        orfs_gc_content_png_file_path = orfs_gc_content_file.replace('txt', 'png')
        generate_boxplot(orfs_gc_content_file, orfs_gc_content_png_file_path,
                         xlabel='\nGC content per genome', dpi=100)

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')
    edit_progress(output_html_path, progress=95)


    # 21.	plot species phylogeny
    step = '21'
    logger.info(f'Step {step}: {"_" * 100}')
    dir_name = f'{step}_plot_tree'
    done_file_path = os.path.join(done_files_dir, f'{step}_plot_species_phylogeny.txt')
    if not os.path.exists(done_file_path):
        logger.info('Ploting species phylogeny...')

        # wait for the raw tree here
        wait_for_results('reconstruct_species_phylogeny.py', phylogeny_tmp_dir,
                         num_of_expected_results=1, error_file_path=error_file_path)

        phylogenetic_png_tree_path = phylogenetic_raw_tree_path.replace('txt', 'png')
        generate_tree_plot(phylogenetic_raw_tree_path, phylogenetic_png_tree_path)

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')


    edit_progress(output_html_path, progress=98)
    # Final step: gather relevant results, zip them together and update html file
    logger.info(f'FINAL STEP: {"_"*100}')
    final_output_dir_name = f'{CONSTS.WEBSERVER_NAME}_{run_number}_outputs'
    final_output_dir, pipeline_step_tmp_dir = prepare_directories(args.output_dir, tmp_dir, final_output_dir_name)
    done_file_path = os.path.join(done_files_dir, final_output_dir_name + '.txt')
    if not os.path.exists(done_file_path):
        logger.info('Gathering results to final output dir...')

        # move orthologs table
        add_results_to_final_dir(final_orthologs_table_path, final_output_dir)

        # move unaligned dna sequences
        add_results_to_final_dir(orthologs_dna_sequences_dir_path, final_output_dir)

        # move unaligned aa sequences
        add_results_to_final_dir(orthologs_aa_sequences_dir_path, final_output_dir)

        # move aligned aa sequences
        add_results_to_final_dir(aa_alignments_path, final_output_dir)

        # move core proteome dir
        add_results_to_final_dir(aligned_core_proteome_path, final_output_dir)

        # move species tree dir
        add_results_to_final_dir(phylogeny_path, final_output_dir)

        # move groups sizes
        add_results_to_final_dir(group_sizes_path, final_output_dir)

        # move orfs statistics
        add_results_to_final_dir(orfs_plots_path, final_output_dir)

        wait_for_results('induce_dna_msa_by_aa_msa.py', induced_tmp_dir,
                         num_of_expected_results=num_of_expected_induced_results,
                         error_file_path=error_file_path)
        # move induced dna sequences
        add_results_to_final_dir(dna_alignments_path, final_output_dir)

        logger.info('Zipping results folder...')
        shutil.make_archive(final_output_dir, 'zip', final_output_dir)

        logger.info(f'Moving results to parent dir... ({meta_output_dir})')
        try:
            shutil.move(f'{final_output_dir}.zip', meta_output_dir)
        except shutil.Error as e:
            logger.error(e.args[0])
        try:
            shutil.move(final_output_dir, meta_output_dir)
        except shutil.Error as e:
            logger.error(e.args[0])

        file_writer.write_to_file(done_file_path)
    else:
        logger.info(f'done file {done_file_path} already exists.\nSkipping step...')

    if remote_run and run_number.lower() != 'example' and False:  # TODO: remove the "and False" once ready.
        # remove raw data from the server
        try:
            shutil.rmtree(data_path)  # remove data
        except:
            pass
        # remove raw data from the server
        try:
            shutil.rmtree(args.output_dir)  # remove intermediate results
        except:
            pass

    logger.info('Editing results html...')
    edit_success_html(output_html_path, meta_output_dir, final_output_dir_name, run_number, CONSTS)

    edit_progress(output_html_path, progress=100, active=False)

    status = 'is done'

except Exception as e:
    status = 'was failed'
    from time import ctime
    import os
    import logging
    logger = logging.getLogger('main')  # use logger instead of printing

    msg = 'M1CR0B1AL1Z3R failed :('

    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logger.error(f'\n\n{"$" * 100}\n\n{msg}\n\n{fname}: {exc_type}, at line: {exc_tb.tb_lineno}\n\ne: {e}\n\n{"$" * 100}')

    edit_failure_html(output_html_path, run_number, msg, CONSTS)
    edit_progress(output_html_path, active=False)

    notify_admin(meta_output_dir, meta_output_url, run_number, CONSTS)

end = time()

results_location = output_url if remote_run else args.output_dir
msg = f'M1CR0B1AL1Z3R pipeline {status}'
if status == 'is done':
    msg += f' (Took {measure_time(int(end-start))}).\nResults can be found at {results_location}.'
else:
    msg += f'.\nFor further information please visit: {results_location}'
logger.info(msg)
send_email('mxout.tau.ac.il', 'TAU BioSequence <bioSequence@tauex.tau.ac.il>', args.email, subject=f'Microbialzer {status}.', content=msg)

