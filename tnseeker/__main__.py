import os,glob
import subprocess
import multiprocessing
from tnseeker import Essential_Finder,reads_trimer,sam_to_insertions,insertions_over_genome_plotter
import argparse
import time

''' Tnseeker is a pipeline for transposon insertion sequencing (Tn-Seq) analysis. 
    It performs various operations such as trimming the reads, 
    aligning the reads to a reference genome, extracting essential genes, 
    and plotting the insertions over the genome.
    
    The pipeline is started by calling the `variables_initializer()` function, 
    which parses the input arguments and sets the various parameters used in the pipeline. 
    The input arguments include information such as the path to the sequencing files, 
    the path to the annotation files, the type of sequencing, the type of annotation, 
    the transposon sequence, etc.
    
    The pipeline then calls several functions to perform the following steps:
    
    1. `path_finder_seq()`: This function sets the paths for the reference genome, 
    annotation file, and sequencing files based on the input parameters.
    
    2. `bowtie_index_maker()`: This function creates a bowtie2 index for the reference genome.
    
    3. `tn_trimmer_single()` or `tn_trimmer_paired()`: This function trims the 
        sequencing reads based on the transposon sequence, depending on whether 
        the data is either paired ended or not
    
    4. `bowtie_aligner_maker_single()` or `bowtie_aligner_maker_paired()`: 
        This function aligns the trimmed reads to the reference genome using bowtie2,
        depending on whether the data is either paired ended or not
        
    5. `sam_parser()`: This function parses the SAM file generated by bowtie2 to 
        identify the transposon insertions.
    
    6. `essentials()`: This function uses the transposon insertions to identify essential genes.
    
    7. `insertions_plotter()`: This function plots the transposon insertions over the genome.
    
    ''' 

def path_finder(variables,extenction):
    for filename in glob.glob(os.path.join(variables["annotation_folder"], extenction)):
        test1 = filename.find(variables["strain"]) 
        if test1 != -1: 
            return filename

def path_finder_seq(variables):
    
    variables["fasta"]=path_finder(variables,'*.fasta')

    variables["directory"] = os.path.join(os.getcwd(), variables["strain"])
    
    if not os.path.isdir(variables["directory"]):
        os.mkdir(variables["directory"])
     
    if variables["sequencing_files"] == None:
        print("check that .fastq files exist in the indicated folder.")
        
    if variables["fasta"] == None:
        print("check that .fasta files exist in the indicated folder.")
    
    if variables["annotation_type"] == "gb":
        extention = '*.gb'
        if path_finder(variables,extention) == None:
            extention = '*.gbk'
        variables["annotation_file"]=path_finder(variables,extention)
        variables["seq_file"]=path_finder(variables,extention)

    elif variables["annotation_type"] == "gff":
        variables["annotation_file"]=path_finder(variables,'*.gff')
        variables["seq_file"]=path_finder(variables,'*.fasta')

    return variables

def cpu():
    c = multiprocessing.cpu_count()
    if c >= 2:
        c -= 1
    pool = multiprocessing.Pool(processes = c)
    return pool, c

def bowtie_index_maker(variables):
    
    variables["index_dir"] = f"{variables['directory']}/indexes/"
    if not os.path.isdir(variables["index_dir"]):
        os.mkdir(variables["index_dir"])
            
        send = ["bowtie2-build",
                f"{variables['fasta']}",
                f"{variables['index_dir']}{variables['strain']}",
                f"2>{variables['directory']}/bowtie_index_log.log"]
        
        subprocess_cmd(send)
    return variables
    
def bowtie_aligner_maker_single(variables):
    
    if not os.path.isfile(f'{variables["directory"]}/alignment.sam'):
    
        cpus = cpu()[1]
        send = ["bowtie2",
                "--end-to-end",
                "-x",f"{variables['index_dir']}{variables['strain']}",
                "-U",f"{variables['fastq_trimed']}",
                "-S",f"{variables['directory']}/alignment.sam",
                "--no-unal",
                f"--threads {cpus}",
                f"2>'{variables['directory']}/bowtie_align_log.log'"]
        
        subprocess_cmd(send)
        
    else:
        print(f'Found {variables["directory"]}/alignment.sam, skipping alignment')

    if variables["remove"]:
        os.remove(variables['fastq_trimed'])
    
