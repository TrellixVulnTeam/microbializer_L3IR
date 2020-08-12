import sys
sys.path.insert(0, '/bioseq/bioSequence_scripts_and_constants/')  # ADD file_writer

import shutil
import subprocess
import os
import logging
import tarfile
from time import time, sleep, ctime
from email_sender import send_email

logger = logging.getLogger('main')  # use logger instead of printing


def load_header2sequences_dict(fasta_path, get_length=False, upper_sequence=False):
    header_to_sequence_dict = {}
    seq_length = 0

    with open(fasta_path) as f:
        header = f.readline().lstrip('>').rstrip()
        sequence = ''
        for line in f:
            line = line.rstrip()
            if line.startswith('>'):
                seq_length = len(sequence)
                if upper_sequence:
                    header_to_sequence_dict[header] = sequence.upper()
                else:
                    # leave untouched
                    header_to_sequence_dict[header] = sequence
                header = line.lstrip('>')
                sequence = ''
            else:
                sequence += line

        # don't forget last record!!
        if sequence != '':

            if upper_sequence:
                header_to_sequence_dict[header] = sequence.upper()
            else:
                # leave untouched
                header_to_sequence_dict[header] = sequence

    if get_length:
        return header_to_sequence_dict, seq_length
    else:
        return header_to_sequence_dict


def measure_time(total):
    hours = total // 3600
    minutes = (total% 3600) // 60
    seconds = total % 60
    if hours != 0:
        return f'{hours}:{minutes:02}:{seconds:02} hours'
    elif minutes != 0:
        return f'{minutes}:{seconds:02} minutes'
    else:
        return f'{seconds} seconds'


def execute(process, process_is_string=False):
    process_str = process if process_is_string else ' '.join(str(token) for token in process)
    logger.info(f'Calling (process_is_string == {process_is_string}):\n{process_str}')
    subprocess.run(process, shell=process_is_string)


def wait_for_results(script_name, path, num_of_expected_results, error_file_path, suffix='done',
                     remove=False, time_to_wait=10, start=0, error_message=None):
    '''waits until path contains num_of_expected_results $suffix files'''
    if not start:
        start = time()
    logger.info(f'Waiting for {script_name}...\nContinues when {num_of_expected_results} results will be in:\n{path}')
    if num_of_expected_results == 0:
        if error_message:
            fail(error_message, error_file_path)
        raise ValueError(f'\n{"#"*100}\nNumber of expected results is {num_of_expected_results}! Something went wrong in the previous analysis steps...\n{"#"*100}')
    total_time = 0
    i = 0
    current_num_of_results = 0
    while num_of_expected_results > current_num_of_results:
        assert not os.path.exists(error_file_path)
        try:
            current_num_of_results = sum(1 for x in os.listdir(path) if x.endswith(suffix))
        except:
            logger.info(f'Could not run the following command, probably due to some system error...')
            logger.info(f'current_num_of_results = sum(1 for x in os.listdir({path}) if x.endswith({suffix}))')
        jobs_left = num_of_expected_results - current_num_of_results
        sleep(time_to_wait)
        total_time += time_to_wait
        i += 1
        if i % 5 == 0:  # print status every 5 cycles of $time_to_wait
            logger.info(f'\t{measure_time(total_time)} have passed since started waiting ({num_of_expected_results} - {current_num_of_results} = {jobs_left} more files are still missing)')
    # if remove:
    #     execute(['python', '-u', '/groups/pupko/orenavr2/pipeline/RemoveDoneFiles.py', path, suffix])
    end = time()
    logger.info(f'Done waiting for:\n{script_name}\n(took {measure_time(int(end-start))}).\n')
    assert not os.path.exists(error_file_path)


# def remove_files_with_suffix(path, suffix='done'):
#     '''remove all files from path that end with suffix'''
#     logger.info(f'Removing {suffix} files from {path}')
#     for file_name in os.listdir(path):
#         if file_name.endswith(suffix):
#             file_path = os.path.join(path,file_name)
#             logger.debug(f'Removing {file_path}')
#             os.remove(file_path)
#     logger.info('Done removing.')


def prepare_directories(outputs_dir_prefix, tmp_dir_prefix, dir_name):
    outputs_dir = os.path.join(outputs_dir_prefix, dir_name)
    logger.info(f'{ctime()}: Creating {outputs_dir}\n')
    os.makedirs(outputs_dir, exist_ok=True)

    tmp_dir = os.path.join(tmp_dir_prefix, dir_name)
    logger.info(f'{ctime()}: Creating {tmp_dir}\n')
    os.makedirs(tmp_dir, exist_ok=True)

    return outputs_dir, tmp_dir


