import os,glob
import subprocess
from tnseeker import Essential_Finder,reads_trimer,sam_to_insertions,insertions_over_genome_plotter # type: ignore
from tnseeker.extras.helper_functions import cpu,colourful_errors
import argparse
from colorama import Fore
import pkg_resources

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
        colourful_errors("FATAL",
                 "check that .fastq files exist in the indicated folder.")
        raise Exception
        
    if variables["fasta"] == None:
        colourful_errors("FATAL",
                f"check that the {variables['strain']}.fasta file exist in the indicated folder.")
        raise Exception
    
    if variables["annotation_type"] == "gb":
        extention = '*.gb'
        if path_finder(variables,extention) == None:
            extention = '*.gbk'
        variables["annotation_file"]=path_finder(variables,extention)
        variables["genome_file"]=path_finder(variables,extention)

    elif variables["annotation_type"] == "gff":
        variables["annotation_file"]=path_finder(variables,'*.gff')
        variables["genome_file"]=path_finder(variables,'*.fasta')

    if variables["annotation_file"] == None:
        colourful_errors("FATAL",
            "check that the annotation file exists in the indicated folder.")
        raise Exception

    return variables

def bowtie_index_maker(variables):
    
    variables["index_dir"] = f"{variables['directory']}/indexes/"

    if not os.path.isdir(variables["index_dir"]):
        os.mkdir(variables["index_dir"])
            
        send = ["bowtie2-build",
                variables['fasta'],
                f"{variables['index_dir']}{variables['strain']}"]

        subprocess_cmd(send)
    return variables
    
def bowtie_aligner_maker_single(variables):
    
    if not os.path.isfile(f'{variables["directory"]}/alignment.sam'):
    
        send = ["bowtie2",
                "--end-to-end",
                "-x",f"{variables['index_dir']}{variables['strain']}",
                "-U",f"{variables['fastq_trimed']}",
                "-S",f"{variables['directory']}/alignment.sam",
                "--no-unal",
                f"--threads {variables['cpus']}",
                f"2>'{variables['directory']}/bowtie_align_log.log'"]
        
        subprocess_cmd(send)
        
    else:
        colourful_errors("INFO",
            f"Found {variables['directory']}/alignment.sam, skipping alignment.")

    if variables["remove"]:
        os.remove(variables['fastq_trimed'])
    
def bowtie_aligner_maker_paired(variables):
    
    if not os.path.isfile(f'{variables["directory"]}/alignment.sam'):
    
        send = ["bowtie2",
                "--end-to-end",
                "-x",f"{variables['index_dir']}{variables['strain']}",
                "-1",f"{variables['fastq_trimed'][0]}",
                "-2",f"{variables['fastq_trimed'][1]}",
                "-S",f"{variables['directory']}/alignment.sam",
                "--no-unal",
                f"--threads {variables['cpus']}",
                f"2>'{variables['directory']}/bowtie_align_log.log'"]
        
        subprocess_cmd(send)
        
    else:
        colourful_errors("INFO",
            f"Found {variables['directory']}/alignment.sam, skipping alignment.")

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
                           f"{variables['trimmed_after_tn']}",
                           f"{variables['cpus']}"
                           ]
                        )
    
    else:
        colourful_errors("INFO",
            f"Found {variables['fastq_trimed']}, skipping trimming.")
    return variables

def tn_trimmer_paired(variables):
    try:
        variables['sequencing_files']
    except IndexError:
        colourful_errors("FATAL",
            "Make sure that you have selected the correct sequencing type, or that the .gz files are named correctly.")
        raise IndexError
    
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
                           f"{variables['trimmed_after_tn']}",
                           f"{variables['cpus']}"
                           ]
                        )

    return variables

def sam_parser(variables):
    
    if not os.path.isfile(f'{variables["directory"]}/all_insertions_{variables["strain"]}.csv'):

        sam_to_insertions.main([f"{variables['directory']}",
                                f"{variables['strain']}",
                                f"{variables['seq_type']}",
                                f"{variables['read_threshold']}",
                                f"{variables['read_value']}",
                                f"{variables['barcode']}",
                                f"{variables['MAPQ']}",
                                f"{variables['annotation_file']}",
                                f"{variables['intergenic_size_cutoff']}",
                                f"{variables['cpus']}"
                                ]
                            )
        
    else:
        colourful_errors("INFO",
            f"Found all_insertions_{variables['strain']}.csv, skipping tn insertion parsing.")