def bowtie_aligner_maker_paired(variables):
    
    if not os.path.isfile(f'{variables["directory"]}/alignment.sam'):
    
        cpus = cpu()[1]
        send = ["bowtie2",
                "--end-to-end",
                "-x",f"{variables['index_dir']}{variables['strain']}",
                "-1",f"{variables['fastq_trimed'][0]}",
                "-2",f"{variables['fastq_trimed'][1]}",
                "-S",f"{variables['directory']}/alignment.sam",
                "--no-unal",
                f"--threads {cpus}",
                f"2>'{variables['directory']}/bowtie_align_log.log'"]
        
        subprocess_cmd(send)
        
    else:
        print(f'Found {variables["directory"]}/alignment.sam, skipping alignment')

    if variables["remove"]:
        os.remove(variables['fastq_trimed'][0])
        os.remove(variables['fastq_trimed'][1])

def tn_compiler(variables):
    import gzip
    variables["fastq_trimed"] = f'{variables["directory"]}/processed_reads_1.fastq'
    
    if path_finder(variables['sequencing_files'], '*.gz') == None:
        
        pathing = []
        for filename in glob.glob(os.path.join(variables['sequencing_files'], '*.fastq')):
            pathing.append(filename) 
                      
        for file in pathing:
            with open(file, "rb") as firstfile, open(variables["fastq_trimed"],"wb") as secondfile:
                for line in firstfile:
                    secondfile.write(line)
        
    else:
    
        pathing = []
        for filename in glob.glob(os.path.join(variables['sequencing_files'], '*.gz')):
            pathing.append(filename) 
                      
        for file in pathing:
            with gzip.open(file, "rb") as firstfile, open(variables["fastq_trimed"],"wb") as secondfile:
                for line in firstfile:
                    secondfile.write(line)
                
    return variables

def tn_trimmer_single(variables):
    
    variables["fastq_trimed"] = f'{variables["directory"]}/processed_reads_1.fastq'
    
    if not os.path.isfile(variables["fastq_trimed"]):
    
        reads_trimer.main([f"{variables['sequencing_files']}",
                           f"{variables['directory']}",
                           f"{variables['sequence']}",
                           f"{variables['seq_type']}",
                           f"{variables['barcode']}",
                           f"{variables['phred']}",
                           f"{variables['barcode_up']}",
                           f"{variables['barcode_down']}",
                           f"{variables['barcode_up_miss']}",
                           f"{variables['barcode_down_miss']}",
                           f"{variables['barcode_up_phred']}",
                           f"{variables['barcode_down_phred']}",
                           f"{variables['tn_mismatches']}",
                           f"{variables['trimmed_after_tn']}"])
    
    else:
        print(f"Found {variables['fastq_trimed']}, skipping trimming")
    
    return variables

def tn_trimmer_paired(variables):
    try:
        variables['sequencing_files']
    except IndexError:
        raise IndexError("Make sure you selected the correct sequencing type, or that the .gz files are labelled accordingly")
    
    variables["fastq_trimed"] = [f'{variables["directory"]}/processed_reads_1.fastq']+\
                                [f'{variables["directory"]}/processed_reads_2.fastq']
    
    if not (os.path.isfile(variables["fastq_trimed"][0])) & (os.path.isfile(variables["fastq_trimed"][1])):
    
        reads_trimer.main([f"{variables['sequencing_files']}",
                           f"{variables['directory']}",
                           f"{variables['sequence']}",
                           f"{variables['seq_type']}",
                           f"{variables['barcode']}",
                           f"{variables['phred']}",
                           f"{variables['sequencing_files_r']}",
                           f"{variables['barcode_up']}",
                           f"{variables['barcode_down']}",
                           f"{variables['barcode_up_miss']}",
                           f"{variables['barcode_down_miss']}",
                           f"{variables['barcode_up_phred']}",
                           f"{variables['barcode_down_phred']}",
                           f"{variables['tn_mismatches']}",
                           f"{variables['trimmed_after_tn']}"])

    return variables

def sam_parser(variables):
    
    if not os.path.isfile(f'{variables["directory"]}/{variables["strain"]}.csv'):

        sam_to_insertions.main([f"{variables['directory']}",
                                f"{variables['strain']}",
                                f"{variables['seq_type']}",
                                f"{variables['read_threshold']}",
                                f"{variables['read_value']}",
                                f"{variables['barcode']}",
                                f"{variables['MAPQ']}",
                                f"{variables['annotation_file']}",
                                f"{variables['intergenic_size_cutoff']}"])