def submit_pipeline_step(script_path, params, tmp_dir, job_name, queue_name, new_line_delimiter='!@#',
                         q_submitter_script_path='/bioseq/bioSequence_scripts_and_constants/q_submitter_power.py',
                         done_files_script_path='/bioseq/microbializer/auxiliaries/file_writer.py',
                         required_modules_as_list=None, more_cmds=None, num_of_cpus=1):

    for char in ' ,;()"\'':
        job_name = job_name.replace(char, '_')

    required_modules_as_str = 'python/python-anaconda3.6.5-orenavr2'
    if required_modules_as_list:
        # don't forget a space after the python module!!
        required_modules_as_str += ' ' + ' '.join(required_modules_as_list)
    cmds_as_str = f'module load {required_modules_as_str}'
    cmds_as_str += new_line_delimiter

    if more_cmds:
        for cmd in more_cmds:
            #cmds_as_str += ' '.join(['python', '-u', script_path, *cmd]) + ';' #unbuffering
            cmds_as_str += ' '.join(['python', script_path, *cmd]) + ';' #buffering
            cmds_as_str += new_line_delimiter  # the queue does not like very long commands so I use a dummy delimiter (!@#) to break the rows in q_submitter

    # ACTUAL COMMAND (last command if it's a batch)
    #cmds_as_str += ' '.join(['python', '-u', script_path, *params])+';' #unbuffering
    cmds_as_str += ' '.join(['python', script_path, *params])+';' #buffering
    cmds_as_str += new_line_delimiter # the queue does not like very long commands so I use a dummy delimiter (!@#) to break the rows in q_submitter

    # GENERATE DONE FILE
    params = [os.path.join(tmp_dir, job_name + '.done'), ''] # write an empty string (like "touch" command)
    cmds_as_str += ' '.join(['python', done_files_script_path, *params])+';'
    cmds_as_str += new_line_delimiter

    cmds_as_str += '\t' + job_name + '\n'
    logger.debug(cmds_as_str)
    cmds_path = os.path.join(tmp_dir, job_name + '.cmds')
    with open(cmds_path, 'w') as f:
        f.write(cmds_as_str)
    execute([q_submitter_script_path, cmds_path, tmp_dir, '-q', queue_name, '--cpu', str(num_of_cpus)])


def fail(error_msg, error_file_path):
    logger.error(error_msg)
    with open(error_file_path, 'w') as error_f:
        error_f.write(error_msg + '\n')
    raise ValueError(error_msg)


def new_submit_pipeline_step(script_path, params_lists, logs_dir, queue_name, q_submitter_script_path,
                             job_name='', new_line_delimiter='!@#', verbose=False, required_modules_as_list=None,
                             num_of_cpus=1, done_files_script_path='/bioseq/microbializer/auxiliaries/file_writer.py',
                             submit_as_a_job=True, done_file_is_needed=True):
    """
    :param script_path:
    :param params_lists: a list of lists. each sublist corresponds to a single command and contain its parameters
    :param logs_dir:
    :param job_name:
    :param queue_name:
    :param q_submitter_script_path: leave it as is
    :param new_line_delimiter: leave it as is
    :param verbose:
    :param required_modules_as_list: a list of strings containing module names that should be loaded before running
    :param num_of_cpus:
    :param done_files_script_path: leave it as is
    :param submit_as_a_job: if False, fetched directly in shell and not as an independent job
    :return: an example command to debug on the shell
    """

    # COMMAND FOR LOADING RELEVANT MODULES
    required_modules_as_str = 'python/python-anaconda3.6.5'
    if required_modules_as_list:
        # don't forget a space after the python module!!
        required_modules_as_str += ' ' + ' '.join(required_modules_as_list)

    shell_cmds_as_str = f'module load {required_modules_as_str}'
    shell_cmds_as_str += new_line_delimiter  # several commands that will be split to different lines
                                             # (long lines with ";" are bad practice)

    example_shell_cmd = ' '.join(['python', script_path, *[str(param) for param in params_lists[0]]] + (['-v'] if verbose else [])) + ';'
    # PREPARING RELEVANT COMMANDS
    for params in params_lists:
        shell_cmds_as_str += ' '.join(['python', script_path, *[str(param) for param in params]] + (['-v'] if verbose else [])) + ';'
        shell_cmds_as_str += new_line_delimiter

    if not job_name:
        job_name = time()

    if done_file_is_needed:
        # GENERATE DONE FILE
        params = [os.path.join(logs_dir, job_name + '.done'), '']  # write an empty string (like "touch" command)
        shell_cmds_as_str += ' '.join(['python', done_files_script_path, *params])+';'
        shell_cmds_as_str += new_line_delimiter

    if submit_as_a_job:
        # WRITING CMDS FILE
        cmds_path = os.path.join(logs_dir, f'{job_name}.cmds')
        with open(cmds_path, 'w') as f:
            f.write(f'{shell_cmds_as_str}\t{job_name}\n')  # ADDING THE JOB NAME

        job_cmd = [q_submitter_script_path, cmds_path, logs_dir, '-q', queue_name, '--cpu', str(num_of_cpus)]
        execute(job_cmd)
    else:
        # fetch directly on shell
        for shell_cmd in shell_cmds_as_str.split(new_line_delimiter):
            execute(shell_cmd, shell=True)

    return example_shell_cmd


