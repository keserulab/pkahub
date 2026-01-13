"""
Translation utilities for converting Django querysets to internal data structures.
"""

from datapoint.models import ExperimentalMacroPka
from molecule.models import MicroSpecies
from pathlib import PureWindowsPath
from django.db.models import Prefetch
import os
import polars as pl
from rdkit import Chem


def molecule_qs_to_internaldict(molecules, pop_cutoff=0.05):
    """
    Convert a Molecule queryset to an internal dictionary structure.

    Args:
        molecules: Django queryset of Molecule objects

    Returns:
        dict: Dictionary with molid as keys and molecule data as values:
        {
            molid (str): {
                "smiles": str,
                "microspecies": {
                    microspecies_id: {
                        "charge": int,
                        "smiles": str,
                        "std_free_energy": float,
                        "relative_population": float
                    }
                },
                "macro_pka_values": [
                    {
                        "pka_value": float,
                        "charge_state_pre": int,
                        "charge_state_post": int,
                        "data_source": str
                    }
                ]
            }
        }
    """
    # Optimize the queryset with prefetch_related to reduce queries
    # Filter microspecies by ph_independent_pop > pop_cutoff
    molecules = molecules.prefetch_related(
        Prefetch(
            'chargemacrostate_set__microspecies_set',
            queryset=MicroSpecies.objects.filter(ph_independent_pop__gt=pop_cutoff)
        )
    )

    # Build the dictionary
    result = {}
    for mol in molecules:
        # Collect all charge macrostates for this molecule
        charge_macrostates = list(mol.chargemacrostate_set.all())

        # Collect all pKa values for this molecule
        macro_pka_values = []
        seen_pkas = set()  # To avoid duplicates

        for cms in charge_macrostates:
            # Get pKa values where this charge state is the pre state
            # Query all experimental macro pKa values for transitions starting from this charge state
            pka_datapoints = ExperimentalMacroPka.objects.filter(
                pre_charge_macrostate=cms
            ).select_related('dataset__source', 'pre_charge_macrostate', 'post_charge_macrostate')

            for pka in pka_datapoints:
                key = (pka.pka_value, pka.pre_charge_macrostate.charge, pka.post_charge_macrostate.charge)
                if key not in seen_pkas:
                    seen_pkas.add(key)
                    macro_pka_values.append({
                        'pka_value': pka.pka_value,
                        'charge_state_pre': pka.pre_charge_macrostate.charge,
                        'charge_state_post': pka.post_charge_macrostate.charge,
                        'data_source': pka.dataset.name if pka.dataset else '' #pka.dataset.source.name if pka.dataset and pka.dataset.source else ''
                    })

        # Collect microspecies data
        microspecies_dict = {}
        for cms in mol.chargemacrostate_set.all():
            for ms in cms.microspecies_set.all():
                microspecies_dict[ms.microspecies_id] = {
                    'charge': cms.charge,
                    'smiles': ms.smiles,
                    'std_free_energy': ms.predicted_std_free_energy,
                    'relative_population': ms.ph_independent_pop,
                }

        # Build the final entry for this molecule
        result[mol.molid] = {
            'smiles': mol.smiles,
            'microspecies': microspecies_dict,
            'macro_pka_values': macro_pka_values
        }

    return result