def essentials(variables):
    Essential_Finder.main([f'{variables["directory"]}',
                           f'{variables["strain"]}',
                           f'{variables["annotation_type"]}',
                           f'{variables["annotation_folder"]}',
                           f'{variables["subdomain_length_down"]}',
                           f'{variables["subdomain_length_up"]}',
                           f'{variables["pvalue"]}',
                           f"{variables['intergenic_size_cutoff']}",
                           f"{variables['domain_uncertain_threshold']}"])

def insertions_plotter(variables):     
    insertions_over_genome_plotter.main([f'{variables["directory"]}',
                                         f'{variables["seq_file"]}',
                                         f'{variables["annotation_type"]}',
                                         f'{variables["strain"]}'])
        
def subprocess_cmd(command):
    try:
        return subprocess.check_output(command)
    except subprocess.CalledProcessError as e:
        return e.output.decode()

def input_parser(variables):
    
    parser = argparse.ArgumentParser()
    parser.add_argument("-s",help="Strain name. Must match the annotation (FASTA/GB) file names")
    parser.add_argument("-sd",help="The full path to the sequencing files FOLDER")
    parser.add_argument("--sd_2",help="The full path to the pair ended sequencing files FOLDER (needs to be different from the first folder)")
    parser.add_argument("-ad",help="The full path to the directory with the annotation (FASTA/GB) files")
    parser.add_argument("-at",help="Annotation Type (Genbank)")
    parser.add_argument("-st",help="Sequencing type (Paired-ended (PE)/Single-ended(SE)")
    parser.add_argument("--tn",nargs='?',const=None,help="Transposon border sequence (tn5: GATGTGTATAAGAGACAG). Required for triming and proper mapping")
    parser.add_argument("--m",nargs='?',const=None,help="Mismatches in the transposon border sequence (default is 0)")
    parser.add_argument("--k",nargs='?',const=False,help="Remove intermediate files. Default is yes, remove.")
    parser.add_argument("--e",nargs='?',const=False,help="Run only the essential determing script. required the all_insertions_STRAIN.csv file to have been generated first.")
    parser.add_argument("--t",nargs='?',const=False,help="Trims to the indicated nucleotides length AFTER finding the transposon sequence. For example, 100 would mean to keep the 100bp after the transposon (this trimmed read will be used for alignement after)")
    parser.add_argument("--b",nargs='?',const=False,help="Run with barcode extraction")
    parser.add_argument("--b1",nargs='?',const=False,help="upstream barcode sequence (example: ATC)")
    parser.add_argument("--b2",nargs='?',const=False,help="downstream barcode sequence (example: CTA)")
    parser.add_argument("--b1m",nargs='?',const=False,help="upstream barcode sequence mismatches")
    parser.add_argument("--b2m",nargs='?',const=False,help="downstream barcode sequence mismatches")
    parser.add_argument("--b1p",nargs='?',const=False,help="upstream barcode sequence Phred-score filtering. Default is no filtering")
    parser.add_argument("--b2p",nargs='?',const=False,help="downstream barcode sequence Phred-score filtering. Default is no filtering")
    parser.add_argument("--rt",nargs='?',const=False,help="Read threshold number")
    parser.add_argument("--ne",nargs='?',const=False,help="Run without essential Finding")
    parser.add_argument("--ph",nargs='?',const=1,help="Phred Score (removes reads where nucleotides have lower phred scores)")
    parser.add_argument("--mq",nargs='?',const=0,help="Bowtie2 MAPQ threshold")
    parser.add_argument("--ig",nargs='?',const=0,help="The number of bp up and down stream of any gene to be considered an intergenic region")
    parser.add_argument("--dut",nargs='?',const=0,help="fraction of the minimal amount of 'too small domains' in a gene before the entire gene is deemed uncertain for essentiality inference")
    parser.add_argument("--pv",nargs='?',const=None,help="Essential Finder pvalue threshold for essentiality determination")
    parser.add_argument("--sl5",nargs='?',const=None,help="5' gene trimming percent for essentiality determination (number between 0 and 1)")
    parser.add_argument("--sl3",nargs='?',const=None,help="3' gene trimming percent for essentiality determination (number between 0 and 1)")
    
    args = parser.parse_args()

    if (args.s is None) or (args.sd is None) or (args.ad is None) or (args.at is None) or (args.st is None):
        print(parser.print_usage())
        raise ValueError("No arguments given")
    
    variables["version"]="1.0.5"
    print(f'\nVersion: {variables["version"]}\n')
    
    variables["full"]=True
    if args.e is not None:
        variables["full"] = False
        print("Running in essentials finder only mode\n")
        
    variables["trim"]=False
    variables["tn_mismatches"] = 0 
    if args.tn is not None:
        variables["trim"] = True

        if args.m is not None:
            variables["tn_mismatches"] = int(args.m)   

    variables["remove"]=True
    if args.k is False:
        variables["remove"]=False
        print("Keeping all intermediate files\n")
        
    variables["trimmed_after_tn"]=-1
    if args.t is not None:
        variables["trimmed_after_tn"]=int(args.t)
        
    variables["barcode"]=False
    if args.b is not None:
        variables["barcode"] = True
        print("Running with barcode finding\n")
        
    variables["intergenic_size_cutoff"]=0
    if args.ig is not None:
        variables["intergenic_size_cutoff"] = int(args.ig)
    
    variables["barcode_up"] = None
    variables["barcode_down"] = None
    variables["barcode_up_miss"] = 0 
    variables["barcode_down_miss"] = 0 
    variables["barcode_up_phred"] = 1
    variables["barcode_down_phred"] = 1
    if variables["barcode"]:

        if args.b1p is not None:
            variables["barcode_down_phred"] = int(args.b2p)
            if variables["barcode_down_phred"] < 1:
                variables["barcode_down_phred"]  = 1
                
        if args.b2p is not None:
            variables["barcode_down_phred"] = int(args.b2p)
            if variables["barcode_down_phred"] < 1:
                variables["barcode_down_phred"]  = 1
        
        if args.b1m is not None:
            variables["barcode_up_miss"] = int(args.b1m)

        if args.b2m is not None:
            variables["barcode_down_miss"] = int(args.b2m)
        
        if args.b1 is not None:
            variables["barcode_up"] = args.b1

        if args.b2 is not None:
            variables["barcode_down"] = args.b2

    variables["read_threshold"]=False
    variables["read_value"] = 0
    if args.rt is not None:
        variables["read_threshold"] = True
        variables["read_value"] = args.rt
        
    variables["essential_find"]=True
    if args.ne is not None:
        variables["essential_find"]=False
        print("Running without essential finding\n")
        
    variables["pvalue"]=0.01
    if args.pv is not None:
        variables["pvalue"]=args.pv
        
    variables["domain_uncertain_threshold"]=0.75
    if args.dut is not None:
        variables["domain_uncertain_threshold"]=float(args.dut)
    
    variables["subdomain_length_up"]=1
    if args.sl5 is not None:
        variables["subdomain_length_up"]=args.sl5
        
    variables["subdomain_length_down"]=0
    if args.sl3 is not None:
        variables["subdomain_length_down"]=args.sl3
    
    if args.st == "PE":
        variables["sequencing_files_r"] = args.sd_2
        
    variables["sequencing_files"] = args.sd
    variables['phred']=int(args.ph)
    variables['MAPQ']=int(args.mq)
    variables["strain"]=args.s
    variables["annotation_type"]=args.at.lower()
    variables["annotation_folder"]=args.ad
    variables["seq_type"]=args.st
    variables["sequence"]=args.tn

    return variables