def submit_batches(script_path, all_cmds_params, logs_dir, job_name_suffix='', queue_name='pupkolabr', num_of_cmds_per_job=1,
                   q_submitter_script_path='/bioseq/bioSequence_scripts_and_constants/q_submitter_power.py',
                   new_line_delimiter='!@#', required_modules_as_list=None, num_of_cpus=1):
    """
    :param script_path: 
    :param all_cmds_params: a list of lists. each sublist corresponds to a single command and contain its parameters
    :param logs_dir: 
    :param job_name_suffix: a string that will be concatenated after the batch number as the job name
    :param queue_name: 
    :param num_of_cmds_per_job:
    :param q_submitter_script_path: leave it as is
    :param new_line_delimiter: leave it as is
    :param required_modules_as_list: a list of strings containing module names that should be loaded before running
    :param num_of_cpus: 
    :return: number of batches submitted (in case waiting for the results) and an example command to debug on the shell
    """
    num_of_batches = 0
    example_cmd_from_batch = 'NO COMMANDS WERE FETCHED'

    if not job_name_suffix:
        job_name_suffix = time()

    job_name_suffix = job_name_suffix.replace(' ', '_')  # job name cannot contain spaces!

    for i in range(0, len(all_cmds_params), num_of_cmds_per_job):
        current_batch_params = all_cmds_params[i: i + num_of_cmds_per_job]
        example_cmd_from_batch = new_submit_pipeline_step(script_path, current_batch_params, logs_dir, queue_name,
                                                          q_submitter_script_path, f'{num_of_batches}_{job_name_suffix}',
                                                          new_line_delimiter, verbose=False,
                                                          required_modules_as_list=required_modules_as_list,
                                                          num_of_cpus=num_of_cpus)
        logger.info(f'Example command from current batch:\n{example_cmd_from_batch}')
        num_of_batches += 1

    return num_of_batches, example_cmd_from_batch


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)


def wait_for_output_folder(output_folder, max_waiting_time=300):
    i = 0
    while not os.path.exists(output_folder):
        logger.info(f'Waiting to {output_folder} to be generated... (waited {i} seconds)')
        i += 1
        if i>max_waiting_time:
            raise OSError(f'{output_folder} was not generated after {max_waiting_time} second. Failed to continue the analysis.')
        sleep(1)


def remove_bootstrap_values(in_tree_path, out_tree_path):
    with open(in_tree_path) as f:
        tree_as_str = f.read()
    import re
    tree_as_str = re.sub('\)\d+:', '):', tree_as_str)
    with open(out_tree_path, 'w') as f:
        f.write(tree_as_str)


