from django.core.management.base import BaseCommand
from molecule.models import MicroSpecies, Molecule
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Update image_path fields to use the new molimages folder location'

    def handle(self, *args, **options):
        self.stdout.write('Updating image paths...')

        # Get all microspecies
        microspecies_list = MicroSpecies.objects.all()
        total_count = microspecies_list.count()
        updated_count = 0

        for ms in microspecies_list:
            if ms.image_path:
                # Extract just the filename
                filename = os.path.basename(ms.image_path)

                # Build new path
                new_path = str(settings.MOLIMAGE_DIR / filename)

                if ms.image_path != new_path:
                    ms.image_path = new_path
                    ms.save(update_fields=['image_path'])
                    updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Updated {updated_count} out of {total_count} microspecies image paths'
        ))

        # Get all molecules
        molecules_list = Molecule.objects.all()
        total_mol_count = molecules_list.count()
        updated_mol_count = 0

        for mol in molecules_list:
            if mol.image_path:
                # Extract just the filename
                filename = os.path.basename(mol.image_path)

                # Build new path
                new_path = str(settings.MOLIMAGE_DIR / filename)

                if mol.image_path != new_path:
                    mol.image_path = new_path
                    mol.save(update_fields=['image_path'])
                    updated_mol_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Updated {updated_mol_count} out of {total_mol_count} molecule image paths'
        ))