from django.shortcuts import render
from dataset.models import Dataset
from datapoint.models import ExperimentalMacroPka, ExperimentalMicroPka
from molecule.models import Molecule, MicroSpecies, ChargeMacroState

# Create your views here.
def index(request):
    return render(request, 'index.html')

def calculate(request):
    return render(request, 'index.html')

def datasets(request):
    from pkahub.settings import flatfilename_for_all_datasets

    datasets = Dataset.objects.all()

    ##### Calculate datapoint counts for each dataset
    expMacro = ExperimentalMacroPka.objects.all()
    expMicro = ExperimentalMicroPka.objects.all()
    expMicroCounts = [expMicro.filter(dataset=ds).count() for ds in datasets]
    expMacroCounts = [expMacro.filter(dataset=ds).count() for ds in datasets]
    # Add expMicroCounts and expMacroCounts to datasets
    datapoint_counts = []
    for i in range(len(datasets)):
        total_count = expMicroCounts[i] + expMacroCounts[i]
        datapoint_counts.append(total_count)

    ##### Calculate molecule counts for each dataset
    # Traverse through expMicro and expMacro datapoints through MicroSpecies and ChargeMacroState to Molecule, and count unique molecules per dataset
    molecule_counts = []
    for ds in datasets:
        micro_species = MicroSpecies.objects.filter(pre_microspecies__dataset=ds).select_related('charge_macrostate__molecule')
        macro_states = ChargeMacroState.objects.filter(pre_charge_macrostate__dataset=ds).select_related('molecule')
        molecules_from_micro = set(ms.charge_macrostate.molecule for ms in micro_species)
        molecules_from_macro = set(ms.molecule for ms in macro_states)
        unique_molecules = molecules_from_micro.union(molecules_from_macro)
        molecule_counts.append(len(unique_molecules))

    return render(request, 'datasets.html', {
        'datasets': zip(datasets, datapoint_counts, molecule_counts),
        'all_datasets_basename': flatfilename_for_all_datasets
    })

def about(request):
    return render(request, 'about.html')

def documentation(request):
    return render(request, 'documentation.html')