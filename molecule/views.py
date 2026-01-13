from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from molecule.models import Molecule, MicroSpecies, ChargeMacroState
from datapoint.models import ExperimentalMacroPka, ExperimentalMicroPka, CalculatedMacroPka, CalculatedMicroPka
from sources.models import Source
from tools.translate import (
    molecule_qs_to_internaldict,
    internaldict_to_json_dict,
    internaldict_to_pldf,
    internaldict_to_molvis_input,
    internaldict_to_mollist,
    chargemacrostate_qs_to_micromollist,
)

import itertools
import json
from django.db.models import Count, Q

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit.Chem import rdFingerprintGenerator
    from rdkit import DataStructs
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

# Create your views here.
def index(request, dataset_id=None):
    """Molecule browse view with search functionality"""
    mols_in_page = 20

    # Get search parameters from GET request
    min_mw = request.GET.get('min_mw', '')
    max_mw = request.GET.get('max_mw', '')
    min_hac = request.GET.get('min_hac', '')
    max_hac = request.GET.get('max_hac', '')
    min_charge_states = request.GET.get('min_charge_states', '')
    max_charge_states = request.GET.get('max_charge_states', '')
    min_microspecies = request.GET.get('min_microspecies', '')
    max_microspecies = request.GET.get('max_microspecies', '')

    # Get SMILES search parameters
    smiles = request.GET.get('smiles', '')
    search_type = request.GET.get('search_type', 'exact')
    similarity = request.GET.get('similarity', '1.0')

    # Try to validate similarity value
    try:
        similarity_value = float(similarity)
        if similarity_value < 0.0 or similarity_value > 1.0:
            similarity = '1.0'
            similarity_value = 1.0
    except (ValueError, TypeError):
        similarity = '1.0'
        similarity_value = 1.0

    # Handle SMILES search
    smiles_error = False
    query_inchi = None
    if smiles and RDKIT_AVAILABLE:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                query_inchi = Chem.MolToInchi(mol)

                if not query_inchi:
                    smiles_error = True
            else:
                smiles_error = True
        except Exception:
            smiles_error = True

    # Start with all molecules
    molecules = Molecule.objects.all()

    if dataset_id:
        # Filter datapoint objects for dataset
        exp_macro_datapoints = ExperimentalMacroPka.objects.filter(dataset__id=dataset_id)
        exp_micro_datapoints = ExperimentalMicroPka.objects.filter(dataset__id=dataset_id)
        # Get molecule IDs from datapoints
        molecule_ids = set()
        for dp in exp_macro_datapoints:
            molecule_ids.add(dp.pre_charge_macrostate.molecule.id)
            molecule_ids.add(dp.post_charge_macrostate.molecule.id)
        for dp in exp_micro_datapoints:
            molecule_ids.add(dp.pre_microspecies.charge_macrostate.molecule.id)
            molecule_ids.add(dp.post_microspecies.charge_macrostate.molecule.id)
        # Filter molecules by these IDs
        molecules = molecules.filter(id__in=molecule_ids)
    

    # Apply SMILES exact search filter (InChI-based)
    if smiles and query_inchi and search_type == 'exact' and not smiles_error:
        molecules = molecules.filter(inchi=query_inchi)

    # Apply molecular weight filters
    if min_mw:
        molecules = molecules.filter(molecular_properties__molecular_weight__gte=float(min_mw))
    if max_mw:
        molecules = molecules.filter(molecular_properties__molecular_weight__lte=float(max_mw))

    # Apply heavy atom count filters
    if min_hac:
        molecules = molecules.filter(molecular_properties__heavy_atom_count__gte=int(min_hac))
    if max_hac:
        molecules = molecules.filter(molecular_properties__heavy_atom_count__lte=int(max_hac))
    
    # Add annotations for counting charge states and microspecies with experimental data
    molecules = molecules.annotate(
        num_charge_states=Count(
            'chargemacrostate',
            #filter=Q(chargemacrostate__pre_macro_pka__isnull=False) | Q(chargemacrostate__post_macro_pka__isnull=False),
            distinct=True
        ),
        num_microspecies=Count(
            'chargemacrostate__microspecies',
            filter=Q(chargemacrostate__microspecies__ph_independent_pop__gt=0.05),
            distinct=True
        )
    )

    #Filter molecules based on charge states and microspecies counts
    if min_charge_states:
        molecules = molecules.filter(num_charge_states__gte=int(min_charge_states))
    if max_charge_states:
        molecules = molecules.filter(num_charge_states__lte=int(max_charge_states))
    if min_microspecies:
        molecules = molecules.filter(num_microspecies__gte=int(min_microspecies))
    if max_microspecies:
        molecules = molecules.filter(num_microspecies__lte=int(max_microspecies))
    
    # Apply SMILES substructure search filter
    if smiles and search_type == 'substructure' and not smiles_error and RDKIT_AVAILABLE:
        substructure_mols = []
        query_mol = Chem.MolFromSmiles(smiles)
        if query_mol:
            for mol in molecules:
                target_mol = Chem.MolFromSmiles(mol.smiles)
                if target_mol and target_mol.HasSubstructMatch(query_mol):
                    substructure_mols.append(mol.id)
            molecules = molecules.filter(id__in=substructure_mols)

    # Apply SMILES similarity search filter
    if smiles and search_type == 'similarity' and not smiles_error and RDKIT_AVAILABLE:
        # Get fingerprint generator (Morgan)
        morgan_radius=4
        morgan_fp_size=2048
        fpgen = rdFingerprintGenerator.GetMorganGenerator(radius=morgan_radius, fpSize=morgan_fp_size)
        similar_mols = []
        query_mol = Chem.MolFromSmiles(smiles)
        if query_mol:
            query_fp=fpgen.GetFingerprint(query_mol)
            for mol in molecules:
                target_mol = Chem.MolFromSmiles(mol.smiles)
                if target_mol:
                    target_fp = fpgen.GetFingerprint(target_mol)
                    sim = DataStructs.TanimotoSimilarity(query_fp, target_fp)
                    if sim >= similarity_value:
                        similar_mols.append(mol.id)
            molecules = molecules.filter(id__in=similar_mols)

    # Get total count before pagination
    total_matching_molecules = molecules.count()

    # Paginate results
    paginator = Paginator(molecules, mols_in_page)
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    # Build molecule data from paginated results
    molecule_data = []
    for mol in page_obj:
        # Get molecular properties
        mw = None
        hac = None
        if hasattr(mol, 'molecular_properties') and mol.molecular_properties:
            mw = mol.molecular_properties.molecular_weight
            hac = mol.molecular_properties.heavy_atom_count

        molecule_data.append({
            'molecule': mol,
            'num_charge_states': mol.num_charge_states,
            'num_microspecies': mol.num_microspecies,
            'molecular_weight': mw,
            'heavy_atom_count': hac
        })

    # Build active filters list for display
    active_filters = []

    # Add SMILES search filter if applicable (and no error)
    if smiles and not smiles_error:
        if search_type == 'exact':
            active_filters.append(f"Exact search: {smiles}")
        elif search_type == 'substructure':
            active_filters.append(f"Substructure search: {smiles}")
        elif search_type == 'similarity':
            active_filters.append(f"Similarity search: {smiles}, minimal similarity: {similarity}")

    if min_mw:
        active_filters.append(f"Molecular Weight ≥ {min_mw}")
    if max_mw:
        active_filters.append(f"Molecular Weight ≤ {max_mw}")
    if min_hac:
        active_filters.append(f"Heavy Atom Count ≥ {min_hac}")
    if max_hac:
        active_filters.append(f"Heavy Atom Count ≤ {max_hac}")
    if min_charge_states:
        active_filters.append(f"Charge States ≥ {min_charge_states}")
    if max_charge_states:
        active_filters.append(f"Charge States ≤ {max_charge_states}")
    if min_microspecies:
        active_filters.append(f"Microspecies ≥ {min_microspecies}")
    if max_microspecies:
        active_filters.append(f"Microspecies ≤ {max_microspecies}")

    return render(request, 'molecule_browse.html', {
        'molecule_data': molecule_data,
        'page_obj': page_obj,
        'total_matching_molecules': total_matching_molecules,
        'min_mw': min_mw,
        'max_mw': max_mw,
        'min_hac': min_hac,
        'max_hac': max_hac,
        'min_charge_states': min_charge_states,
        'max_charge_states': max_charge_states,
        'min_microspecies': min_microspecies,
        'max_microspecies': max_microspecies,
        'active_filters': active_filters,
        'smiles': smiles,
        'search_type': search_type,
        'similarity': similarity,
        'smiles_error': smiles_error,
    })


