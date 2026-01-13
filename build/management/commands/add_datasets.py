from django.core.management.base import BaseCommand
from dataset.models import Dataset
from pkahub.settings import BASE_DIR
from build.build_globals import datasetconfigs_folder
import yaml
from pathlib import Path
from sources.models import Source

#datasetconfigs_folder=BASE_DIR / 'build' / 'datasetconfigs'
datasetconfigs_test_folder=BASE_DIR / 'build' / 'testdata' / 'datasetsconfig_test'
#datasetconfigs_folder=datasetconfigs_test_folder #now we test

class Command(BaseCommand):
    help = """
    Add all datasets to the database defined in datasetconfigs
    configfile needs to have .yaml extension
    need to contain 
    name: str, 
    idname: str, 
    priority: int, 
    sourcename: str (the name attribute of the source model), 
    also need another file in the folder with the same stem name as the yaml file 
    which holds the description (max 1000 characters) of the dataset
    """

    def add_arguments(self, parser):
        parser.add_argument('--overwrite_all', action='store_true', help='Overwrite all existing datasets')
        parser.add_argument('--configfolder', type=str, help='Config folder path to look at yaml and description txt files', default=str(datasetconfigs_folder))
        parser.add_argument('--testmode', action='store_true', help='Use test dataset config folder')

    def handle(self, *args, **kwargs):
        configfolder=Path(kwargs['configfolder'])
        overwrite_all = kwargs['overwrite_all']
        if overwrite_all:
            print("Overwriting")
        
        if kwargs['testmode']:
            print("Using test mode for dataset configs")
            configfolder=datasetconfigs_test_folder

        #see if folder exists
        if not configfolder.exists():
            errormsg=f"Dataset config folder {configfolder} does not exist"
            raise FileNotFoundError(errormsg)
        print(f"Using dataset config folder: {configfolder}")
        for configfile in configfolder.glob('*.yaml'):
            print(f"Processing dataset config file: {configfile}")
            config_name = configfile.stem
            with open(configfile, 'r') as f:
                content=yaml.safe_load(f)
            name=content['name']
            idname=content['idname']
            priority=content['priority']
            sourcename=content['sourcename'] #this is the idname of the source
            #try to find license information
            license=content.get('license', None)
            descriptionfile_list=list(configfolder.glob(f'{config_name}*.txt'))
            if len(descriptionfile_list)>0:
                descriptionfile=descriptionfile_list[0]
                with open(descriptionfile, 'r') as f:
                    description=f.read()
            else:
                description="No description provided."
                print(f"Warning: No description file found for dataset {name} ({idname})")
            defaults={'name': name, 'priority': priority, 
                      'source': Source.objects.get(idname=sourcename), 
                      'description': description,
                      'license': license}
            Dataset_obj, created=Dataset.objects.get_or_create(idname=idname, defaults=defaults)
            if not created and overwrite_all:
                for key, value in defaults.items():
                    setattr(Dataset_obj, key, value)
                Dataset_obj.save()