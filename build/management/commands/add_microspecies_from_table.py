from django.core.management.base import BaseCommand
from molecule.models import Molecule, ChargeMacroState, MicroSpecies
import polars as pl
from rdkit import Chem

from pathlib import Path
from tools.makemolimage import save_molecule_image
from pkahub.settings import MOLIMAGE_DIR
from django.core.management import call_command

"""
microspecies for reference

class MicroSpecies(models.Model):
    microspecies_id=models.CharField(max_length=10) #this is unique within a molecule
    #molecule=models.ForeignKey(Molecule, on_delete=models.CASCADE)
    smiles=models.CharField(max_length=500)
    #smiles_explicit_hydrogens=models.CharField(max_length=500)
    smiles_atom_numbered=models.CharField(max_length=500)
    total_charge=models.IntegerField()
    charge_macrostate=models.ForeignKey(ChargeMacroState, on_delete=models.CASCADE)
    image_path=models.CharField(max_length=200, null=True, blank=True)
    predicted_std_free_energy=models.FloatField(null=True, blank=True) #in kcal/mol
    ph_independent_pop=models.FloatField(null=True, blank=True) #between 0 and 1
"""

#take into consideration to add an --addallmicrospecies flag in future to add all microspecies even for charge state not present in the database

class Command(BaseCommand):
    help="""Add molecules from a table file containing SMILES strings.
    The Table file requires the following columns:
    'smiles' (str format) - SMILES string of the microspecies
    'molid' (str format) - molid of the parent molecule, must already exist in the database

    optional columns:
    'predicted_std_free_energy' (float format) - predicted standard free energy in kcal/mol

    The command will only add microspecies for existing ChargeMacroState entries in the database.
    If a microspecies has a charge state that doesn't exist in the database, it will be skipped.
    The command will skip adding microspecies that already exist in the database based on canonical SMILES, unless the --overwrite flag is used.

    ph_independent_pop will not be set by this command and should be calculated separately based on std_free_energy values of all microspecies for a given molecule.
    """
    
    def add_arguments(self, parser):
        parser.add_argument('tablefile', type=str, help='Path to the table file containing molecules in SMILES format')
        parser.add_argument('--separator', type=str, help='separator used in the table file, default=\t (tab)', default='\t')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite all existing microspecies with same molid already in database')
        parser.add_argument('--dont_calc_pop', action='store_true', help='Dont calculate ph independent population after adding microspecies (caluculated by default)')
    
    def handle(self, *args, **kwargs):
        tablefile=kwargs['tablefile']
        separator=kwargs['separator']
        overwrite=kwargs['overwrite']
        dontcalcpop=kwargs['dont_calc_pop']
        if overwrite:
            print("Overwriting existing microspecies with same molid in database")
        if separator.lower()=='tab':
            separator='\t'
        df=pl.read_csv(tablefile, separator=separator)
        smiles_list=df['smiles'].to_list()
        molid_list=df['molid'].to_list()

        # Check if predicted_std_free_energy column exists
        has_free_energy = 'predicted_std_free_energy' in df.columns
        free_energy_list = df['predicted_std_free_energy'].to_list() if has_free_energy else [None] * len(smiles_list)

        #get all existing molecules for molids in the list (bulk fetch)
        existing_molids = set(Molecule.objects.filter(molid__in=molid_list).values_list('molid', flat=True))

        #get existing charge states for molids in the list (bulk fetch with select_related)
        existing_charge_states = ChargeMacroState.objects.filter(
            molecule__molid__in=molid_list
        ).select_related('molecule')

        #get existing microspecies for molids in the list (bulk fetch with select_related)
        existing_microspecies = MicroSpecies.objects.filter(
            charge_macrostate__molecule__molid__in=molid_list
        ).select_related('charge_macrostate__molecule')

        #handle overwrite
        existing_smiles_set = set()
        if overwrite:
            #delete existing microspecies for molids in the list (keep charge states)
            existing_microspecies.delete()
            #make empty query set
            existing_microspecies=MicroSpecies.objects.none()
        else:
            #get existing smiles list of microstates
            existing_smiles_set = set(existing_microspecies.values_list('smiles', flat=True))

        #make dictionary which maps molid:charge to ChargeMacroState object (single iteration)
        charge_macrostate_dict={}
        for cms in existing_charge_states:
            molid = cms.molecule.molid
            if molid not in charge_macrostate_dict:
                charge_macrostate_dict[molid] = {}
            charge_macrostate_dict[molid][cms.charge] = cms

        #make dictionary which maps molid:charge state to list of existing microspecies smiles (single iteration)
        microspecies_dict={}
        for mp in existing_microspecies:
            molid=mp.charge_macrostate.molecule.molid
            charge=mp.charge_macrostate.charge
            if molid not in microspecies_dict:
                microspecies_dict[molid]={}
            if charge not in microspecies_dict[molid]:
                microspecies_dict[molid][charge]=set()
            microspecies_dict[molid][charge].add(mp.smiles)

        microspecies_to_create = []

        num_processed=0
        for smiles, molid, free_energy in zip(smiles_list, molid_list, free_energy_list):
            #need to have existing molid
            if molid not in existing_molids:
                self.stdout.write(self.style.ERROR(f'Molecule with molid {molid} not found in database, skipping...'))
                continue
            mol=Chem.MolFromSmiles(smiles)
            if mol is None:
                self.stdout.write(self.style.ERROR(f'Could not parse SMILES: {smiles}, skipping...'))
                continue
            smiles_canonical=Chem.MolToSmiles(mol, isomericSmiles=True)
            total_charge=Chem.GetFormalCharge(mol)

            #check if this microspecies already exists
            if not overwrite:
                if smiles_canonical in existing_smiles_set:
                    continue

            #get numbered smiles
            for atom in mol.GetAtoms():
                atom.SetAtomMapNum(atom.GetIdx()+1)
            smiles_numbered=Chem.MolToSmiles(mol, isomericSmiles=True)
            #reset atom map numbers
            for atom in mol.GetAtoms():
                atom.SetAtomMapNum(0)

            #get charge macrostate from molecule - only add if it exists
            charge_macrostate_obj = charge_macrostate_dict.get(molid, {}).get(total_charge, None)
            if charge_macrostate_obj is None:
                self.stdout.write(self.style.WARNING(f'ChargeMacroState with charge {total_charge} for molecule {molid} not found in database, skipping microspecies...'))
                continue

            #get microspecies id
            #count the number of existing microspecies for this charge state
            existing_count=microspecies_dict.get(molid, {}).get(total_charge, set())
            microspecies_id=f'{total_charge}_{len(existing_count)+1}'

            #save molecule image
            image_path = MOLIMAGE_DIR/f"{molid}_{microspecies_id}.png"
            save_molecule_image(mol, image_path)

            # Parse free energy if present
            predicted_free_energy = None
            if free_energy is not None and str(free_energy).strip():
                try:
                    predicted_free_energy = float(free_energy)
                except (ValueError, TypeError):
                    self.stdout.write(self.style.WARNING(f'Could not parse predicted_std_free_energy value: {free_energy}, setting to None'))

            #create microspecies object
            microspecies_obj=MicroSpecies(
                microspecies_id=microspecies_id,
                smiles=smiles_canonical,
                smiles_atom_numbered=smiles_numbered,
                total_charge=total_charge,
                image_path=str(image_path),
                charge_macrostate=charge_macrostate_obj,
                predicted_std_free_energy=predicted_free_energy
            )
            microspecies_to_create.append(microspecies_obj)
            #add to microspecies dict
            if molid not in microspecies_dict:
                microspecies_dict[molid]={}
            if total_charge not in microspecies_dict[molid]:
                microspecies_dict[molid][total_charge]=set()
            microspecies_dict[molid][total_charge].add(smiles_canonical)
            num_processed+=1
            if num_processed % 100 == 0:
                self.stdout.write(self.style.SUCCESS(f'Processed {num_processed} microspecies...'))

        #bulk create microspecies
        if microspecies_to_create:
            MicroSpecies.objects.bulk_create(microspecies_to_create)
            self.stdout.write(self.style.SUCCESS(f'Added {len(microspecies_to_create)} microspecies to the database'))
        else:
            self.stdout.write(self.style.WARNING('No microspecies were added to the database'))
        
        if not dontcalcpop:
            #call calculate_micro_ph_independent_pop command to calculate ph independent populations
            self.stdout.write(self.style.SUCCESS('Calculating pH-independent populations for added microspecies...'))
            call_command('calculate_micro_ph_independent_pop')