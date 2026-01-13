import pickle
import polars as pl
from pathlib import Path

"""
take raw data files (tsv with all molecules, tsv with all processed experimental macro pka data, unipka microspecies pickle files)
and make them into formats which are acceptible by the command scripts to add them to the database
note: experimental macro pka data should be already compatible with the command script add_exp_macro_datapoints.py
"""

def merge_unique_molecules(output_path, tablefiles=[], check_unique=False):
    """
    Merges tablefiles with unique molecules into a single tablefile
    tablefiles must have "smiles"/"reprSMILES_processed" and "molid" columns
    """
    merged_smiles_rows=[]
    merged_molid_rows=[]

    for tablefile in tablefiles:
        df=pl.read_csv(tablefile, separator='\t')
        try:
            smiles_list=df['smiles'].to_list()
        except:
            smiles_list=df['reprSMILES_processed'].to_list()
        molid_list=df['molid'].to_list()
        for smiles, molid in zip(smiles_list, molid_list):
            if check_unique:
                if smiles in merged_smiles_rows or molid in merged_molid_rows:
                    print(f"Duplicate molecule found, skipping: smiles={smiles}, molid={molid}")
                    continue
            merged_smiles_rows.append(smiles)
            merged_molid_rows.append(molid)

    merged_df = pl.DataFrame({
        "smiles": merged_smiles_rows,
        "molid": merged_molid_rows
    })
    
    merged_df.write_csv(output_path, separator='\t')
    print(f"Merged {len(tablefiles)} tablefiles into {output_path} with {len(merged_smiles_rows)} unique molecules.")

def examine_needed_charge_states(combined_exp_macro_pka_input_file):
    """
    returns a dict of molid: set of needed charge states (int) based on the experimental macro pka data
    the combined_exp_macro_pka_input_file should be the tsv file used as input for add_exp_macro_datapoints.py
    examines the "assigned_charge_state_transition" column
    """
    combined_exp_macro_pka_input_file=Path(str(combined_exp_macro_pka_input_file))
    df=pl.read_csv(combined_exp_macro_pka_input_file, separator='\t')
    molid_list=df['molid'].to_list()
    charge_state_transition_list=df['assigned_charge_state_transition'].to_list()
    exclude_flag_list=df['exclude_flag'].to_list()

    molid_to_needed_charge_states={}

    for molid, charge_state_transition, exclude_flag in zip(molid_list, charge_state_transition_list, exclude_flag_list):
        if exclude_flag is not None:
            if exclude_flag.lower()=='exclude':
                continue
        if charge_state_transition is None or charge_state_transition.strip()=='':
            print(f"Warning: missing assigned_charge_state_transition for molid {molid}, skipping...")
            continue
        try:
            pre_charge, post_charge = (int(charge_state_transition.split('>>')[0]), int(charge_state_transition.split('>>')[1]))
        except:
            print(f"Warning: could not parse assigned_charge_state_transition '{charge_state_transition}' for molid {molid}, skipping...")
            continue
        if molid not in molid_to_needed_charge_states:
            molid_to_needed_charge_states[molid] = set()
        molid_to_needed_charge_states[molid].add(pre_charge)
        molid_to_needed_charge_states[molid].add(post_charge)
    
    #check conecutiveness of charge states and update them if needed
    for molid, charge_states in molid_to_needed_charge_states.items():
        min_charge = min(charge_states)
        max_charge = max(charge_states)
        complete_charge_states = set(range(min_charge, max_charge + 1))
        if charge_states != complete_charge_states:
            print(f"Warning: non-consecutive charge states for molid {molid}, updating to complete range {complete_charge_states}")
            molid_to_needed_charge_states[molid] = complete_charge_states

    return molid_to_needed_charge_states

def calculate_relative_population(microspecies_dict):
    """
    placeholder for future function to calculate relative populations of microspecies
    microspecies_dict: {charge_state: {microspecies_id: (microspecies_smiles, std_free_energy)}}
    returns: microspecies_id: relative_population
    """
    pass

