#!/usr/bin/env python3
import os
import collections
from Bio import SeqIO
import csv
from itertools import groupby, count
import pysam
import pandas as pd
import json
# from cigar import Cigar

from piranha.utils.config import *

def id_reference_cns(aln):
    ref_seq = False
    for record in SeqIO.parse(aln, KEY_FASTA):
        if not ref_seq:
            ref_seq = str(record.seq).upper()
        else:
            cns_seq = str(record.seq).upper()
    
    return ref_seq,cns_seq

def merge_indels(indel_list,prefix):
    if indel_list:
        groups = groupby(indel_list, key=lambda item, c=count():item-next(c))
        tmp = [list(g) for k, g in groups]
        merged_indels = []
        for i in tmp:
            indel = f"{i[0]}:{prefix}{len(i)}"
            merged_indels.append(indel)
        return merged_indels
    
    return indel_list

def find_variants(reference_seq,query_seq):

    non_amb = ["A","T","G","C"]
    
    variants = []

    snps =[]
    insertions = []
    deletions = []

    for i in range(len(query_seq)):
        # bases[0] == query seq
        # bases[1] == ref seq
        bases = [query_seq[i],reference_seq[i]]
        if bases[0] != bases[1]:
            
            if bases[0] in non_amb and bases[1] in non_amb:
                #if neither of them are ambiguous
                snp = f"{i+1}:{bases[1]}{bases[0]}" # position-reference-query
                snps.append(snp)
            elif bases[0]=='-':
                #if there's a gap in the query, means a deletion
                deletions.append(i+1)
            elif bases[1]=='-':
                #if there's a gap in the ref, means an insertion
                insertions.append(i+1)

    insertions = merge_indels(insertions,"ins")
    deletions = merge_indels(deletions,"del")

    for var_list in [snps,insertions,deletions]:
        for var in var_list:
            variants.append(var)

    variants = sorted(variants, key = lambda x : int(x.split(":")[0]))

    return variants

def find_ambiguity_pcent(query_seq):
    ambiguity_count = 0
    for i in query_seq:
        if i not in ["A","T","G","C","-"]:
            ambiguity_count +=1
    ambiguity_pcent = round(100*(ambiguity_count/len(query_seq)),2)
    return ambiguity_pcent

def parse_variants(alignment,out_report,barcode,reference):

    ref_seq,cns_seq = id_reference_cns(alignment)
    variants = find_variants(ref_seq,cns_seq)
    var_string = ";".join(variants)
    with open(out_report,"w") as fw:
        fw.write(f"{barcode},{reference},{len(variants)},{var_string}\n")


def join_variant_files(header_fields,in_files,output):
    with open(output,"w") as fw:
        header = ",".join(header_fields) + "\n"
        fw.write(header)
        for in_file in in_files:
            with open(in_file, "r") as f:
                for l in f:
                    l = l.rstrip("\n")
                    fw.write(f"{l}\n")


#Get the reference bases at each position and stick it in a dictionary
def ref_dict_maker(ref_fasta):
    ref_dict = {}
    ref_fasta = pysam.FastaFile(ref_fasta)
    for idx, base in enumerate(ref_fasta.fetch(ref_fasta.references[0])):
        ref_dict[idx] = base

    return ref_dict

#function to calculate the percentage of non ref bases at a given position
def non_ref_prcnt_calc(pos,pileup_dict,ref_dict):
    non_ref_prcnt = 0
    ref_count = 0
    total = 0
    if ref_dict[pos] != "N":
        ref_base = ref_dict[pos] + " reads"
        for key in pileup_dict:
            if key != "Position":
                total += pileup_dict[key]
        ref_count = pileup_dict[ref_base]
        if (total == 0):
            non_ref_prcnt = 0
        elif (ref_count == 0):
            non_ref_prcnt = 100
        else:
            non_ref_prcnt = round((100 - ((ref_count / total) * 100)), 2)

    return non_ref_prcnt

