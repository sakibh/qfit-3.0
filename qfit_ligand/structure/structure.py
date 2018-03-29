from collections import defaultdict

import numpy as np

from .base_structure import _BaseStructure, PDBFile
from .ligand import _Ligand
from .math import Rz, dihedral_angle
from .residue import _Residue, _RotamerResidue, residue_type
from .selector import _Selector


class Structure(_BaseStructure):

    """Class with access to underlying PDB hierarchy."""

    def __init__(self, data, **kwargs):

        for attr in self.REQUIRED_ATTRIBUTES:
            if attr not in data:
                raise ValueError("Not all attributes are given to build the structure")

        super().__init__(data, **kwargs)
        self._chains = []

    @classmethod
    def fromfile(cls, fname):
        if isinstance(fname, PDBFile):
            pdbfile = fname
        else:
            pdbfile = PDBFile.read(fname)
        dd = pdbfile.coor
        data = {}
        for attr, array in dd.items():
            if attr in 'xyz':
                continue
            data[attr] = np.asarray(array)
        coor = np.asarray(list(zip(dd['x'], dd['y'], dd['z'])), dtype=np.float64)
        data['coor'] = coor
        # Add an active array, to check for collisions and density creation.
        data['active'] = np.ones(len(dd['x']), dtype=np.bool)
        return cls(data)

    @classmethod
    def fromstructurelike(cls, structure_like):
        data = {}
        for attr in cls.REQUIRED_ATTRIBUTES:
            data[attr] = getattr(structure_like, attr)
        return cls(data)

    @classmethod
    def empty(cls):

        data = {}
        for attr in self.REQUIRED_ATTRIBUTES:
            data[attr] = []

    def __getitem__(self, key):
        if not self._chains:
            self.build_hierarchy()
        if isinstance(key, int):
            nchains = len(self._chains)
            if key < 0:
                key = key + nchains
            if key >= nchains or key < 0:
                raise IndexError("Selection out of range.")
            else:
                return self._chains[key]
        elif isinstance(key, str):
            for chain in self._chains:
                if key == chain.id:
                    return chain
            raise KeyError
        else:
            raise TypeError

    def __repr__(self):
        if not self._chains:
            self.build_hierarchy()
        return f'Structure: {self.natoms} atoms'

    @property
    def chains(self):
        if not self._chains:
            self.build_hierarchy()
        return self._chains

    @property
    def residue_groups(self):
        for chain in self.chains:
            for rg in chain.residue_groups:
                yield rg

    @property
    def residues(self):
        for chain in self.chains:
            for conformer in chain.conformers:
                for residue in conformer.residues:
                    yield residue

    @property
    def segments(self):
        for chain in self.chains:
            for conformer in chain.conformers:
                for segment in conformer.segments:
                    yield segment

    def build_hierarchy(self):
        # Build up hierarchy starting from chains
        chainids = np.unique(self.chain).tolist()
        self._chains = []
        for chainid in chainids:
            selection = self.select('chain', chainid)
            chain = _Chain(self.data, selection=selection, parent=self, chainid=chainid)
            self._chains.append(chain)

    def combine(self, structure):
        """Combines two structures into one"""
        data = {}
        for attr in self.data:
            hattr = '_' + attr
            array1 = getattr(self, hattr)
            array2 = getattr(structure, hattr)
            combined = np.concatenate((array1, array2))
            data[attr] = combined
        return Structure(data)

    def register(self, attr, array):
        """Register array attribute"""
        if self.parent is not None:
            msg = "This structure has a parent, registering a new array is not allowed."
            raise ValueError(msg)

        self.data[attr] = array
        hattr = '_' + attr
        setattr(self, hattr, array)
        setattr(self.__class__, attr, self._structure_property(hattr))

    def reorder(self):
        ordering = []
        for chain in self.chains:
            for rg in chain.residue_groups:
                for ag in rg.atom_groups:
                    ordering.append(ag._selection)
        ordering = np.concatenate(ordering)
        data = {}
        for attr, value in self.data.items():
            data[attr] = value[ordering]
        return Structure(data)


