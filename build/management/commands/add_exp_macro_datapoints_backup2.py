import polars as pl
from django.core.management.base import BaseCommand
from datapoint.models import ExperimentalMacroPka, ExperimentalMacroPkaComment
from molecule.models import Molecule, ChargeMacroState
from dataset.models import Dataset
from sources.models import Source
from django.db import transaction

"""
ExperimentalMacroPka definition for reference:

class ExperimentalMacroPka(models.Model):
    rawdataID=models.CharField(max_length=100, unique=True)
    pre_charge_macrostate=models.ForeignKey(ChargeMacroState, on_delete=models.CASCADE, related_name='pre_charge_macrostate')
    post_charge_macrostate=models.ForeignKey(ChargeMacroState, on_delete=models.CASCADE, related_name='post_charge_macrostate')
    pka_value=models.FloatField()
    temperature=models.FloatField(null=True, blank=True) #temperature
    ionic_strength=models.FloatField(null=True, blank=True) #ionic strength
    state_assignment_method=models.CharField(max_length=100)
    assignment_error=models.FloatField(null=True, blank=True)
    primary_source=models.ForeignKey(Source, on_delete=models.CASCADE, null=True, blank=True)
    dataset=models.ForeignKey(Dataset, on_delete=models.CASCADE, null=True, blank=True)
"""
#automatically add missing intermediate charge states
#add argument --no_consecutiveplaceholders to not add missing intermediate charge states

