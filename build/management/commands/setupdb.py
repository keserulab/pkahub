from django.core.management.base import BaseCommand
from pathlib import Path
from django.core.management import call_command

class Command(BaseCommand):
    help=f"""
    Builds the database and sets up pregenerated files.
    WARNING: This will clear the existing database.

    Adding --testmode will use test data for the build process.
    """

    def add_arguments(self, parser):
        parser.add_argument('--testmode', action='store_true', help='Use test data')
    
    def handle(self, *args, **kwargs):
        testmode= kwargs['testmode']

        if testmode:
            call_command('build_all', '--rebuild', '--testmode')
        else:
            call_command('build_all', '--rebuild')
        
        call_command('create_flatfiles')