
import numpy as np
import argparse
import logging
import os
import sys
import time
from string import ascii_uppercase
from . import Structure
from .structure import residue_type
from .structure.rotamers import ROTAMERS

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("structure", type=str,
                   help="PDB-file containing structure.")
    p.add_argument("lig_name", type=str, help="Ligand Name")
    args = p.parse_args()
    return args

def main():
    args = parse_args()
    structure = Structure.fromfile(args.structure)
    structure_resi = structure.extract('resn', args.lig_name) 
    chain = np.unique(structure_resi.chain)
    resi = np.unique(structure_resi.resi)
    chain2 = ' '.join(map(str, chain))
    resi2 = ' '.join(map(str, resi))

    with open(args.lig_name + '_chain_resi.txt', 'w') as file:
           file.write(chain2 + ',' + resi2)