def download(request):
    """Download molecule data in TSV or JSON format based on current filters"""

    # Get the download format
    download_format = request.GET.get('format', 'tsv')

    # Get search parameters from GET request (same as index view)
    min_mw = request.GET.get('min_mw', '')
    max_mw = request.GET.get('max_mw', '')
    min_hac = request.GET.get('min_hac', '')
    max_hac = request.GET.get('max_hac', '')
    min_charge_states = request.GET.get('min_charge_states', '')
    max_charge_states = request.GET.get('max_charge_states', '')
    min_microspecies = request.GET.get('min_microspecies', '')
    max_microspecies = request.GET.get('max_microspecies', '')

    # Get SMILES search parameters
    smiles = request.GET.get('smiles', '')
    search_type = request.GET.get('search_type', 'exact')
    similarity = request.GET.get('similarity', '1.0')

    # Try to validate similarity value
    try:
        similarity_value = float(similarity)
        if similarity_value < 0.0 or similarity_value > 1.0:
            similarity_value = 1.0
    except (ValueError, TypeError):
        similarity_value = 1.0

    # Handle SMILES search
    smiles_error = False
    query_inchi = None
    if smiles and RDKIT_AVAILABLE:
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                query_inchi = Chem.MolToInchi(mol)
                if not query_inchi:
                    smiles_error = True
            else:
                smiles_error = True
        except Exception:
            smiles_error = True

    # Start with all molecules
    molecules = Molecule.objects.all()

    # Apply SMILES exact search filter (InChI-based)
    if smiles and query_inchi and search_type == 'exact' and not smiles_error:
        molecules = molecules.filter(inchi=query_inchi)

    # Apply molecular weight filters
    if min_mw:
        molecules = molecules.filter(molecular_properties__molecular_weight__gte=float(min_mw))
    if max_mw:
        molecules = molecules.filter(molecular_properties__molecular_weight__lte=float(max_mw))

    # Apply heavy atom count filters
    if min_hac:
        molecules = molecules.filter(molecular_properties__heavy_atom_count__gte=int(min_hac))
    if max_hac:
        molecules = molecules.filter(molecular_properties__heavy_atom_count__lte=int(max_hac))

    # Add annotations for counting charge states and microspecies
    molecules = molecules.annotate(
        num_charge_states=Count(
            'chargemacrostate',
            distinct=True
        ),
        num_microspecies=Count(
            'chargemacrostate__microspecies',
            distinct=True
        )
    )

    # Filter molecules based on charge states and microspecies counts
    if min_charge_states:
        molecules = molecules.filter(num_charge_states__gte=int(min_charge_states))
    if max_charge_states:
        molecules = molecules.filter(num_charge_states__lte=int(max_charge_states))
    if min_microspecies:
        molecules = molecules.filter(num_microspecies__gte=int(min_microspecies))
    if max_microspecies:
        molecules = molecules.filter(num_microspecies__lte=int(max_microspecies))

    # Apply SMILES substructure search filter
    if smiles and search_type == 'substructure' and not smiles_error and RDKIT_AVAILABLE:
        substructure_mols = []
        query_mol = Chem.MolFromSmiles(smiles)
        if query_mol:
            for mol in molecules:
                target_mol = Chem.MolFromSmiles(mol.smiles)
                if target_mol and target_mol.HasSubstructMatch(query_mol):
                    substructure_mols.append(mol.id)
            molecules = molecules.filter(id__in=substructure_mols)

    # Apply SMILES similarity search filter
    if smiles and search_type == 'similarity' and not smiles_error and RDKIT_AVAILABLE:
        morgan_radius = 4
        morgan_fp_size = 2048
        fpgen = rdFingerprintGenerator.GetMorganGenerator(radius=morgan_radius, fpSize=morgan_fp_size)
        similar_mols = []
        query_mol = Chem.MolFromSmiles(smiles)
        if query_mol:
            query_fp = fpgen.GetFingerprint(query_mol)
            for mol in molecules:
                target_mol = Chem.MolFromSmiles(mol.smiles)
                if target_mol:
                    target_fp = fpgen.GetFingerprint(target_mol)
                    sim = DataStructs.TanimotoSimilarity(query_fp, target_fp)
                    if sim >= similarity_value:
                        similar_mols.append(mol.id)
            molecules = molecules.filter(id__in=similar_mols)

    # Convert to internal dictionary
    internaldict = molecule_qs_to_internaldict(molecules)

    if download_format == 'json':
        # Convert to JSON format
        json_data = internaldict_to_json_dict(internaldict)

        # Create JSON response
        response = HttpResponse(
            json.dumps(json_data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="molecules.json"'
        return response

    else:  # TSV format
        # Convert to Polars DataFrame
        df = internaldict_to_pldf(internaldict)

        # Convert to TSV string
        tsv_content = df.write_csv(separator='\t')

        # Create TSV response
        response = HttpResponse(tsv_content, content_type='text/tab-separated-values')
        response['Content-Disposition'] = 'attachment; filename="molecules.tsv"'
        return response


def download_single_molecule(request, molid):
    """Download data for a single molecule in TSV, JSON, SMILES, SDF, MICROSMILES, or MICROSDF format"""

    # Get the download format
    download_format = request.GET.get('format', 'tsv')

    # Get the molecule queryset (just one molecule)
    molecules = Molecule.objects.filter(molid=molid)

    # Convert to internal dictionary
    internaldict = molecule_qs_to_internaldict(molecules)

    if download_format == 'json':
        # Convert to JSON format
        json_data = internaldict_to_json_dict(internaldict)

        # Create JSON response
        response = HttpResponse(
            json.dumps(json_data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{molid}.json"'
        return response

    elif download_format == 'smiles':
        # Get the molecule object
        molecule = molecules.first()
        if not molecule:
            return HttpResponse("Molecule not found", status=404)

        # Create SMILES content (SMILES followed by 4 spaces and molid)
        smiles_content = f"{molecule.smiles}    {molid}\n"

        # Create SMILES response
        response = HttpResponse(smiles_content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{molid}.smi"'
        return response

    elif download_format == 'sdf':
        # Convert to mol list using RDKit
        mol_list = internaldict_to_mollist(internaldict)

        if not mol_list:
            return HttpResponse("Could not generate SDF for this molecule", status=500)

        # Write to SDF string with properties
        if RDKIT_AVAILABLE:
            from io import StringIO
            sdf_buffer = StringIO()
            writer = Chem.SDWriter(sdf_buffer)

            for mol in mol_list:
                writer.write(mol)

            writer.close()
            sdf_content = sdf_buffer.getvalue()

            # Create SDF response
            response = HttpResponse(sdf_content, content_type='chemical/x-mdl-sdfile')
            response['Content-Disposition'] = f'attachment; filename="{molid}.sdf"'
            return response
        else:
            return HttpResponse("RDKit is not available", status=500)

    elif download_format == 'microsmiles':
        # Get the molecule object
        molecule = molecules.first()
        if not molecule:
            return HttpResponse("Molecule not found", status=404)

        # Get all charge macrostates for this molecule
        charge_macrostates = ChargeMacroState.objects.filter(molecule=molecule).prefetch_related('microspecies_set')

        # Create microspecies SMILES content
        microsmiles_lines = []
        for cms in charge_macrostates:
            for ms in cms.microspecies_set.all():
                # Format: smiles    molid    microspecies_id
                line = f"{ms.smiles}    {molid}    {ms.microspecies_id}\n"
                microsmiles_lines.append(line)

        microsmiles_content = ''.join(microsmiles_lines)

        # Create SMILES response
        response = HttpResponse(microsmiles_content, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{molid}_microspecies.smi"'
        return response

    elif download_format == 'microsdf':
        # Get the molecule object
        molecule = molecules.first()
        if not molecule:
            return HttpResponse("Molecule not found", status=404)

        # Get all charge macrostates for this molecule
        charge_macrostates = ChargeMacroState.objects.filter(molecule=molecule)

        # Convert to microspecies mol list using chargemacrostate_qs_to_micromollist
        micro_mol_list = chargemacrostate_qs_to_micromollist(charge_macrostates)

        if not micro_mol_list:
            return HttpResponse("Could not generate microspecies SDF for this molecule", status=500)

        # Write to SDF string with properties
        if RDKIT_AVAILABLE:
            from io import StringIO
            sdf_buffer = StringIO()
            writer = Chem.SDWriter(sdf_buffer)

            for mol in micro_mol_list:
                writer.write(mol)

            writer.close()
            sdf_content = sdf_buffer.getvalue()

            # Create SDF response
            response = HttpResponse(sdf_content, content_type='chemical/x-mdl-sdfile')
            response['Content-Disposition'] = f'attachment; filename="{molid}_microspecies.sdf"'
            return response
        else:
            return HttpResponse("RDKit is not available", status=500)

    else:  # TSV format
        # Convert to Polars DataFrame
        df = internaldict_to_pldf(internaldict)

        # Convert to TSV string
        tsv_content = df.write_csv(separator='\t')

        # Create TSV response
        response = HttpResponse(tsv_content, content_type='text/tab-separated-values')
        response['Content-Disposition'] = f'attachment; filename="{molid}.tsv"'
        return response


def molecule(request, molid):

    molecule = Molecule.objects.get(molid=molid)

    # Build a single JSON payload for the client-side microspecies renderer.
    internaldict = molecule_qs_to_internaldict(Molecule.objects.filter(molid=molid))
    molvis_input = internaldict_to_molvis_input(internaldict)

    # Serialize to JSON for JavaScript
    molvis_input_json = json.dumps(molvis_input)

    # Collect all pKa datapoints for this molecule (for the table)
    all_pka_datapoints = ExperimentalMacroPka.objects.filter(
        pre_charge_macrostate__molecule=molecule
    ).select_related('dataset', 'pre_charge_macrostate', 'post_charge_macrostate').order_by('pka_value')

    return render(request, 'molecule.html', {
        'molecule': molecule,
        'pka_datapoints': all_pka_datapoints,
        'molvis_input_json': molvis_input_json,
    })


def dummymolview(request, molid):
    """A dummy molecule view for testing MolVis component."""
    try:
        molecule = Molecule.objects.get(molid=molid)
    except Molecule.DoesNotExist:
        raise Http404("Molecule does not exist.")

    # Build MolVis input data
    internaldict = molecule_qs_to_internaldict(Molecule.objects.filter(molid=molid))
    molvis_input = internaldict_to_molvis_input(internaldict)

    # Debug output
    print(f"\n=== DummyMolView Debug for {molid} ===")
    print(f"Internal dict keys: {list(internaldict.keys()) if internaldict else 'None'}")
    print(f"MolVis input is None: {molvis_input is None}")
    if molvis_input:
        print(f"MolVis input has charge_states: {molvis_input.get('charge_states') is not None}")
        if molvis_input.get('charge_states'):
            print(f"Number of charge states: {len(molvis_input['charge_states'])}")

    # Serialize to JSON for JavaScript
    molvis_input_json = json.dumps(molvis_input)

    return render(request, 'dummymolview.html', {
        'molecule': molecule,
        'molvis_input_json': molvis_input_json,
    })

