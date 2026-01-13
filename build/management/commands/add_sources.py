#add sources by the jsons in the sourceconfigs folder
from django.core.management.base import BaseCommand
from sources.models import Source
from pkahub.settings import BASE_DIR
from build.build_globals import sourcesconfigs_folder
import json
from sources.models import Source
from pathlib import Path

#sourceconfigs_folder=BASE_DIR / 'build' / 'testdata' / 'sourceconfigs'
sourcesconfigs_test_folder=BASE_DIR / 'build' / 'testdata' / 'sourcesconfig_test'
#sourceconfigs_folder=sourcesconfigs_test_folder #now we test

class Command(BaseCommand):
    help = """
    Add all sources to the database defined in sourceconfigs
    configfile needs to have .json extension with a list of source objects
    one source object need to contain
    name: str, 
    type: str,
    citation: str, #authors, title, journal, year, volume, pages

    optional keys:
    doi: str
    url: str, 
    """

    def add_arguments(self, parser):
        parser.add_argument('--overwrite_all', action='store_true', help='Overwrite all existing sources')
        parser.add_argument('--configfolder', type=str, help='config folder path to search for source json files', default=str(sourcesconfigs_folder))
        parser.add_argument('--testmode', action='store_true', help='Use test source config folder')

    def handle(self, *args, **kwargs):
        configfolder=Path(str(kwargs['configfolder']))
        overwrite_all = kwargs['overwrite_all']
        if overwrite_all:
            print("Overwriting")

        if kwargs['testmode']:
            print("Using test mode for source configs")
            configfolder=Path(sourcesconfigs_test_folder)

        if not configfolder.exists():
            errormsg=f"Source config folder {configfolder} does not exist"
            raise FileNotFoundError(errormsg)
        print(f"Using source config folder: {configfolder}")

        for configfile in configfolder.glob('*.json'):
            with open(configfile, 'r') as f:
                source_list=json.load(f)
            for source in source_list:
                name=source['name']
                idname=source['idname']
                type=source['type']
                citation=source['citation']
                doi=source.get('doi', '')
                url=source.get('url', '')
                defaults={'name': name, 'type': type, 'citation': citation, 'doi': doi, 'url': url}
                Source_obj, created=Source.objects.get_or_create(idname=idname, defaults=defaults)
                if not created and overwrite_all:
                    for key, value in defaults.items():
                        setattr(Source_obj, key, value)
                    Source_obj.save()
                    