def parse_variant_file(var_file):
    var_dict = collections.defaultdict(dict)
    with open(var_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            
            variants = row["variants"].split(";")
            if variants != ['']:
                for var in variants:
                    pos,snp = var.split(":")
                    ref,alt = snp

                    var_dict[row[KEY_REFERENCE]][int(pos)] = [ref,alt]

    return var_dict

def parse_vcf(vcf):
    var_dict = {}

    vcf_file = pysam.VariantFile(vcf)
    for rec in vcf_file.fetch():
        
        length_var = len(rec.ref)
        qual = round(rec.qual,2)
        start_pos = rec.pos
        
        if length_var >1:
            print(start_pos, rec.ref,rec.alts)
            for i in range(length_var):
                print(i, rec.ref[i])
                print(i, rec.alts[0][i])
                #Poliovirus3-Sabin_AY184221	473	.	TC	T	2.494	PASS	.	GT:GQ	1:2

                var_dict[start_pos] = [rec.ref[i],rec.alts[0][i],qual]
                start_pos+=1
        else:
             var_dict[rec.pos] = [rec.ref,rec.alts[0],qual]
    return var_dict

def add_to_cooccurance_analysis(pileupread,read_vars,genome_position):
    if not pileupread.is_del:
        read_pos = pileupread.query_position
        read_base = pileupread.alignment.query_sequence[read_pos]
        read_vars[pileupread.alignment.query_name][genome_position]= read_base
#             elif pileupread.is_refskip:
#                 print("ref",pileupcolumn.pos,pileupread.alignment.query_name)
#                 read_pos = pileupread.query_position         
#                 read_vars[pileupread.alignment.query_name][pileupcolumn.pos] = "ref"
    elif pileupread.is_del:
        read_vars[pileupread.alignment.query_name][genome_position] = "-"
    return read_vars


#Use mpileup to get bases per read at each postion, then calculate % vs ref for each
def pileupper(bamfile,ref_dict,var_dict,base_q=13):
    bamfile = pysam.AlignmentFile(bamfile, "rb" )

    variation_info = []
    
    read_vars = collections.defaultdict(dict)

    for pileupcolumn in bamfile.pileup(bamfile.references[0], min_base_quality=base_q):
        pileup_dict = {}
        A_counter, G_counter, C_counter, T_counter, del_counter = 0,0,0,0,0

        genome_position = pileupcolumn.pos+1
        
        for pileupread in pileupcolumn.pileups:
            if genome_position in var_dict:

                read_vars = add_to_cooccurance_analysis(pileupread,read_vars,genome_position)
            if not pileupread.is_del and not pileupread.is_refskip:
                # query position is None if is_del or is_refskip is set.
                counts_list = []
                if pileupread.alignment.query_sequence[pileupread.query_position] == "A":
                    A_counter += 1
                elif pileupread.alignment.query_sequence[pileupread.query_position] == "G":
                    G_counter += 1
                elif pileupread.alignment.query_sequence[pileupread.query_position] == "C":
                    C_counter += 1
                elif pileupread.alignment.query_sequence[pileupread.query_position] == "T":
                    T_counter += 1
            else:
                del_counter += 1
        pileup_dict["Position"] = pileupcolumn.pos + 1
        pileup_dict["A reads"] = A_counter
        pileup_dict["C reads"] = C_counter
        pileup_dict["T reads"] = T_counter
        pileup_dict["G reads"] = G_counter
        pileup_dict["- reads"] = del_counter
        pileup_dict["Percentage"] = non_ref_prcnt_calc(pileupcolumn.pos,pileup_dict,ref_dict)
        pileup_dict["Ref base"] = ref_dict[pileupcolumn.pos]
        variation_info.append(pileup_dict)


    return variation_info,read_vars


def calculate_coocc_json(var_dict,read_vars):

    binary_alts = collections.defaultdict(list)
    binary_refs = collections.defaultdict(list)
    
    
    total_hq_allele = collections.Counter()
    for position in sorted(var_dict):
        
        ref_allele = var_dict[position][0]
        alt_allele = var_dict[position][1]
        
        for read in read_vars:
            if position in read_vars[read]:
                total_hq_allele[position] +=1
                variant = read_vars[read][position]
                if variant == ref_allele:
                    binary_refs[read].append(1)
                    binary_alts[read].append(0)
                elif variant == alt_allele:
                    binary_refs[read].append(0)
                    binary_alts[read].append(1)
#                     print(variant,alt_allele)
                else:
                    #noise/sub_cns var
#                     print(variant,alt_allele,ref_allele)
                    binary_refs[read].append(0)
                    binary_alts[read].append(0)
            
            else:
                binary_refs[read].append(0)
                binary_alts[read].append(0)
    
    header = []
    for i in var_dict:
        header.append(i)

    df_refs = pd.DataFrame.from_dict(binary_refs, orient='index',columns=header)
    coocc_refs= df_refs.T.dot(df_refs)
    long_refs = coocc_refs.stack().reset_index().set_axis('SNP1 SNP2 Ref'.split(), axis=1)

    df_alts = pd.DataFrame.from_dict(binary_alts, orient='index',columns=header)
    coocc_alts= df_alts.T.dot(df_alts)
    long_alts = coocc_alts.stack().reset_index().set_axis('SNP1 SNP2 Alt'.split(), axis=1)
    
    merged = pd.merge(long_alts, long_refs)
    
    merged["Total"] = [total_hq_allele[x] for x in merged["SNP1"]]
    merged["PcentAlt"] = round(100* (merged["Alt"] / merged["Total"]),0)
    merged["PcentRef"] = round(100* (merged["Ref"] / merged["Total"]),0)
    coocurrance =  merged.to_json(orient="records")
    coocurrance_json_string = json.loads(coocurrance)
    
    return coocurrance_json_string