class Command(BaseCommand):
    help="""
    Add experimental macroscopic pKa datapoints from a table file. 

    The table file must contain the following columns: 
    molid: str, should already exist in the database
    rawdataID: str, unique identifier for the datapoint
    dataset: str, dataset idname, should already exist in the database
    assigned_charge_state_transition: str, format "pre_charge>>post_charge", e.g. "0>>1"
    Exp_Macro_pKa_processed: float, experimental macroscopic pKa value
    T_processed: float, temperature in Kelvin (optional)
    I_processed: float, ionic strength in M (optional)
    assignment_method: str, method used to assign the pKa value to the charge state transition
    assignment_error: float, uncertainty in the pKa assignment (this shouldn't be optional)
    primary_source: str, name of the primary source, should already exist in the database ( optional)
    comments: str, optional comments in the format "type1: comment1; type2: comment2"
    exclude_flag: str, if set to "exclude", this row will be skipped
    The table file may contain additional columns, which will be ignored.

    Example row:
    molid, rawdataID, dataset, assigned_charge_state_transition, Exp_Macro_pKa_processed, T_processed, I_processed, assignment_method, assignment_error, primary_source, comments, excluded_flag
    MOL123, RD001, Dataset_A, 0>>1, 7.4, 298.15, 0.1, Potentiometric titration, 0.2, Source_X, type1: comment1; type2: comment2, 
    The order of the columns does not matter, but the header row must be present.
    Required columns: molid, rawdataID, dataset, assigned_charge_state_transition, Exp_Macro_pKa_processed, assignment_method, assignment_error.
    Optional columns: T_processed, I_processed, primary_source, comments, excluded_flag.
    Note: comments should be in the format "type: comment", multiple comments separated by semicolons.

    For adding comments to existing datapoints, use the 'comments' column with the format specified above.
    To overwrite existing datapoints with the same rawdataID, use the --overwrite flag.
    Each comment will be added as a separate ExperimentalMacroPkaComment linked to the corresponding datap oint.
    ExperimentalMacroPkaComment format: comment_type, datapoint (FK), comment_text
    Required columns for comments: molid, rawdataID, assigned_charge_state_transition
    """

    def add_arguments(self, parser):
        parser.add_argument('tablefile', type=str, help='Path to the table file containing experimental macroscopic pKa datapoints')
        parser.add_argument('--separator', type=str, help='separator used in the table file, default=\t (tab)', default='\t')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite all existing datapoints with same molid and charge_state_id already in database')

    def handle(self, *args, **kwargs):
        tablefile=kwargs['tablefile']
        separator=kwargs['separator']
        overwrite=kwargs['overwrite']
        if separator.lower()=='tab':
            separator='\t'
        df=pl.read_csv(tablefile, separator=separator, infer_schema=False)
        
        # Collect all unique molids and charge states needed
        molids_needed = set()
        charge_states_needed = {}  # {molid: {charge_pre, charge_post}}
        
        for row in df.iter_rows(named=True):
            exclude_flag=row.get('exclude_flag', '')
            if exclude_flag.lower().strip()=='exclude':
                continue
            
            molid = row['molid'].strip()
            molids_needed.add(molid)
            
            assigned_ch_state_trans_str = row.get('assigned_charge_state_transition')
            if assigned_ch_state_trans_str:
                try:
                    charge_state_pre = int(assigned_ch_state_trans_str.split(">>")[0].strip())
                    charge_state_post = int(assigned_ch_state_trans_str.split(">>")[1].strip())
                    
                    if molid not in charge_states_needed:
                        charge_states_needed[molid] = set()
                    charge_states_needed[molid].add(charge_state_pre)
                    charge_states_needed[molid].add(charge_state_post)
                except (ValueError, IndexError):
                    pass

        #Check if needed charge states are consecutive for each molecule, if not add the missing intermediate charge states
        for molid, charges in charge_states_needed.items():
            min_charge = min(charges)
            max_charge = max(charges)
            full_charge_set = set(range(min_charge, max_charge + 1))
            missing_charges = full_charge_set - charges
            if missing_charges:
                #self.stdout.write(self.style.WARNING(f'For molecule {molid}, missing intermediate charge states detected: {missing_charges}. They will be added automatically.'))
                charges.update(missing_charges)

        # Bulk fetch all molecules
        molecules_dict = {m.molid: m for m in Molecule.objects.filter(molid__in=molids_needed)}
        
        # Bulk fetch existing charge macrostates
        existing_cms = ChargeMacroState.objects.filter(
            molecule__molid__in=molids_needed
        ).select_related('molecule')
        
        # Build lookup: {(molid, charge): ChargeMacroState}
        cms_lookup = {(cms.molecule.molid, cms.charge): cms for cms in existing_cms}
        
        # Determine which charge states need to be created
        cms_to_create = []
        for molid, charges in charge_states_needed.items():
            if molid not in molecules_dict:
                continue
            
            molecule = molecules_dict[molid]
            for charge in charges:
                if (molid, charge) not in cms_lookup:
                    charge_state_id = f'CS_{charge}'
                    cms_obj = ChargeMacroState(
                        charge_state_id=charge_state_id,
                        molecule=molecule,
                        charge=charge
                    )
                    cms_to_create.append(cms_obj)
                    # Add to lookup immediately for later reference
                    cms_lookup[(molid, charge)] = cms_obj
        
        # Bulk create missing charge macrostates
        if cms_to_create:
            created_cms = ChargeMacroState.objects.bulk_create(cms_to_create)
            self.stdout.write(self.style.SUCCESS(f'Created {len(created_cms)} new ChargeMacroState entries.'))
            
            # Update lookup with newly created objects (with PKs)
            for cms in created_cms:
                cms_lookup[(cms.molecule.molid, cms.charge)] = cms
        
        # Bulk fetch datasets and sources
        dataset_idnames = set()
        source_names = set()
        for row in df.iter_rows(named=True):
            excluded_flag = row.get('excluded_flag', '')
            if excluded_flag.lower().strip() == 'excluded':
                continue
            dataset_idnames.add(row['dataset'].strip())
            primary_source = row.get('primary_source', '').strip()
            if primary_source:
                source_names.add(primary_source)
        
        datasets_dict = {ds.idname: ds for ds in Dataset.objects.filter(idname__in=dataset_idnames)}
        sources_dict = {src.name: src for src in Source.objects.filter(name__in=source_names)}
        
        # Get already existing rawdataIDs
        rawdataids = []
        for row in df.iter_rows(named=True):
            rawdataid = row['rawdataID'].strip()
            rawdataids.append(rawdataid)
        existing_rawdataids = set(ExperimentalMacroPka.objects.filter(rawdataID__in=rawdataids).values_list('rawdataID', flat=True))
        
        data_to_create = []
        data_to_overwrite = []
        comments_to_create = []
        
        for row in df.iter_rows(named=True):
            rawdataid = row['rawdataID'].strip()
            dataset_str = row['dataset'].strip()
            molid = row['molid'].strip()
            comments_str = row.get('comments', '')
            exp_macro_pka_str = row['Exp_Macro_pKa_processed']
            T_str = row.get('T_processed')
            I_str = row.get('I_processed')
            assigned_ch_state_trans_str = row.get('assigned_charge_state_transition')
            assignment_error_str = row.get('assignment_error')
            assignment_method = row['assignment_method']
            primary_source_str = row.get('primary_source', '').strip()

            # Skip excluded rows
            excluded_flag = row.get('excluded_flag', '')
            if excluded_flag.lower().strip() == 'excluded':
                continue
            
            # Check if molecule exists
            if molid not in molecules_dict:
                self.stdout.write(self.style.ERROR(f'Molecule with molid {molid} does not exist, skipping...'))
                continue
            
            # Get charge macrostates
            if not assigned_ch_state_trans_str:
                self.stdout.write(self.style.WARNING(f'No assigned charge state transition for rawdataID {rawdataid}, skipping...'))
                continue
            
            try:
                charge_state_pre = int(assigned_ch_state_trans_str.split(">>")[0].strip())
                charge_state_post = int(assigned_ch_state_trans_str.split(">>")[1].strip())
            except (ValueError, IndexError):
                self.stdout.write(self.style.ERROR(f'Could not parse charge state transition: {assigned_ch_state_trans_str}, skipping...'))
                continue
            
            charge_macrostate_pre = cms_lookup.get((molid, charge_state_pre))
            charge_macrostate_post = cms_lookup.get((molid, charge_state_post))
            
            if not charge_macrostate_pre or not charge_macrostate_post:
                self.stdout.write(self.style.ERROR(f'ChargeMacroState with charge {charge_state_pre} or {charge_state_post} for molecule {molid} not found, skipping...'))
                continue

            # Parse experimental pka value
            try:
                exp_macro_pka = float(exp_macro_pka_str)
            except (ValueError, TypeError):
                self.stdout.write(self.style.ERROR(f'Could not parse experimental macro pKa value: {exp_macro_pka_str}, skipping...'))
                continue
            
            # Parse assignment error
            assignment_error = None
            if assignment_error_str and assignment_error_str.strip():
                try:
                    assignment_error = float(assignment_error_str)
                except (ValueError, TypeError):
                    self.stdout.write(self.style.WARNING(f'Could not parse assignment error value: {assignment_error_str}, setting to None'))
            
            # Parse temperature and ionic strength
            T = None
            if T_str and T_str.strip():
                try:
                    T = float(T_str)
                except (ValueError, TypeError):
                    self.stdout.write(self.style.WARNING(f'Could not parse temperature value: {T_str}, setting to None'))
            
            I = None
            if I_str and I_str.strip():
                try:
                    I = float(I_str)
                except (ValueError, TypeError):
                    self.stdout.write(self.style.WARNING(f'Could not parse ionic strength value: {I_str}, setting to None'))
            
            # Get comments
            comments_list = []
            if comments_str and comments_str.strip():
                comments_str_list = comments_str.split(";")
                for commentfull in comments_str_list:
                    if ":" in commentfull:
                        comment_type = commentfull.split(":")[0].strip()
                        comment_text = commentfull.split(":")[1].strip()
                        comments_list.append((comment_type, comment_text, rawdataid))
                    else:
                        self.stdout.write(self.style.WARNING(f"Wrong comment format (missing colon): {commentfull}, skipping this comment..."))
            comments_to_create.extend(comments_list)

            # Get dataset
            dataset = datasets_dict.get(dataset_str)
            if not dataset:
                self.stdout.write(self.style.ERROR(f'Dataset with idname {dataset_str} not found, skipping...'))
                continue

            # Get source
            source = sources_dict.get(primary_source_str) if primary_source_str else None
            
            # Create ExperimentalMacroPka object
            datapoint_obj = ExperimentalMacroPka(
                rawdataID=rawdataid,
                pre_charge_macrostate=charge_macrostate_pre,
                post_charge_macrostate=charge_macrostate_post,
                pka_value=exp_macro_pka,
                temperature=T,
                ionic_strength=I,
                state_assignment_method=assignment_method,
                assignment_error=assignment_error,
                primary_source=source,
                dataset=dataset
            )
            
            if rawdataid in existing_rawdataids:
                if overwrite:
                    data_to_overwrite.append(datapoint_obj)
                else:
                    self.stdout.write(self.style.WARNING(f'Skipping rawdataID {rawdataid}: already exists in database'))
                    continue
            else:
                data_to_create.append(datapoint_obj)

        with transaction.atomic():
            # Bulk create new datapoints
            if data_to_create:
                created_datapoints = ExperimentalMacroPka.objects.bulk_create(data_to_create)
                self.stdout.write(self.style.SUCCESS(f'Created {len(created_datapoints)} new ExperimentalMacroPka datapoints.'))
            
            # Overwrite existing datapoints
            if data_to_overwrite:
                rawdata_ids_to_delete = [dp.rawdataID for dp in data_to_overwrite]
                ExperimentalMacroPka.objects.filter(rawdataID__in=rawdata_ids_to_delete).delete()
                overwritten_datapoints = ExperimentalMacroPka.objects.bulk_create(data_to_overwrite)
                self.stdout.write(self.style.SUCCESS(f'Overwritten {len(overwritten_datapoints)} existing ExperimentalMacroPka datapoints.'))
            
            # Create comments
            if comments_to_create:
                comment_objs = []
                # Fetch all needed datapoints in one query
                rawdata_ids_for_comments = list(set(c[2] for c in comments_to_create))
                datapoints_for_comments = {dp.rawdataID: dp for dp in ExperimentalMacroPka.objects.filter(rawdataID__in=rawdata_ids_for_comments)}
                
                for comment_type, comment_text, rawdataid in comments_to_create:
                    datapoint_obj = datapoints_for_comments.get(rawdataid)
                    if not datapoint_obj:
                        self.stdout.write(self.style.ERROR(f'Could not find ExperimentalMacroPka with rawdataID {rawdataid} for adding comment, skipping comment...'))
                        continue
                    
                    if rawdataid in existing_rawdataids and not overwrite:
                        # Skip adding comments to non-overwritten datapoints
                        continue
                    
                    comment_obj = ExperimentalMacroPkaComment(
                        comment_type=comment_type,
                        datapoint=datapoint_obj,
                        comment_text=comment_text
                    )
                    comment_objs.append(comment_obj)
                
                if comment_objs:
                    created_comments = ExperimentalMacroPkaComment.objects.bulk_create(comment_objs)
                    self.stdout.write(self.style.SUCCESS(f'Created {len(created_comments)} ExperimentalMacroPka comments.'))

