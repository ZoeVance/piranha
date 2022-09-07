#!/usr/bin/env python3
from piranha import __version__

from piranha.input_parsing import initialising as init

from piranha.utils import misc
from piranha.utils import dependency_checks
from piranha.utils import data_install_checks
from piranha.input_parsing import analysis_arg_parsing
from piranha.input_parsing import directory_setup
from piranha.input_parsing import input_qc
from piranha.report.make_report import make_output_report
import piranha.utils.custom_logger as custom_logger
from piranha.utils.log_colours import green,cyan,red
from piranha.utils.config import *

import os
import sys
import yaml
import argparse
import snakemake

cwd = os.getcwd()
thisdir = os.path.abspath(os.path.dirname(__file__))

def main(sysargs = sys.argv[1:]):
 
    parser = argparse.ArgumentParser(add_help=False,
    description=misc.preamble(__version__),
    usage='''
\tpiranha -c <config.yaml> [options]
\tpiranha -i input.csv [options]
''')

    i_group = parser.add_argument_group('Input options')
    i_group.add_argument('-c',"--config", action="store",help="Input config file in yaml format, all command line arguments can be passed via the config file.", dest="config")
    i_group.add_argument('-i','--readdir',help="Path to the directory containing fastq read files",dest="readdir")
    i_group.add_argument('-b','--barcodes-csv',help="CSV file describing which barcodes were used on which sample",dest="barcodes_csv")
    i_group.add_argument("-r","--reference-sequences",action="store",dest="reference_sequences",help="Custom reference sequences file.")
    i_group.add_argument("-pc","--positive-control",action="store",help=f"Sample name of positive control. Default: `{VALUE_POSITIVE}`")
    i_group.add_argument("-nc","--negative-control",action="store",help=f"Sample name of negative control. Default: `{VALUE_NEGATIVE}`")

    analysis_group = parser.add_argument_group('Analysis options')
    analysis_group.add_argument("-m","--analysis-mode",action="store",help=f"Specify analysis mode to run. Options: `vp1`. Default: `{VALUE_ANALYSIS_MODE}`")
    analysis_group.add_argument("--medaka-model",action="store",help=f"Medaka model to run analysis using. Default: {VALUE_DEFAULT_MEDAKA_MODEL}")
    analysis_group.add_argument("--medaka-list-models",action="store_true",help="List available medaka models and exit.")
    analysis_group.add_argument("-n","--min-read-length",action="store",type=int,help=f"Minimum read length. Default: {READ_LENGTH_DEFAULT_VP1[0]}")
    analysis_group.add_argument("-x","--max-read-length",action="store",type=int,help=f"Maximum read length. Default: {READ_LENGTH_DEFAULT_VP1[1]}")
    analysis_group.add_argument("-d","--min-read-depth",action="store",type=int,help=f"Minimum read depth required for consensus generation. Default: {VALUE_MIN_READS}")
    analysis_group.add_argument("-p","--min-read-pcent",action="store",type=int,help=f"Minimum percentage of sample required for consensus generation. Default: {VALUE_MIN_PCENT}")

    o_group = parser.add_argument_group('Output options')
    o_group.add_argument('-o','--outdir', action="store",help=f"Output directory. Default: `{VALUE_OUTPUT_PREFIX}-2022-XX-YY`")
    o_group.add_argument('-pub','--publishdir', action="store",help=f"Output publish directory. Default: `{VALUE_OUTPUT_PREFIX}-2022-XX-YY`")
    o_group.add_argument('-pre','--output-prefix',action="store",help=f"Prefix of output directory & report name: Default: `{VALUE_OUTPUT_PREFIX}`",dest="output_prefix")
    o_group.add_argument('--datestamp', action="store",help="Append datestamp to directory name when using <-o/--outdir>. Default: <-o/--outdir> without a datestamp")
    o_group.add_argument('--overwrite', action="store_true",help="Overwrite output directory. Default: append an incrementing number if <-o/--outdir> already exists")
    o_group.add_argument('-temp','--tempdir',action="store",help="Specify where you want the temp stuff to go. Default: `$TMPDIR`")
    o_group.add_argument("--no-temp",action="store_true",help="Output all intermediate files. For development/ debugging purposes",dest="no_temp")

    misc_group = parser.add_argument_group('Misc options')
    misc_group.add_argument('--language',action="store",help=f"Report language. Options: English, French. Default: {VALUE_LANGUAGE}")
    misc_group.add_argument('--runname',action="store",help=f"Run name to appear in report. Default: {VALUE_RUN_NAME}")
    misc_group.add_argument('--username',action="store",help="Username to appear in report. Default: no user name")
    misc_group.add_argument('--institute',action="store",help="Institute name to appear in report. Default: no institute name")
    misc_group.add_argument('-t', '--threads', action='store',dest="threads",type=int,help="Number of threads. Default: 1")
    misc_group.add_argument("--verbose",action="store_true",help="Print lots of stuff to screen")
    misc_group.add_argument("-v","--version", action='version', version=f"piranha {__version__}")
    misc_group.add_argument("-h","--help",action="store_true",dest="help")

    """
    Exit with help menu if no args supplied
    """

    if len(sysargs)<1: 
        parser.print_help()
        sys.exit(0)
    else:
        args = parser.parse_args(sysargs)
        if args.help:
            parser.print_help()
            sys.exit(0)

    dependency_checks.check_dependencies(dependency_list, module_list)

    # Initialise config dict
    config = init.setup_config_dict(cwd,args.config)
    # Checks access to package data and grabs the snakefile
    analysis_arg_parsing.analysis_mode(args.analysis_mode,config)
    data_install_checks.check_install(args.language,config)

    snakefile = data_install_checks.get_snakefile(thisdir,config[KEY_ANALYSIS_MODE])
    # Threads and verbosity to config
    

    # Sort out where the query info is coming from, csv or id string, optional fasta seqs.
    # Checks if they're real files, of the right format and that QC args sensible values.
    analysis_arg_parsing.medaka_options_parsing(args.medaka_model,args.medaka_list_models,config)
    analysis_arg_parsing.analysis_group_parsing(args.min_read_length,args.max_read_length,args.min_read_depth,args.min_read_pcent,config)
    input_qc.parse_input_group(args.barcodes_csv,args.readdir,args.reference_sequences,config)
    input_qc.control_group_parsing(args.positive_control, args.negative_control, config)

    # sets up the output dir, temp dir, and data output desination
    directory_setup.output_group_parsing(args.outdir, args.output_prefix, args.overwrite, args.datestamp, args.tempdir, args.no_temp, config)
    # ready to run? either verbose snakemake or quiet mode
    init.misc_args_to_config(args.verbose,args.threads,args.username,args.institute,args.runname,config)
    init.set_up_verbosity(config)

    preprocessing_snakefile = data_install_checks.get_snakefile(thisdir,"preprocessing")

    if config[KEY_VERBOSE]:
        print(red("\n**** CONFIG ****"))
        for k in sorted(config):
            print(green(f" - {k}: ") + f"{config[k]}")
        status = snakemake.snakemake(preprocessing_snakefile, printshellcmds=True, forceall=True, force_incomplete=True,
                                    workdir=config[KEY_TEMPDIR], config=config, cores=config[KEY_THREADS],lock=False
                                    )
    else:
        logger = custom_logger.Logger()
        status = snakemake.snakemake(preprocessing_snakefile, printshellcmds=False, forceall=True, force_incomplete=True,
                                    workdir=config[KEY_TEMPDIR], config=config, cores=config[KEY_THREADS],lock=False,
                                    quiet=True,log_handler=logger.log_handler
                                    )

    if status: # translate "success" into shell exit code of 0
        with open(os.path.join(config[KEY_TEMPDIR],PREPROCESSING_CONFIG),"r") as f:
            preprocessing_config = yaml.safe_load(f)
        

        if config[KEY_VERBOSE]:

            print(red("\n**** CONFIG ****"))
            for k in sorted(config):
                print(green(f" - {k}: ") + f"{config[k]}")
            status = snakemake.snakemake(snakefile, printshellcmds=True, forceall=True, force_incomplete=True,
                                        workdir=config[KEY_TEMPDIR], config=preprocessing_config, cores=config[KEY_THREADS],lock=False
                                        )
        else:
            logger = custom_logger.Logger()
            status = snakemake.snakemake(snakefile, printshellcmds=False, forceall=True, force_incomplete=True,
                                        workdir=config[KEY_TEMPDIR], config=preprocessing_config, cores=config[KEY_THREADS],lock=False,
                                        quiet=True,log_handler=logger.log_handler
                                        )
        if status: 
            report =os.path.join(config[KEY_OUTDIR],OUTPUT_REPORT)
            summary_csv=os.path.join(config[KEY_TEMPDIR],PREPROCESSING_SUMMARY)
            composition_csv=os.path.join(config[KEY_TEMPDIR],SAMPLE_COMPOSITION)
            sample_seqs=os.path.join(config[KEY_OUTDIR],"published_data",SAMPLE_SEQS)

            make_output_report(report,summary_csv,composition_csv,sample_seqs,config)

            return 0
        

        return 1
    return 1



if __name__ == '__main__':
    main()
