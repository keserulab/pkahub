from django.test import TestCase
from django.core.management import call_command
from pkahub.settings import BASE_DIR
from dataset.models import Dataset
from molecule.models import Molecule, MicroSpecies
from datapoint.models import ExperimentalMacroPka

sourcesconfig_folder_test=BASE_DIR/"build/sourcesconfigs"
datasetsconfig_folder_test=BASE_DIR/"build/datasetconfigs"

# Create your tests here.
class TestBuildCommands(TestCase):
    def test_build_commands(self):
        print("Testing build management commands")
        print("Adding sources")
        call_command("add_sources") #"--testmode"
        print("Adding datasets")
        call_command("add_datasets") #"--testmode"

        print("Datasets in database after adding:")
        datasets=Dataset.objects.all()
        print("Datasets in database after adding:")
        for dataset in datasets:
            print(f"- {dataset.name} (idname: {dataset.idname}, priority: {dataset.priority})")

        #print out sources in database
        #sources=Source.objects.all()
        #print("Sources in database after adding:")
        #for source in sources:
        #    print(f"- {source.name} (type: {source.type} , citation: {source.citation})")
        
        test_tablefile_molecules=BASE_DIR/"build/datafiles/testdata/test_molecules_table.tsv"
        
        print("Adding molecules from table")
        call_command("add_molecules_from_table", str(test_tablefile_molecules))
        #show the first 5 molecules in the database
        molecules=Molecule.objects.all()[:5]
        for molecule in molecules:
            print(f"- smiles: {molecule.smiles}, molid: {molecule.molid}")

        print("Adding experimental pKa values from table")
        macro_pka_data_path=BASE_DIR/"build/datafiles/testdata/test_exp_macro_pka_table.tsv"
        print("Adding IUPAC digitized example")
        call_command("add_exp_macro_datapoints", str(macro_pka_data_path))

        #show the first 5 experimental pKa values in the database
        exp_pka_values=ExperimentalMacroPka.objects.all()[:5]
        for pka in exp_pka_values:
            print(f"- molid: {pka.pre_charge_macrostate.molecule.molid}, pka_value: {pka.pka_value}, dataset: {pka.dataset.name}")
        
        test_tablefile_microspecies=BASE_DIR/"build/datafiles/testdata/test_microspecies_table.tsv"
        print("Adding microspecies from table")
        call_command("add_microspecies_from_table", str(test_tablefile_microspecies))

        #show the first 5 microspecies in the database
        microspecies=MicroSpecies.objects.all()[:5]
        for ms in microspecies:
            print(f"- molid: {ms.charge_macrostate.molecule.molid}, microspecies_id: {ms.microspecies_id}, smiles: {ms.smiles}, ph independent_pop: {ms.ph_independent_pop}")

        print("\nChecking pH-independent population calculation statistics:")
        total_microspecies = MicroSpecies.objects.count()
        microspecies_with_pop = MicroSpecies.objects.filter(ph_independent_pop__isnull=False).count()
        microspecies_with_energy = MicroSpecies.objects.filter(predicted_std_free_energy__isnull=False).count()
        microspecies_missing_energy = MicroSpecies.objects.filter(predicted_std_free_energy__isnull=True).count()

        print(f"Total microspecies: {total_microspecies}")
        print(f"Microspecies with pH-independent populations: {microspecies_with_pop}")
        print(f"Microspecies with predicted free energy: {microspecies_with_energy}")
        print(f"Microspecies missing predicted free energy: {microspecies_missing_energy}")

        # Check a sample molecule to see what's happening
        sample_ms = MicroSpecies.objects.first()
        if sample_ms:
            sample_molid = sample_ms.charge_macrostate.molecule.molid
            sample_charge = sample_ms.charge_macrostate.charge
            print(f"\nSample molecule {sample_molid}, charge state {sample_charge}:")
            same_charge_ms = MicroSpecies.objects.filter(
                charge_macrostate__molecule__molid=sample_molid,
                charge_macrostate__charge=sample_charge
            )
            print(f"Number of microspecies in this charge state: {same_charge_ms.count()}")
            for ms in same_charge_ms:
                print(f"  - microspecies_id: {ms.microspecies_id}, free_energy: {ms.predicted_std_free_energy}, pop: {ms.ph_independent_pop}")

