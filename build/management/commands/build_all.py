from django.core.management.base import BaseCommand
from pathlib import Path
from django.core.management import call_command
from build.build_globals import molecules_table_folder, microstates_table_folder, exp_macro_pka_datapoints_folder, sourcesconfigs_folder, datasetconfigs_folder
from pkahub.settings import BASE_DIR

class Command(BaseCommand):
    help=f"""
    Build all necessary database entries including sources, datasets, molecules, microspecies, and experimental pKa values.
    This command sequentially calls other management commands to populate the database.
    By calling --rebuild option, the existing database will be cleared before rebuilding.
    Usage:
        python manage.py build_all [--rebuild]
    
    Data used for building is expected to be found in the following directories:
    sourcesconfigs: {sourcesconfigs_folder}
    datasetconfigs: {datasetconfigs_folder}
    molecules tsv file: {molecules_table_folder}
    microstates tsv file: {microstates_table_folder}
    exp macro pka datapoints: {exp_macro_pka_datapoints_folder}

    for required file structures see build/readme.md
    """

    def add_arguments(self, parser):
        parser.add_argument('--rebuild', action='store_true', help='Clear existing database entries before rebuilding')
        parser.add_argument('--testmode', action='store_true', help='Use test data')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing entries in the database during the build process')
    
    def handle(self, *args, **kwargs):
        rebuild = kwargs['rebuild']
        testmode = kwargs['testmode']
        overwrite = kwargs['overwrite']
        if rebuild:
            print("Rebuilding database: clearing existing entries")
            #clear existing entries
            call_command('flush')
        #if kwargs['testmode']:
        #    print("Using test mode for sources and datasets")
        
        print("Adding sources to database")
        call_command('add_sources')
        
        print("Adding datasets to database")
        call_command('add_datasets')
        
        print("Adding molecules from table to database")
        molecules_tablefiles = Path(molecules_table_folder).glob('*.tsv')
        if testmode:
            print("Using test mode for molecules table")
            molecules_tablefiles = [BASE_DIR/'build/datafiles/testdata/test_molecules_table.tsv']
        for molecules_tablefile in molecules_tablefiles:
            call_command('add_molecules_from_table', str(molecules_tablefile))
        
        print("Adding experimental macro pKa datapoints to database")
        exp_macro_pka_files = Path(exp_macro_pka_datapoints_folder).glob('*.tsv')
        if testmode:
            print("Using test mode for experimental macro pKa datapoints")
            exp_macro_pka_files = [BASE_DIR/'build/datafiles/testdata/test_exp_macro_pka_table.tsv']
        for filepath in exp_macro_pka_files:
            print(f"Adding data from {filepath}")
            call_command('add_exp_macro_datapoints', str(filepath))

        print("Adding microspecies from table to database")
        microstates_tablefiles = Path(microstates_table_folder).glob('*.tsv')
        if testmode:
            print("Using test mode for microspecies table")
            microstates_tablefiles = [BASE_DIR/'build/datafiles/testdata/test_microspecies_table.tsv']
        for ms_tablefile in microstates_tablefiles:
            call_command('add_microspecies_from_table', str(ms_tablefile))
        
        print("Database build process completed.")