def expmacropka_qs_to_internaldict(expmacropka_qs):
    """
    Convert an ExperimentalMacroPka queryset to an internal dictionary structure.

    Args:
        expmacropka_qs: Django queryset of ExperimentalMacroPka objects

    Returns:
        dict: Dictionary with molid as keys and molecule data as values:
        {
            molid (str): {
                "smiles": str,
                "microspecies": {
                    microspecies_id: {
                        "charge": int,
                        "smiles": str,
                        "std_free_energy": float,
                        "relative_population": float
                    }
                },
                "macro_pka_values": [
                    {
                        "pka_value": float,
                        "charge_state_pre": int,
                        "charge_state_post": int,
                        "data_source": str
                    }
                ]
            }
        }

    Note: Unlike molecule_qs_to_internaldict, this function only includes
          macro_pka_values that are present in the input queryset.
    """
    # Optimize the queryset with select_related and prefetch_related
    expmacropka_qs = expmacropka_qs.select_related(
        'pre_charge_macrostate__molecule',
        'post_charge_macrostate',
        'dataset__source'
    )

    # Build a dictionary to collect data by molecule
    molecules_data = {}

    # Process each ExperimentalMacroPka entry
    for pka in expmacropka_qs:
        # Get the molecule (via pre_charge_macrostate)
        molecule = pka.pre_charge_macrostate.molecule
        molid = molecule.molid

        # Initialize molecule entry if not exists
        if molid not in molecules_data:
            molecules_data[molid] = {
                'molecule': molecule,
                'macro_pka_values': [],
                'seen_pkas': set()
            }

        # Add pKa value if not duplicate
        key = (pka.pka_value, pka.pre_charge_macrostate.charge, pka.post_charge_macrostate.charge)
        if key not in molecules_data[molid]['seen_pkas']:
            molecules_data[molid]['seen_pkas'].add(key)
            molecules_data[molid]['macro_pka_values'].append({
                'pka_value': pka.pka_value,
                'charge_state_pre': pka.pre_charge_macrostate.charge,
                'charge_state_post': pka.post_charge_macrostate.charge,
                'data_source': pka.dataset.name if pka.dataset else '' #pka.dataset.source.name if pka.dataset and pka.dataset.source else ''
            })

    # Now build the final result dictionary with microspecies
    result = {}
    for molid, mol_info in molecules_data.items():
        molecule = mol_info['molecule']

        # Collect microspecies data for this molecule
        microspecies_dict = {}
        charge_macrostates = molecule.chargemacrostate_set.prefetch_related('microspecies_set').all()

        for cms in charge_macrostates:
            for ms in cms.microspecies_set.all():
                microspecies_dict[ms.microspecies_id] = {
                    'charge': cms.charge,
                    'smiles': ms.smiles,
                    'std_free_energy': ms.predicted_std_free_energy,
                    'relative_population': ms.ph_independent_pop,
                }

        # Build the final entry for this molecule
        result[molid] = {
            'smiles': molecule.smiles,
            'microspecies': microspecies_dict,
            'macro_pka_values': mol_info['macro_pka_values']
        }

    return result

def internaldict_to_molvis_input(internaldict):
    """
    Convert internal dictionary format to MolVis input format.

    Args:
        internaldict: Dictionary with molid as keys and molecule data as values
                     (output from molecule_qs_to_internaldict)

    Returns:
        dict: Dictionary optimized for MolVis JavaScript component:
        {
            "molid": str,
            "smiles": str,
            "charge_states": [
                {
                    "charge": int,
                    "charge_label": str,  # e.g., "+2", "-1", "0"
                    "microspecies": [
                        {
                            "id": str,
                            "smiles": str,
                            "image_path": str,
                            "relative_population": float or None,
                            "relative_population_percent": str  # e.g., "45.2%" or "NaN"
                        }
                    ]
                }
            ],
            "transitions": [
                {
                    "charge_pre": int,
                    "charge_post": int,
                    "pka_values": [
                        {
                            "pka_value": float,
                            "data_source": str
                        }
                    ],
                    "mean": float or None,
                    "std": float or None,
                    "has_data": bool,
                    "label": str  # e.g., "9.45 ± 0.12 (n=3)" or "No experimental data"
                }
            ]
        }

    Note: This function expects a single molecule in the internaldict.
          If multiple molecules are present, only the first one will be processed.
          image_path is only the image's filename for easier handling in the frontend.
          images are stored in the static/molimages folder
    """
    if not internaldict:
        return None

    # Get the first (and ideally only) molecule from the internaldict
    molid = next(iter(internaldict))
    mol_data = internaldict[molid]

    # Query the db for microspecies images paths
    microspecies_qs = MicroSpecies.objects.filter(
        charge_macrostate__molecule__molid=molid
    )
    # Extract just the filename from the path (handles both Windows and Unix paths)
    ms_image_paths = {}
    for ms in microspecies_qs:
        if ms.image_path:
            # Try Windows path first, then fall back to Unix path
            try:
                filename = PureWindowsPath(ms.image_path).name
            except:
                filename = os.path.basename(ms.image_path)
        else:
            filename = ''
        ms_image_paths[ms.microspecies_id] = filename

    # Group microspecies by charge state
    microspecies_by_charge = {}
    for ms_id, ms_data in mol_data['microspecies'].items():
        charge = ms_data['charge']
        if charge not in microspecies_by_charge:
            microspecies_by_charge[charge] = []

        # Format relative population as percentage
        rel_pop = ms_data['relative_population']
        if rel_pop is not None:
            rel_pop_percent = f"{rel_pop * 100:.1f}%"
        else:
            rel_pop_percent = "NaN"

        microspecies_by_charge[charge].append({
            'id': str(ms_id),
            'smiles': ms_data['smiles'],
            'image_path': ms_image_paths.get(ms_id, ''),
            'relative_population': rel_pop,
            'relative_population_percent': rel_pop_percent
        })

    # Build charge_states list sorted by charge (descending)
    charge_states = []
    for charge in sorted(microspecies_by_charge.keys(), reverse=True):
        # Format charge label
        if charge == 0:
            charge_label = "0"
        elif charge > 0:
            charge_label = f"+{charge}"
        else:
            charge_label = str(charge)

        charge_states.append({
            'charge': charge,
            'charge_label': charge_label,
            'microspecies': microspecies_by_charge[charge]
        })

    # Build transitions list for consecutive charge states
    transitions = []
    pka_by_transition = {}

    # Group pKa values by transition
    for pka_data in mol_data['macro_pka_values']:
        charge_pre = pka_data['charge_state_pre']
        charge_post = pka_data['charge_state_post']
        key = (charge_pre, charge_post)

        if key not in pka_by_transition:
            pka_by_transition[key] = []

        pka_by_transition[key].append({
            'pka_value': pka_data['pka_value'],
            'data_source': pka_data['data_source']
        })

    # Create transitions for consecutive charge states
    for i in range(len(charge_states) - 1):
        charge_pre = charge_states[i]['charge']
        charge_post = charge_states[i + 1]['charge']
        key = (charge_pre, charge_post)

        pka_values = pka_by_transition.get(key, [])
        has_data = len(pka_values) > 0

        # Calculate mean and std if we have data
        mean = None
        std = None
        label = "No experimental data"

        if has_data:
            pka_vals = [pka['pka_value'] for pka in pka_values]
            mean = sum(pka_vals) / len(pka_vals)

            if len(pka_vals) > 1:
                variance = sum((x - mean) ** 2 for x in pka_vals) / len(pka_vals)
                std = variance ** 0.5
                label = f"{mean:.2f} ± {std:.2f} (n={len(pka_vals)})"
            else:
                label = f"{mean:.2f} (n=1)"

        transitions.append({
            'charge_pre': charge_pre,
            'charge_post': charge_post,
            'pka_values': pka_values,
            'mean': mean,
            'std': std,
            'has_data': has_data,
            'label': label
        })

    return {
        'molid': molid,
        'smiles': mol_data['smiles'],
        'charge_states': charge_states,
        'transitions': transitions
    }

