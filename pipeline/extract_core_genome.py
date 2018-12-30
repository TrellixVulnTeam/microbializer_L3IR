"""
script_name.py /Users/Oren/Dropbox/Projects/microbializer/output/15_aligned_orthologs_groups 5 /Users/Oren/Dropbox/Projects/microbializer/output/16_aligned_core_genome/aligned_core_genome.fasta
"""

import os

def load_orthologs_group_to_dict(fasta_path):
    header_to_sequence_dict = {}
    with open(fasta_path) as f:
        header = f.readline().lstrip('>').rstrip()
        sequence = ''
        for line in f:
            line = line.rstrip()
            if line.startswith('>'):
                header_to_sequence_dict[header] = sequence
                header = line.lstrip('>')
                sequence = ''
            else:
                sequence += line

        # don't forget last record!!
        if sequence != '':
            header_to_sequence_dict[header] = sequence

    return header_to_sequence_dict


def is_core_gene(strain_to_gene_dict, num_of_strains, core_minimal_percentage):
    return len(strain_to_gene_dict) >= num_of_strains*core_minimal_percentage/100


def update_core_genome(core_genome_dict, strain_to_gene_dict):
    for strain in strain_to_gene_dict:
        core_genome_dict[strain] = core_genome_dict.get(strain, '') + strain_to_gene_dict[strain]


def extract_core_genome(alignments_path, num_of_strains, core_genome_path, core_minimal_percentage):
    core_genome_dict = {}
    for og_file in os.listdir(alignments_path):
        strain_to_gene_dict = load_orthologs_group_to_dict(os.path.join(alignments_path, og_file))
        if is_core_gene(strain_to_gene_dict, num_of_strains, core_minimal_percentage):
            logger.info(f'Adding to core genome: {og_file}')
            update_core_genome(core_genome_dict, strain_to_gene_dict)
        else:
            logger.info(f'Not a core gene: {og_file}')


    with open(core_genome_path, 'w') as f:
        for strain in sorted(core_genome_dict):
            f.write(f'>{strain}\n{core_genome_dict[strain]}\n')


if __name__ == '__main__':
        from sys import argv
        print(f'Starting {argv[0]}. Executed command is:\n{" ".join(argv)}')

        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('alignments_path', help='path to a folder where each file is a multiple sequences fasta file')
        parser.add_argument('num_of_strains', help='number of strains in the data', type=int)
        parser.add_argument('core_genome_path', help='path to an output file in which the core genome will be written')
        parser.add_argument('--core_minimal_percentage',
                            help='number that represents the required percent that is needed to be considered a core gene. For example: (1) 100 means that for a gene to be considered core, all strains should have a member in the group.\n(2) 50 means that for a gene to be considered core, at least half of the strains should have a member in the group.\n(3) 0 means that every gene should be considered as a core gene.',
                            default=100)
        parser.add_argument('-v', '--verbose', help='Increase output verbosity', action='store_true')
        args = parser.parse_args()

        import logging
        if args.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger('main')

        extract_core_genome(args.alignments_path, args.num_of_strains,
                            args.core_genome_path, args.core_minimal_percentage)