class _Chain(_BaseStructure):

    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        self.id = kwargs['chainid']
        self._residue_groups = []
        self._conformers = []
        self.conformer_ids = np.unique(self.altloc)

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            if not self._residue_groups:
                self.build_hierarchy()
        nresidues = len(self._residue_groups)
        if isinstance(key, int):
            if key < 0:
                key += nresidues
            if key >= nresidues or key < 0:
                raise IndexError
            else:
                return self._residue_groups[key]
        elif isinstance(key, slice):
            start = key.start
            end = key.end
            if start < 0:
                start += nresidues
            if end < 0:
                end += nresidues
            return self._residue_groups[start: end]
        elif isinstance(key, str):
            if not self._conformers:
                self.build_conformers()
            for conformer in self._conformers:
                if conformer.id == key:
                    return conformer
            raise KeyError
        else:
            raise TypeError

    def __repr__(self):
        return 'Chain: {chainid}'.format(chainid=self.id)

    @property
    def conformers(self):
        if not self._conformers:
            self.build_conformers()
        return self._conformers

    @property
    def residue_groups(self):
        if not self._residue_groups:
            self.build_hierarchy()
        return self._residue_groups

    def build_hierarchy(self):

        resi = self.resi
        order = np.argsort(resi)
        resi = resi[order]
        icode = self.icode[order]
        # A residue group is a collection of entries that have a unique
        # chain, resi, and icode
        # Do all these order tricks to keep the resid ordering correct
        cadd = np.char.add
        residue_group_ids = cadd(cadd(resi.astype(str), '_'), icode)
        residue_group_ids, ind = np.unique(residue_group_ids, return_index=True)
        order = np.argsort(ind)
        residue_group_ids = residue_group_ids[order]
        self._residue_groups = []
        self._residue_group_ids = []
        for residue_group_id in residue_group_ids:
            resi, icode = residue_group_id.split('_')
            resi = int(resi)
            selection = self.select('resi', resi)
            if icode:
                selection &= self.select('icode', icode)
            residue_group = _ResidueGroup(self.data, selection=selection,
                                         parent=self, resi=resi, icode=icode)
            self._residue_groups.append(residue_group)
            self._residue_group_ids.append((resi, icode))

    def build_conformers(self):
        altlocs = np.unique(self.altloc)
        self._conformers = []
        if altlocs.size > 1 or altlocs[0] != "":
            main_selection = self.select('altloc', '')
            for altloc in altlocs:
                if not altloc:
                    continue
                altloc_selection = self.select('altloc', altloc)
                selection = np.union1d(main_selection, altloc_selection)
                conformer = _Conformer(self.data, selection=selection, parent=self, altloc=altloc)
                self._conformers.append(conformer)
        else:
            conformer = _Conformer(self.data, selection=self._selection, parent=self, altloc='')
            self._conformers.append(conformer)


class _ResidueGroup(_BaseStructure):
    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        self.id = (kwargs['resi'], kwargs['icode'])
        self._atom_groups = []

    @property
    def atom_groups(self):
        if not self._atom_groups:
            self.build_hierarchy()
        return self._atom_groups

    def build_hierarchy(self):
        # An atom group is a collection of entries that have a unique
        # chain, resi, icode, resn and altloc
        cadd = np.char.add
        self.atom_group_ids = np.unique(cadd(cadd(self.resn, '_'), self.altloc))
        self._atom_groups = []
        for atom_group_id in self.atom_group_ids:
            resn, altloc = atom_group_id.split('_')
            selection = self.select('resn', resn)
            if altloc:
                altloc_selection = self.select('altloc', altloc)
                selection = np.intersect1d(selection, altloc_selection, assume_unique=True)
            atom_group = _AtomGroup(self.data, selection=selection, parent=self,
                                    resn=resn, altloc=altloc)
            self._atom_groups.append(atom_group)

    def __repr__(self):
        resi, icode = self.id
        string = 'ResidueGroup: resi {}'.format(resi)
        if icode:
            string += ':{}'.format(icode)
        return string


class _AtomGroup(_BaseStructure):
    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        self.id = (kwargs['resn'], kwargs['altloc'])

    def __repr__(self):
        string = 'AtomGroup: {} {}'.format(*self.id)
        return string


class Atom(_BaseStructure):
    pass