def internaldict_to_json_dict(internaldict):
    """
    Convert internal dictionary format to JSON-serializable list format.

    Args:
        internaldict: Dictionary with molid as keys and molecule data as values
                     (output from molecule_qs_to_internaldict)

    Returns:
        list: List of molecule dictionaries in JSON-serializable format:
        [
            {
                "molid": str,
                "smiles": str,
                "microspecies": [
                    {
                        "id": str,
                        "charge": int,
                        "smiles": str,
                        "std_free_energy": float,
                        "relative_population": float
                    }
                ],
                "macro_pka_values": [
                    {
                        "pka_value": float,
                        "charge_state_pre": int,
                        "charge_state_post": int,
                        "data_source": str
                    }
                ]
            }
        ]
    """
    json_list = []

    for molid, mol_data in internaldict.items():
        # Convert microspecies dictionary to list format
        microspecies_list = []
        for ms_id, ms_data in mol_data['microspecies'].items():
            microspecies_list.append({
                'id': str(ms_id),
                'charge': ms_data['charge'],
                'smiles': ms_data['smiles'],
                'std_free_energy': ms_data['std_free_energy'],
                'relative_population': ms_data['relative_population'],
            })

        # Build the JSON entry for this molecule
        json_list.append({
            'molid': molid,
            'smiles': mol_data['smiles'],
            'microspecies': microspecies_list,
            'macro_pka_values': mol_data['macro_pka_values']
        })

    return json_list


def internaldict_to_pldf(internaldict):
    """
    Convert internal dictionary format to Polars DataFrame.

    Args:
        internaldict: Dictionary with molid as keys and molecule data as values
                     (output from molecule_qs_to_internaldict)

    Returns:
        polars.DataFrame: DataFrame with columns:
            - pka_value (float)
            - data_source (str)
            - charge_state_pre (int)
            - charge_state_post (int)
            - microspecies_pre (str): comma-separated SMILES
            - microspecies_post (str): comma-separated SMILES
            - molid (str)
            - smiles (str)

    Raises:
        ImportError: If polars is not installed
    """

    # Initialize lists for each column
    pka_values = []
    data_sources = []
    charge_states_pre = []
    charge_states_post = []
    microspecies_pre_list = []
    microspecies_post_list = []
    molids = []
    smiles_list = []

    for molid, mol_data in internaldict.items():
        # Group microspecies by charge state for quick lookup
        microspecies_by_charge = {}
        for ms_id, ms_data in mol_data['microspecies'].items():
            charge = ms_data['charge']
            if charge not in microspecies_by_charge:
                microspecies_by_charge[charge] = []
            microspecies_by_charge[charge].append(ms_data['smiles'])

        # Create a row for each pKa value
        for pka_data in mol_data['macro_pka_values']:
            pka_values.append(pka_data['pka_value'])
            data_sources.append(pka_data['data_source'])
            charge_states_pre.append(pka_data['charge_state_pre'])
            charge_states_post.append(pka_data['charge_state_post'])

            # Get microspecies SMILES for pre charge state
            pre_smiles = microspecies_by_charge.get(pka_data['charge_state_pre'], [])
            microspecies_pre_list.append(','.join(pre_smiles))

            # Get microspecies SMILES for post charge state
            post_smiles = microspecies_by_charge.get(pka_data['charge_state_post'], [])
            microspecies_post_list.append(','.join(post_smiles))

            molids.append(molid)
            smiles_list.append(mol_data['smiles'])

    # Create Polars DataFrame with explicit schema
    df = pl.DataFrame({
        'pka_value': pl.Series(pka_values, dtype=pl.Float64),
        'data_source': pl.Series(data_sources, dtype=pl.Utf8),
        'charge_state_pre': pl.Series(charge_states_pre, dtype=pl.Int64),
        'charge_state_post': pl.Series(charge_states_post, dtype=pl.Int64),
        'microspecies_pre': pl.Series(microspecies_pre_list, dtype=pl.Utf8),
        'microspecies_post': pl.Series(microspecies_post_list, dtype=pl.Utf8),
        'molid': pl.Series(molids, dtype=pl.Utf8),
        'smiles': pl.Series(smiles_list, dtype=pl.Utf8)
    })

    return df