def essentials(variables):
    Essential_Finder.main([f'{variables["directory"]}',
                           f'{variables["strain"]}',
                           f'{variables["annotation_type"]}',
                           f'{variables["annotation_folder"]}',
                           f'{variables["subdomain_length_up"]}',
                           f'{variables["subdomain_length_down"]}',
                           f'{variables["pvalue"]}',
                           f"{variables['intergenic_size_cutoff']}",
                           f"{variables['domain_uncertain_threshold']}",
                           f"{variables['cpus']}",
                           ]
                        )

def insertions_plotter(variables):     
    insertions_over_genome_plotter.main([f'{variables["directory"]}',
                                         f'{variables["genome_file"]}',
                                         f'{variables["annotation_file"]}',
                                         f'{variables["annotation_type"]}',
                                         f'{variables["barcode"]}',
                                         f'{variables["strain"]}'
                                         ]
                                        )
        
def subprocess_cmd(command):
    try:
        return subprocess.check_output(command)
    except subprocess.CalledProcessError as e:
        return e.output.decode()

def test_functionalities():
    result_bowtie = subprocess.run(['bowtie2', '-h'], capture_output=True, text=True)
    if result_bowtie.returncode == 0:
        colourful_errors("INFO",
            "Bowtie2 is working as intended.")
    else:
        colourful_errors("FATAL",
            "Bowtie2 is not working as intended. Check instalation and/or that it is on path.")

    result_blast = subprocess.run(['tblastn', '-h'], capture_output=True, text=True)
    if result_blast.returncode == 0:
        colourful_errors("INFO",
            "Blast is working as intended.")
    else:
        colourful_errors("FATAL",
            "Blast is not working as intended. Check instalation and/or that it is on path.")

    if (result_blast.returncode == 0) & (result_bowtie.returncode == 0):
        colourful_errors("INFO",
            "Testing Tnseeker. Please hold, this might take several minutes.")

        data_dir = pkg_resources.resource_filename(__name__, 'data/test/')
        result_full = subprocess.run(["python","-m", "tnseeker", 
                                        "-s","test",
                                        "-sd", data_dir,
                                        "-ad", data_dir,
                                        "-at", "gb",
                                        "-st", "SE",
                                        "--tn", "AGATGTGTATAAGAGACAG",
                                        "--ph", "10",
                                        "--mq", "40",
                                        "--sl5", "0.05", "--sl3", "0.9",
                                        "--k"], capture_output=True, text=True)
        
        if result_full.returncode == 0:
            colourful_errors("INFO",
                "Tnseeker is working as intended.")
        else:
            print(result_full.stdout)
            print(result_full.stderr)
            colourful_errors("FATAL",
                "Tnseeker is not working as intended. Check errors.")

    if (result_blast.returncode == 0) & (result_bowtie.returncode == 0) & (result_full.returncode == 0):
        colourful_errors("INFO",
                " All tests passed.")
    print("\n")
    
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
    parser.add_argument("--tst",nargs='?',const=True,help="Test the program functionalities and instalations")
    parser.add_argument("--cpu",nargs='?',const=None,help="Define the number of threads (must be and integer)")

    args = parser.parse_args()
                                                             
    print("\n")
    print(f"{Fore.RED} Welcome to{Fore.RESET}")
    print(f"{Fore.RED} ████████╗███╗   ██╗ {Fore.RESET}███████╗███████╗███████╗██╗  ██╗███████╗██████╗ ")
    print(f"{Fore.RED} ╚══██╔══╝████╗  ██║ {Fore.RESET}██╔════╝██╔════╝██╔════╝██║ ██╔╝██╔════╝██╔══██╗")
    print(f"{Fore.RED}    ██║   ██╔██╗ ██║ {Fore.RESET}███████╗█████╗  █████╗  █████╔╝ █████╗  ██████╔╝")
    print(f"{Fore.RED}    ██║   ██║╚██╗██║ {Fore.RESET}╚════██║██╔══╝  ██╔══╝  ██╔═██╗ ██╔══╝  ██╔══██╗")
    print(f"{Fore.RED}    ██║   ██║ ╚████║ {Fore.RESET}███████║███████╗███████╗██║  ██╗███████╗██║  ██║")
    print(f"{Fore.RED}    ╚═╝   ╚═╝  ╚═══╝ {Fore.RESET}╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝")   
    
    variables["version"]="1.0.7.4"
    
    print(f"{Fore.RED}            Version: {Fore.RESET}{variables['version']}")
    print("\n")  
    
    if args.tst is not None:
        test_functionalities()
        exit()
        
    if (args.s is None) or (args.sd is None) or (args.ad is None) or (args.at is None) or (args.st is None):
        print(parser.print_usage())
        colourful_errors("FATAL",
                 "No arguments given.")
        raise ValueError

    variables["full"]=True
    if args.e is not None:
        variables["full"] = False

    variables["trim"]=False
    variables["tn_mismatches"] = 0 
    if args.tn is not None:
        variables["trim"] = True

        if args.m is not None:
            variables["tn_mismatches"] = int(args.m)   

    variables["remove"]=True
    if args.k is False:
        variables["remove"]=False

    variables["trimmed_after_tn"]=-1
    if args.t is not None:
        variables["trimmed_after_tn"]=int(args.t)
        
    variables["barcode"]=False
    if args.b is not None:
        variables["barcode"] = True

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
            variables["barcode_up_phred"] = int(args.b2p)
            if variables["barcode_up_phred"] < 1:
                variables["barcode_up_phred"]  = 1
                
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

    variables["pvalue"]=0.1
    if args.pv is not None:
        variables["pvalue"]=args.pv
        
    variables["domain_uncertain_threshold"]=0.75
    if args.dut is not None:
        variables["domain_uncertain_threshold"]=float(args.dut)
    
    variables["subdomain_length_up"]=0
    if args.sl5 is not None:
        variables["subdomain_length_up"]=args.sl5
        
    variables["subdomain_length_down"]=1
    if args.sl3 is not None:
        variables["subdomain_length_down"]=args.sl3

    if args.cpu is not None:
        variables["cpus"]=int(args.cpu)
    else:
        variables["cpus"]=cpu()
    
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
    
    print(f"{Fore.YELLOW} -- Parameters -- {Fore.RESET}\n")
    with open(cmd_printer_path,'w+') as current:
        for key in variables:
            current.write(str(key)+' : '+str(variables[key])+'\n')
            print(f"{Fore.GREEN} {key}:{Fore.RESET} {variables[key]}")
    print(f"\n{Fore.YELLOW} ---- {Fore.RESET}\n")
    return variables