def variables_initializer():
    variables = {}
    variables = input_parser(variables)
    variables = path_finder_seq(variables)
    cmd_printer_path = os.path.join(variables['directory'],'cmd_input' + ".txt")
    with open(cmd_printer_path,'w+') as current:
        for key in variables:
            current.write(str(key)+':'+str(variables[key])+'\n')
    return variables

def main():
    variables = variables_initializer()
    
    if variables["full"]:
        variables = bowtie_index_maker(variables)

        if variables["seq_type"] == "PE":
            
            print("Running in paired-end mode")
            variables["fastq_trimed"] = [variables['sequencing_files'],\
                                         variables['sequencing_files_r']]
            if variables["trim"]:
                variables = tn_trimmer_paired(variables)

            print("Aligning Sequences")
            bowtie_aligner_maker_paired(variables)
            
        elif variables["seq_type"] == "SE":
            
            print("Running in single-end mode")
            variables["fastq_trimed"] = variables['sequencing_files']

            if variables["trim"]:
                variables = tn_trimmer_single(variables)
            else:
                variables = tn_compiler(variables)
                
            print("Aligning Sequences")
            bowtie_aligner_maker_single(variables)
        
        print("Parsing insertions")
        sam_parser(variables)
        if variables["remove"]:
            os.remove(f"{variables['directory']}/alignment.sam")
    
        insertions_plotter(variables)
    
    if variables["essential_find"]:
        print("Finding Essentials")
        essentials(variables)
    
if __name__ == "__main__":
    main() 