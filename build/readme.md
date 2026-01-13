# Data files for build
## Source data building
done with the add_sources command
source data is built from the sourcesconfig folder: build/sourcesconfigs by default
it needs a json file with this structure:
[
    #list of json objects for sources
    { 
    "name": str, #identifier of source in database
    "type": "article" or "weblink",
    "citation": str,
    "doi": str,
    "url": str
    }
]

## Dataset data building
done with the add_datasets command
dataset data is built from datasetconfigs folder: build/datasetconfigs by default
to define a dataset you need to put a .yaml file and a .txt file into this folder
the .yaml and .txt file must start with the same name (e.g. novartis.yaml and novartis_description.txt)
the .yaml file holds the metadata for the dataset:
name: str #the name that gets displayed
idname: str #identifier of dataset in database
priority: int #priority of experimental data in case of duplicates
sourcename: the name attribute of the source which is the primary citation of this dataset
license: str #license of the dataset (optional)

the .txt file holds the description of the dataset

## Molecule data building
done with the add_molecules_from_table command
preferably a .tsv (tab separated values) file
must have "smiles" and "molid" columns
molid is used as a unique identifier for molecules in the database
the molecule will get processed according to the smiles

## Microspecies data building
done with add_microspecies_from_table command
preferably a .tsv (tab separated values) file
needs to have a "smiles" and "molid" column
microspecies information is derived from smiles
microspecies is assigned to molecule model based on molid, currently there is no quality check for this
charge macrostate models also get created here based on created microspecies

## Exp Macro pKa datapoint data building
done with add_exp_macro_datapoints
Exp Macro pKa datapoint and the corresponding data model describes one experimental macro pka measurement value (if a molecule has multiple experimental pka values they are assigned to their own data point model)
preferably a .tsv (tab separated values) file
must have the following columns:
"rawdataID": unique identifier for this datapoint
"dataset": idname attribute of the dataset (Dataset model) the datapoint belongs to
"molid": the molid attribute of the Molecule model which the datapoint gets assigned to
"Exp_Macro_pKa_processed": the (experimental macro) pKa value for this datapoint, float type
"T_processed": temperature assigned to this datapoint, float type, can be empty
"I_processed": ionic strength of solution assigned to this datapoint, float type, can be empty
"assigned_charge_state_transition": str type, must be in format: n+1>>n where n is an integer, this descripes a macroscopic deprotonation reaction
"assignment_method": type str, method used for assigning charge state transition to this datapoint (almost always epikx)
"assignment_error": float type, a numeric value which describes the uncertainty of the charge state assignment (e.g. absolute difference between predicted and experimental value)
"primary_source": name attribute of a source model which is assigned to this datapoint, can be empty, in this case we treat the primary source as the source assigned to the dataset

# Commands for building
call the build_all command to automatically build the database from the files described above found in their specified folder
for source and dataset data it is the default config folder
for molecules its: build/datafiles/molecules_table
for microspecies its: build/datafiles/microspecies_table
for (exp macro) datapoints its: build/datafiles/exp_macro_pka_datapoints

there can be multiple files in these folders, they must be .tsv files

by calling it with the --rebuild flag, the existing database gets flushed