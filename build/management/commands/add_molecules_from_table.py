from django.core.management.base import BaseCommand
from molecule.models import Molecule, MolecularProperties, StereoParentMolecule
import polars as pl
from rdkit import Chem
from rdkit.Chem import Descriptors, inchi
from rdkit.Chem.MolStandardize.rdMolStandardize import StereoParent

class Command(BaseCommand):
    help="""
    Add molecules from a table file containing SMILES strings. 
    The Table file requires one column named 'smiles' (str format) and one column named 'molid' (str format) which should be a unique identifier for each molecule."""
    
    def add_arguments(self, parser):
        parser.add_argument('tablefile', type=str, help='Path to the table file containing molecules in SMILES format')
        parser.add_argument('--separator', type=str, help='separator used in the table file, default=\t (tab)', default='\t')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite all existing molecules with same molid already in database')
    
    def handle(self, *args, **kwargs):
        tablefile=kwargs['tablefile']
        separator=kwargs['separator']
        overwrite=kwargs['overwrite']
        if overwrite:
            print("Overwriting existing molecules with same molid in database")
        if separator.lower()=='tab':
            separator='\t'
        df=pl.read_csv(tablefile, separator=separator)
        smiles_list=df['smiles'].to_list()
        molid_list=df['molid'].to_list()
        
        # Get existing molids from database
        existing_molids = set(Molecule.objects.filter(molid__in=molid_list).values_list('molid', flat=True))

        #make set for stereo parent inchi
        stereo_parent_inchi_to_smiles={}
        molid_to_stereo_parent_inchi={}
        
        # Prepare lists for new molecules and properties
        molecules_to_create = []
        molecules_to_update = []
        properties_to_create = []

        if overwrite:
            # Delete existing molecules and their properties
            Molecule.objects.filter(molid__in=molid_list).delete()
            existing_molids = set()
        
        # Process each molecule
        for molid, smiles in zip(molid_list, smiles_list):
            # Check if molecule already exists
            if molid in existing_molids:
                if not overwrite:
                    continue

            # Parse SMILES with RDKit
            try:
                mol = Chem.MolFromSmiles(smiles)
            except:
                mol = None
            if mol is None:
                self.stdout.write(self.style.WARNING(f'Could not parse SMILES for molid {molid}: {smiles}'))
                continue
            
            # Generate InChI and InChIKey
            try:
                mol_inchi = inchi.MolToInchi(mol)
                mol_inchikey = inchi.InchiToInchiKey(mol_inchi)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not generate InChI for molid {molid}: {e}'))
                continue
            
            # Generate atom-numbered SMILES
            for atom in mol.GetAtoms():
                atom.SetAtomMapNum(atom.GetIdx() + 1)
            smiles_atom_numbered = Chem.MolToSmiles(mol)
            
            # Reset atom map numbers
            for atom in mol.GetAtoms():
                atom.SetAtomMapNum(0)
            
            # Calculate molecular properties
            mol_weight = Descriptors.MolWt(mol)
            heavy_atom_count = mol.GetNumHeavyAtoms()
            num_hbond_donors = Descriptors.NumHDonors(mol)
            num_hbond_acceptors = Descriptors.NumHAcceptors(mol)
            
            # Add to create list
            molecule_obj = Molecule(
                molid=molid,
                smiles=smiles,
                smiles_atom_numbered=smiles_atom_numbered,
                inchi=mol_inchi,
                inchikey=mol_inchikey,
                name=""
            )
            molecules_to_create.append(molecule_obj)
            # Prepare molecular properties
            properties_obj = MolecularProperties(
                molecular_weight=mol_weight,
                heavy_atom_count=heavy_atom_count,
                num_hbond_donors=num_hbond_donors,
                num_hbond_acceptors=num_hbond_acceptors
            )
            properties_to_create.append(properties_obj)

            #get stereo parent inchi
            sp = StereoParent(mol)
            stereo_parent_inchi = inchi.MolToInchi(sp)
            molid_to_stereo_parent_inchi[molid] = stereo_parent_inchi

            #in case of duplicate molids
            existing_molids.add(molid)
        
        #link stereo parents
        #find existing stereo parents
        existing_stereo_parents = StereoParentMolecule.objects.filter(inchi__in=stereo_parent_inchi_to_smiles.keys())
        stereo_parent_inchi_to_sp_obj={spm.inchi: spm for spm in existing_stereo_parents}
        
        stereo_parents_to_create=[]
        for stereo_parent_inchi, stereo_parent_smiles in stereo_parent_inchi_to_smiles.items():
            if stereo_parent_inchi in stereo_parent_inchi_to_sp_obj:
                continue
            spm = StereoParentMolecule(name='', smiles=stereo_parent_smiles, inchi=stereo_parent_inchi, inchikey=inchi.InchiToInchiKey(stereo_parent_inchi))
            stereo_parents_to_create.append(spm)
        if len(stereo_parents_to_create)>0:
            created_stereo_parents = StereoParentMolecule.objects.bulk_create(stereo_parents_to_create)
            for spm in created_stereo_parents:
                stereo_parent_inchi_to_sp_obj[spm.inchi] = spm
        ######
        
        # Batch create molecules
        if len(molecules_to_create)>0:
            for molecule in molecules_to_create:
                stereo_parent_inchi = molid_to_stereo_parent_inchi.get(molecule.molid, None)
                if stereo_parent_inchi:
                    spm = stereo_parent_inchi_to_sp_obj.get(stereo_parent_inchi, None)
                    if spm:
                        molecule.stereo_parent = spm
            created_molecules = Molecule.objects.bulk_create(molecules_to_create)
            self.stdout.write(self.style.SUCCESS(f'Created {len(created_molecules)} molecules'))
            
            # Batch create molecular properties
            if len(properties_to_create)>0:
                MolecularProperties.objects.bulk_create(properties_to_create)
                self.stdout.write(self.style.SUCCESS(f'Created {len(properties_to_create)} molecular property records'))
        else:
            self.stdout.write(self.style.WARNING('No molecules to create'))