#this should be updated in the future to handle duplicates better
def merge_unipka_microspecies_picklefiles(output_path, combined_exp_macro_pka_input_file, 
                                          picklefiles_high_priority: list, picklefiles_low_priority: list):
    """
    Merges unipka microspecies pickle files and saves them to a single output tsv file compatible with add_microspecies_from_table.py
    only keeps microspecies for charge states needed based on the experimental macro pka data
    Microspecies from Higher priority files will be added first for a given charge state, and lower priority files will only be used to fill in states where higher priority files do not have data
    saves table file to output_path with columns: molid, smiles, predicted_std_free_energy
    """
    molid_to_needed_charge_states = examine_needed_charge_states(combined_exp_macro_pka_input_file) #path is handled here

    high_priority_data={}
    for picklefile in picklefiles_high_priority:
        picklefile=Path(str(picklefile))
        with open(picklefile, 'rb') as f:
            data = pickle.load(f)
        for molid, ensemble in data.items():
            if molid not in high_priority_data:
                high_priority_data[molid] = {}
            for charge_state, macrostate in ensemble.items():
                if charge_state not in high_priority_data[molid]:
                    high_priority_data[molid][charge_state] = []
                for microtuple in macrostate: #(smiles, std_free_energy)
                    high_priority_data[molid][charge_state].append(microtuple) #ADD ALL MICROSTATES FOUND, LATER UPDATE THIS CODE TO FILTER DUPLICATES
    
    low_priority_data={}
    for picklefile in picklefiles_low_priority:
        picklefile=Path(str(picklefile))
        with open(picklefile, 'rb') as f:
            data = pickle.load(f)
        for molid, ensemble in data.items():
            if molid not in low_priority_data:
                low_priority_data[molid] = {}
            for charge_state, macrostate in ensemble.items():
                if charge_state not in low_priority_data[molid]:
                    low_priority_data[molid][charge_state] = []
                for microtuple in macrostate: #(smiles, std_free_energy)
                    low_priority_data[molid][charge_state].append(microtuple) #ADD ALL MICROSTATES FOUND, LATER UPDATE THIS CODE TO FILTER DUPLICATES
    
    states_with_no_data=[]
    molid_to_ensembles={}
    for molid, needed_charge_states in molid_to_needed_charge_states.items():
        if molid not in molid_to_ensembles:
            molid_to_ensembles[molid] = {}
        for charge_state in needed_charge_states:
            #first try to get from high priority data
            if molid in high_priority_data and charge_state in high_priority_data[molid]:
                molid_to_ensembles[molid][charge_state] = high_priority_data[molid][charge_state]
            #then try to get from low priority data
            elif molid in low_priority_data and charge_state in low_priority_data[molid]:
                molid_to_ensembles[molid][charge_state] = low_priority_data[molid][charge_state]
            else:
                states_with_no_data.append((molid, charge_state))
                #print(f"Warning: no microspecies found for molid {molid} at charge state {charge_state}")
    
    #save to output tsv file
    output_smiles_rows=[]
    output_molid_rows=[]
    output_free_energy_rows=[]
    for molid, ensemble in molid_to_ensembles.items():
        for charge_state, microstates in ensemble.items():
            for microtuple in microstates:
                smiles, std_free_energy = microtuple
                output_smiles_rows.append(smiles)
                output_molid_rows.append(molid)
                output_free_energy_rows.append(std_free_energy)
    
    output_df = pl.DataFrame({
        "smiles": output_smiles_rows,
        "molid": output_molid_rows,
        "predicted_std_free_energy": output_free_energy_rows
    })
    output_path=Path(str(output_path))
    output_df.write_csv(output_path, separator='\t')
    print(f"Merged microspecies from pickle files into {output_path} with {len(output_smiles_rows)} microspecies entries.")
    print(f"States with no data for microspecies: {len(states_with_no_data)}")

if __name__=="__main__":
    merge_unique_molecules_flag=True
    merge_unipka_microspecies_picklefiles_flag=True

    script_dir = Path(__file__).resolve().parent
    print(f"script_dir: {script_dir}")

    if merge_unique_molecules_flag:
        merge_unique_molecules("molecules_table.tsv", tablefiles=[script_dir/"datafiles/rawdatafiles/collected_unique_molecules_v1.tsv", 
                                                                            script_dir/"datafiles/rawdatafiles/SAMPL_combined_final_processed.tsv"],
                                                                            check_unique=False)
        
    if merge_unipka_microspecies_picklefiles_flag:
        merge_unipka_microspecies_picklefiles(
            output_path="microspecies_table.tsv",
            combined_exp_macro_pka_input_file=script_dir/"datafiles/data/exp_macro_pka_datapoints/combined_unified_dataset.tsv",
            picklefiles_high_priority=[
                script_dir/"datafiles/rawdatafiles/combined_unipka_simple_template.pkl",
                script_dir/"datafiles/rawdatafiles/sampl_unipka_simple_template.pkl"
            ],
            picklefiles_low_priority=[
                script_dir/"datafiles/rawdatafiles/combined_unipka_full_template.pkl"
            ]
        )
        
    