def main():

    variables = variables_initializer()
    
    if variables["full"]:
        variables = bowtie_index_maker(variables)
        
        if variables["seq_type"] == "PE":

            variables["fastq_trimed"] = [variables['sequencing_files'],\
                                         variables['sequencing_files_r']]
            if variables["trim"]:

                colourful_errors("INFO",
                    "Getting that .fastq ready.")
                
                variables = tn_trimmer_paired(variables)
            
            colourful_errors("INFO",
                    "Aligning reads to the reference genome.")
            
            bowtie_aligner_maker_paired(variables)
            
        elif variables["seq_type"] == "SE":

            variables["fastq_trimed"] = variables['sequencing_files']

            if variables["trim"]:
                colourful_errors("INFO",
                    "Getting that .fastq ready.")
                
                variables = tn_trimmer_single(variables)

            else:
                colourful_errors("INFO",
                    "Compiling those .fastq.")
                
                variables = tn_compiler(variables)
            
            colourful_errors("INFO",
                    "Aligning reads to the reference genome.")

            bowtie_aligner_maker_single(variables)
        
        sam_parser(variables)
        if variables["remove"]:
            if variables["barcode"]:
                os.remove(f"{variables['directory']}/barcoded_align.sam")
            os.remove(f"{variables['directory']}/alignment.sam")
    
        insertions_plotter(variables)
    
    if variables["essential_find"]:
        colourful_errors("INFO",
                    "Infering essential genes.")
        
        essentials(variables)
    
    colourful_errors("INFO",
            "Analysis Finished.")

if __name__ == "__main__":
    main()