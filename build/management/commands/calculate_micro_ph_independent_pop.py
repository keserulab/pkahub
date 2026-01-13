from django.core.management.base import BaseCommand
from molecule.models import MicroSpecies
import math


def calculate_ph_independent_micro_populations(microspecies_dict):
    """
    input: microspecies_dict - dict of microspecies for a given molecule, key: microspecies_id, value: predicted_std_free_energy (float)
    return: dict of microspecies_id to ph independent population (float between 0 and 1)
    """
    partition_function = 0.0
    for micro_id, std_free_energy in microspecies_dict.items():
        if std_free_energy is not None:
            partition_function += math.exp(-std_free_energy)
    
    ph_independent_populations = {}
    for micro_id, std_free_energy in microspecies_dict.items():
        if std_free_energy is not None and partition_function > 0:
            pop = math.exp(-std_free_energy) / partition_function
            ph_independent_populations[micro_id] = pop
        else:
            ph_independent_populations[micro_id] = None
    
    return ph_independent_populations


class Command(BaseCommand):
    help="""
    Calculate ph independent population for microspecies based on unipka predictions of standard free energy.
    The command will go through all microspecies in the database, group them by parent molecule and charge state,
    and calculate the ph independent population for each microspecies based on the standard free energy values
    of all microspecies within the same charge state.
    The ph independent population is calculated using the Boltzmann distribution.
    """
    
    def add_arguments(self, parser):
        parser.add_argument('--molid', type=str, help='Optional: Calculate only for a specific molecule molid', default=None)

    def handle(self, *args, **kwargs):
        molid = kwargs.get('molid')

        # Get all microspecies, optionally filtered by molid
        if molid:
            microspecies_qs = MicroSpecies.objects.filter(
                charge_macrostate__molecule__molid=molid
            ).select_related('charge_macrostate__molecule')
            self.stdout.write(self.style.SUCCESS(f'Calculating pH-independent populations for molecule {molid}'))
        else:
            microspecies_qs = MicroSpecies.objects.all().select_related('charge_macrostate__molecule')
            self.stdout.write(self.style.SUCCESS('Calculating pH-independent populations for all molecules'))

        # Group microspecies by parent molecule, charge state and keep microspecies objects
        charge_state_microspecies_map = {}  # {(molid, charge): {micro_id: free_energy}}
        microspecies_objects_map = {}  # {(molid, micro_id): microspecies_object}

        for microspecies in microspecies_qs:
            parent_molid = microspecies.charge_macrostate.molecule.molid
            charge = microspecies.charge_macrostate.charge
            key = (parent_molid, charge)

            if key not in charge_state_microspecies_map:
                charge_state_microspecies_map[key] = {}
            charge_state_microspecies_map[key][microspecies.microspecies_id] = microspecies.predicted_std_free_energy
            microspecies_objects_map[(parent_molid, microspecies.microspecies_id)] = microspecies

        # Calculate pH-independent populations for each charge state
        total_charge_states_processed = 0
        total_microspecies_updated = 0
        charge_states_with_missing_energies = []

        for (parent_molid, charge), microspecies_dict in charge_state_microspecies_map.items():
            # Check if all microspecies in this charge state have free energy values
            missing_energy_count = sum(1 for energy in microspecies_dict.values() if energy is None)
            if missing_energy_count > 0:
                charge_states_with_missing_energies.append((parent_molid, charge))
                self.stdout.write(self.style.WARNING(
                    f'Molecule {parent_molid}, charge {charge}: {missing_energy_count}/{len(microspecies_dict)} microspecies missing free energy values, skipping...'
                ))
                continue

            # Calculate pH-independent populations within this charge state
            ph_independent_pops = calculate_ph_independent_micro_populations(microspecies_dict)

            # Update microspecies in database
            microspecies_to_update = []
            for micro_id, pop_value in ph_independent_pops.items():
                if pop_value is not None:
                    microspecies_obj = microspecies_objects_map[(parent_molid, micro_id)]
                    microspecies_obj.ph_independent_pop = pop_value
                    microspecies_to_update.append(microspecies_obj)

            # Bulk update
            if microspecies_to_update:
                MicroSpecies.objects.bulk_update(microspecies_to_update, ['ph_independent_pop'])
                total_microspecies_updated += len(microspecies_to_update)
                total_charge_states_processed += 1

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f'\nProcessed {total_charge_states_processed} charge states'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Updated {total_microspecies_updated} microspecies with pH-independent populations'
        ))

        if charge_states_with_missing_energies:
            self.stdout.write(self.style.WARNING(
                f'\nSkipped {len(charge_states_with_missing_energies)} charge states due to missing free energy values'
            ))

        #debug print
        print("\nChecking if pH-independent populations were calculated:")
        microspecies_with_pop = MicroSpecies.objects.filter(ph_independent_pop__isnull=False)
        print(f"Microspecies with pH-independent populations: {microspecies_with_pop.count()}/{MicroSpecies.objects.count()}")