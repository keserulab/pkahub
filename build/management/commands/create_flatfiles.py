from django.core.management.base import BaseCommand
from pathlib import Path
from django.core.management import call_command
from dataset.models import Dataset
from datapoint.models import ExperimentalMacroPka
from molecule.models import Molecule
from tools.translate import (
    expmacropka_qs_to_internaldict,
    internaldict_to_pldf,
    internaldict_to_json_dict,
    internaldict_to_mollist
)
from rdkit import Chem
import json
from pkahub.settings import FLATFILE_DIR
from pkahub.settings import flatfilename_for_all_datasets

class Command(BaseCommand):
    help = "Create flatfiles for all datasets in the database."

    def add_arguments(self, parser):
        parser.add_argument("--formats", nargs="+", type=str, default=["tsv", "json", "smiles", "sdf"],)
    
    def internaldict_to_formats(self, internaldict, output_dir, name, formats):
        # Create TSV file
        if 'tsv' in formats:
            try:
                df = internaldict_to_pldf(internaldict)
                tsv_path = output_dir / f"{name}.tsv"
                df.write_csv(str(tsv_path), separator='\t')
                self.stdout.write(self.style.SUCCESS(f"Created TSV: {tsv_path}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating TSV for {name}: {e}"))
        
        # Create JSON file
        if 'json' in formats:
            try:
                json_data = internaldict_to_json_dict(internaldict)
                json_path = output_dir / f"{name}.json"
                with open(json_path, 'w') as f:
                    json.dump(json_data, f, indent=2)
                self.stdout.write(self.style.SUCCESS(f"Created JSON: {json_path}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating JSON for {name}: {e}"))
        
        # Create SDF file
        if 'sdf' in formats:
            try:
                mol_list = internaldict_to_mollist(internaldict)
                sdf_path = output_dir / f"{name}.sdf"
                writer = Chem.SDWriter(str(sdf_path))
                for mol in mol_list:
                    writer.write(mol)
                writer.close()
                self.stdout.write(self.style.SUCCESS(f"Created SDF: {sdf_path}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating SDF for {name}: {e}"))
    
    def create_smiles_file(self, expmacropka_qs, output_dir, name):
        # Create SMILES file
        try:
            # Get unique molecules from the ExperimentalMacroPka queryset
            molecule_ids = expmacropka_qs.values_list(
                'pre_charge_macrostate__molecule__id', flat=True
            ).distinct()
            molecules = Molecule.objects.filter(id__in=molecule_ids)
            
            smiles_path = output_dir / f"{name}.smi"
            with open(smiles_path, 'w') as f:
                for mol in molecules:
                    f.write(f"{mol.smiles}\t{mol.molid}\n")
            self.stdout.write(self.style.SUCCESS(f"Created SMILES: {smiles_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating SMILES for {name}: {e}"))

    def handle(self, *args, **kwargs):
        formats = kwargs['formats']
        
        # Get all datasets
        datasets = Dataset.objects.all()
        
        # Create output directory if it doesn't exist
        output_dir = FLATFILE_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for dataset in datasets:
            self.stdout.write(f"Processing dataset: {dataset.name} ({dataset.idname})")
            
            # Get all ExperimentalMacroPka entries for this dataset
            expmacropka_qs = ExperimentalMacroPka.objects.filter(dataset=dataset)
            
            if not expmacropka_qs.exists():
                self.stdout.write(self.style.WARNING(f"No data found for dataset {dataset.idname}"))
                continue
            
            # Get internal dict
            internaldict = expmacropka_qs_to_internaldict(expmacropka_qs)
            
            if not internaldict:
                self.stdout.write(self.style.WARNING(f"Empty internal dict for dataset {dataset.idname}"))
                continue
        
            # Create flatfiles in specified formats
            self.internaldict_to_formats(internaldict, output_dir, dataset.idname, formats)
            # Create SMILES file
            self.create_smiles_file(expmacropka_qs, output_dir, dataset.idname)
        
        self.stdout.write(self.style.SUCCESS("Finished processing all datasets"))

        #create flatfiles for all data in database
        self.stdout.write("Creating flatfiles for all experimental macro pKa data in database")
        all_expmacropka_qs = ExperimentalMacroPka.objects.all()
        all_internaldict = expmacropka_qs_to_internaldict(all_expmacropka_qs)
        if all_internaldict:
            self.internaldict_to_formats(all_internaldict, output_dir, flatfilename_for_all_datasets, formats)
            self.create_smiles_file(all_expmacropka_qs, output_dir, flatfilename_for_all_datasets)
            self.stdout.write(self.style.SUCCESS("Created flatfiles for all datasets"))