class _Conformer(_BaseStructure):

    """Guarantees a single consistent conformer."""

    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        self.id = kwargs['altloc']
        self._residues = []
        self._segments = []

    def __getitem__(self, arg):
        if not self._residues:
            self.build_residues()
        if isinstance(arg, int):
            key = (arg, '')
        elif isinstance(arg, tuple):
            key = arg
        for residue in self._residues:
            if residue.id == key:
                return residue
        raise ValueError("Residue id not found.")

    def __repr__(self):
        return 'Conformer {}'.format(self.id)

    @property
    def ligands(self):
        if not self._residues:
            self.build_residues()
        _ligands = [l for l in self._residues if isinstance(l, _Ligand) and l.natoms > 3]
        return _ligands

    @property
    def residues(self):
        if not self._residues:
            self.build_residues()
        return self._residues

    @property
    def segments(self):
        if not self._segments:
            self.build_segments()
        return self._segments

    def build_residues(self):
        resi = self.resi
        order = np.argsort(resi)
        resi = resi[order]
        icode = self.icode[order]
        # A residue group is a collection of entries that have a unique
        # chain, resi, and icode
        # Do all these order tricks in order to keep the resid ordering correct
        cadd = np.char.add
        residue_ids = cadd(cadd(resi.astype(str), '_'), icode)
        residue_ids, ind = np.unique(residue_ids, return_index=True)
        order = np.argsort(ind)
        residue_ids = residue_ids[order]
        self._residues = []
        for residue_id in residue_ids:
            resi, icode = residue_id.split('_')
            resi = int(resi)
            selection = self.select('resi', resi)
            if icode:
                icode_selection = self.select('icode', icode)
                selection = np.intersect1d(selection, icode_selection, assume_unique=True)
            residue = self.extract(selection)
            rtype = residue_type(residue)
            if rtype == 'rotamer-residue':
                C = _RotamerResidue
            elif rtype == 'aa-residue':
                C = _AminoAcidResidue
            elif rtype == 'residue':
                C = _Residue
            elif rtype == 'ligand':
                C = _Ligand
            else:
                continue
            residue = C(self.data, selection=selection, parent=self,
                        resi=resi, icode=icode, type=rtype)
            self._residues.append(residue)

    def build_segments(self):
        if not self._residues:
            self.build_residues()

        segments = []
        segment = []
        for res in self._residues:
            if not segment:
                segment.append(res)
            else:
                prev = segment[-1]
                if prev.type == res.type:
                    bond_length = 10
                    if res.type in ('rotamer-residue', 'aa-residue'):
                        # Check for nearness
                        sel = prev.select('name', 'C')
                        C = prev._coor[sel]
                        sel = res.select('name', 'N')
                        N = res._coor[sel]
                        bond_length = np.linalg.norm(N - C)
                    elif res.type == 'residue':
                        # Check if RNA / DNA segment
                        O3 = prev.extract("name O3'")
                        P = res.extract('name P')
                        bond_length = np.linalg.norm(O3.coor[0] - P.coor[0])
                    if bond_length < 1.5:
                        segment.append(res)
                    else:
                        segments.append(segment)
                        segment = [res]
                else:
                    segments.append(segment)
                    segment = [res]
        segments.append(segment)

        for segment in segments:
            if len(segment) > 1:
                selections = [residue._selection for residue in segment]
                selection = np.concatenate(selections)
                segment = _Segment(self.data, selection=selection, parent=self, residues=segment)
                self._segments.append(segment)


class _Segment(_BaseStructure):

    """Class that guarantees connected residues and allows backbone rotations."""

    def __init__(self, data, **kwargs):
        super().__init__(data, **kwargs)
        self.residues = kwargs['residues']
        self.length = len(self.residues)

    def __getitem__(self, arg):
        if isinstance(arg, int):
            return self.residues[arg]
        elif isinstance(arg, slice):
            residues = self.residues[arg]
            selections = []
            for residue in residues:
                selections.append(residue._selection)
            selection = np.concatenate(selections)
            return _Segment(self.data, selection=selection, parent=self.parent, residues=residues)
        else:
            raise TypeError

    def __repr__(self):
        return 'Segment: length {}'.format(len(self.residues))

    def find(self, residue_id):
        if isinstance(residue_id, int):
            residue_id = (residue_id, '')
        for n, residue in enumerate(self.residues):
            if residue.id == residue_id:
                return n
        raise ValueError("Residue is not part of segment.")

    def rotate_psi(self, index, angle):
        """Rotate along psi dihedral."""
        selection = [residue._selection for residue in self.residues[index + 1:]]
        residue = self.residues[index]
        selection.append(residue.select('name', ('O', 'OXT')))
        selection = np.concatenate(selection)
        coor = self._coor[selection]
        # Make an orthogonal axis system based on 3 atoms
        CA = residue.extract('name', 'CA').coor[0]
        C = residue.extract('name', 'C').coor[0]
        O = residue.extract('name', 'O').coor[0]
        system_coor = np.vstack((CA, C, O))
        origin = system_coor[0].copy()
        system_coor -= origin
        zaxis = system_coor[1]
        norm = np.linalg.norm
        zaxis /= norm(zaxis)
        yaxis = system_coor[2] - np.inner(system_coor[2], zaxis) * zaxis
        yaxis /= norm(yaxis)
        xaxis = np.cross(yaxis, zaxis)
        backward = np.asmatrix(np.vstack((xaxis, yaxis, zaxis)))
        forward = backward.T
        angle = np.deg2rad(angle)
        coor -= origin
        rotation = Rz(angle)
        R = forward * rotation * backward
        self._coor[selection] = np.dot(coor, R.T) + origin