def notify_admin(meta_output_dir, meta_output_url, run_number, CONSTS):
    email = 'NO_EMAIL'
    user_email_path = os.path.join(meta_output_dir, CONSTS.EMAIL_FILE_NAME)
    if os.path.exists(user_email_path):
        with open(user_email_path) as f:
            email = f.read().rstrip()
    error_log_path = 'NO_ERROR_LOG'
    file_with_job_id_on_qstat = os.path.join(meta_output_dir, 'qsub.log')
    if os.path.exists(file_with_job_id_on_qstat):
        with open(file_with_job_id_on_qstat) as f:
            job_id_on_qstat = f.read().strip()
        error_log_path = os.path.join(meta_output_dir, f'{job_id_on_qstat}.ER')
        # TODO: change to ER url and add reading permissions
    # Send me a notification email every time there's a failure
    send_email(smtp_server=CONSTS.SMTP_SERVER,
               sender=CONSTS.ADMIN_EMAIL,
               receiver=CONSTS.OWNER_EMAIL,
               subject=f'{CONSTS.WEBSERVER_NAME} job {run_number} by {email} has been failed: ',
               content=f"{email}\n\n{os.path.join(meta_output_url, 'output.html')}\n\n"
               f"{os.path.join(meta_output_url, 'cgi_debug.txt')}\n\n"
               f"{os.path.join(meta_output_url, error_log_path)}\n\n"
               f"{os.path.join(meta_output_dir, error_log_path.replace('ER', 'OU'))}")


def add_results_to_final_dir(source, final_output_dir, copy=True):
    dest = os.path.join(final_output_dir, os.path.split(source)[1])

    try:
        if not copy:
            logger.info(f'Moving {source} TO {dest}')
            shutil.move(source, dest)
        else:
            logger.info(f'Copying {source} TO {dest}')
            shutil.copytree(source, dest)
    except FileExistsError:
        pass

    return dest


def remove_path(path_to_remove):
    logger.info(f'Removing {path_to_remove} ...')
    try:
        shutil.rmtree(path_to_remove)  # maybe it's a folder
    except:
        pass
    try:
        os.remove(path_to_remove)
    except:
        pass


def unpack_data(data_path, meta_output_dir, error_file_path):
    if not os.path.isdir(data_path):
        unzipped_data_path = os.path.join(meta_output_dir, 'data')
        try:
            if tarfile.is_tarfile(data_path):
                logger.info('UnTARing')
                with tarfile.open(data_path, 'r:gz') as f:
                    f.extractall(path=unzipped_data_path)  # unzip tar folder to parent dir
                logger.info('Succeeded!')
                # data_path = data_path.split('.tar')[0] # e.g., /groups/pupko/orenavr2/microbializer/example_data.tar.gz
                # logger.info(f'Updated data_path is:\n{data_path}')
            elif data_path.endswith('.gz'):  # gunzip gz file
                execute(f'gunzip -f "{data_path}"', process_is_string=True)
                unzipped_data_path = data_path[:-3]  # trim the ".gz"
            else:
                logger.info('UnZIPing')
                shutil.unpack_archive(data_path, extract_dir=unzipped_data_path)  # unzip tar folder to parent dir
        except Exception as e:
            logger.info(e)
            remove_path(data_path)
            fail(f'Illegal file format. Please upload either a '
                 f'<a href="https://support.microsoft.com/en-us/help/14200/windows-compress-uncompress-zip-files" target="_blank">.zip</a> file or a '
                 f'<a href="https://linhost.info/2012/08/gzip-files-in-windows/" target="_blank">.tar.gz</a> file in which each file is a '
                 f'<a href="https://www.ncbi.nlm.nih.gov/blast/fasta.shtml" target="_blank">FASTA format</a> containing genomic sequence of a different species',
                 error_file_path)
        logger.info('Succeeded!')
        # data_path = os.path.join(meta_output_dir, 'data') # e.g., /groups/pupko/orenavr2/microbializer/example_data.tar.gz
        # logger.info(f'Updated data_path is:\n{data_path}')

        if not os.path.exists(unzipped_data_path):
            fail(f'Failed to unzip {os.path.split(data_path)[-1]} (maybe it is empty?)', error_file_path)

        if not os.path.isdir(unzipped_data_path):
            fail('Archived file content is not a folder', error_file_path)

        file = [x for x in os.listdir(unzipped_data_path) if not x.startswith(('_', '.'))][0]
        logger.info(f'first file in {unzipped_data_path} is:\n{file}')
        if os.path.isdir(os.path.join(unzipped_data_path, file)):
            data_path = os.path.join(unzipped_data_path, file)
            file = [x for x in os.listdir(data_path) if not x.startswith(('_', '.'))][0]
            if os.path.isdir(os.path.join(data_path, file)):
                fail('More than a 2-levels folder...', error_file_path)
        else:
            data_path = unzipped_data_path

    logger.info(f'Updated data_path is:\n{data_path}')
    for file in os.listdir(data_path):
        file_path = os.path.join(data_path, file)
        if file_path.endswith('gz'):  # gunzip gz files in $data_path if any
            execute(f'gunzip -f "{file_path}"', process_is_string=True)

    return data_path