def internaldict_to_mollist(internaldict):
    """
    Convert internal dictionary format to list of RDKit mol objects.

    Args:
        internaldict: Dictionary with molid as keys and molecule data as values
                     (output from molecule_qs_to_internaldict)

    Returns:
        list: List of RDKit mol objects with properties:
            - _Name: molid
            - molid: molid
            - pka_value: comma-separated list of pKa values
            - charge_state_pre: comma-separated list of pre charge states
            - charge_state_post: comma-separated list of post charge states
            - data_source: comma-separated list of data sources

    Note: All comma-separated property values correspond to entries in the same
          macro_pka_values list from the internaldict.
    """
    mol_list = []

    for molid, mol_data in internaldict.items():
        # Create RDKit mol object from SMILES
        mol = Chem.MolFromSmiles(mol_data['smiles'])

        if mol is None:
            # Skip invalid SMILES
            continue

        # Set the _Name property
        mol.SetProp('_Name', molid)

        # Set the molid property
        mol.SetProp('molid', molid)

        # Extract and format macro_pka_values as comma-separated strings
        pka_values = []
        charge_states_pre = []
        charge_states_post = []
        data_sources = []

        for pka_data in mol_data['macro_pka_values']:
            pka_values.append(str(pka_data['pka_value']))
            charge_states_pre.append(str(pka_data['charge_state_pre']))
            charge_states_post.append(str(pka_data['charge_state_post']))
            data_sources.append(pka_data['data_source'])

        # Set properties as comma-separated strings
        mol.SetProp('pka_value', ','.join(pka_values))
        mol.SetProp('charge_state_pre', ','.join(charge_states_pre))
        mol.SetProp('charge_state_post', ','.join(charge_states_post))
        mol.SetProp('data_source', ','.join(data_sources))

        mol_list.append(mol)

    return mol_list


def chargemacrostate_qs_to_micromollist(chargemacrostate_qs):
    """
    Convert a ChargeMacroState queryset to list of RDKit mol objects for microspecies.

    Args:
        chargemacrostate_qs: Django queryset of ChargeMacroState objects

    Returns:
        list: List of RDKit mol objects (one per microspecies) with properties:
            - _Name: "{molid}-{microspecies_id}"
            - molid: molid of parent molecule
            - std_free_energy: predicted_std_free_energy of microspecies (as string)
            - relative_population: ph_independent_pop of microspecies (as string)
    """
    # Optimize the queryset with select_related and prefetch_related
    chargemacrostate_qs = chargemacrostate_qs.select_related('molecule').prefetch_related('microspecies_set')

    mol_list = []

    for cms in chargemacrostate_qs:
        molid = cms.molecule.molid

        for ms in cms.microspecies_set.all():
            # Create RDKit mol object from microspecies SMILES
            mol = Chem.MolFromSmiles(ms.smiles)

            if mol is None:
                # Skip invalid SMILES
                continue

            # Set the _Name property as "{molid}-{microspecies_id}"
            mol.SetProp('_Name', f"{molid}-{ms.microspecies_id}")

            # Set the molid property
            mol.SetProp('molid', molid)

            # Set std_free_energy property (convert to string)
            if ms.predicted_std_free_energy is not None:
                mol.SetProp('std_free_energy', str(ms.predicted_std_free_energy))
            else:
                mol.SetProp('std_free_energy', '')

            # Set relative_population property (convert to string)
            if ms.ph_independent_pop is not None:
                mol.SetProp('relative_population', str(ms.ph_independent_pop))
            else:
                mol.SetProp('relative_population', '')

            mol_list.append(mol)

    return mol_list
