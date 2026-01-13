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

class Command(BaseCommand):
    help="""Add experimental macroscopic pKa datapoints from a table file. The table file must contain the following columns: molid, charge_state_id, exp_macro_pka, exp_macro_pka_uncertainty, source_name, source_year, source_doi, dataset_name. Optional column: comment"""

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
        
        #get already existing rawdataIDs
        rawdataids=[]
        for row in df.iter_rows(named=True):
            rawdataid=row['rawdataID'].strip()
            rawdataids.append(rawdataid)
        existing_rawdataids=set(ExperimentalMacroPka.objects.filter(rawdataID__in=rawdataids).values_list('rawdataID', flat=True))
        
        data_to_create=[]
        data_to_overwrite=[]
        comments_to_create=[]
        for row in df.iter_rows(named=True):
            rawdataid=row['rawdataID'].strip()
            dataset_str=row['dataset'].strip()
            molid=row['molid'] #needs a molid row
            comments_str=row['comments'] if 'comments' in row else ''
            reprsmiles=row['reprSMILES'] if 'reprSMILES' in row else ''
            exp_macro_pka_str=row['Exp_Macro_pKa_processed']
            T_str=row['T_processed']
            I_str=row['I_processed']
            assigned_ch_state_trans_str=row['assigned_charge_state_transition'] #n>>n-1 charge state transition
            assignment_error_str=row['assignment_error']
            assignment_method=row['assignment_method']
            primary_source=row['primary_source']

            #skip excluded rows
            excluded_flag=row['excluded_flag'] if 'excluded_flag' in row else ''
            if excluded_flag.lower().strip()=='excluded':
                continue
            
            #there is need to be a molecule with this molid
            try:
                molecule=Molecule.objects.get(molid=molid)
            except Molecule.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Molecule with molid {molid} does not exist, skipping...'))
                continue
            
            #get charge macrostate
            if assigned_ch_state_trans_str is not None:
                charge_state_pre=int(assigned_ch_state_trans_str.split(">>")[0].strip())
                charge_state_post=int(assigned_ch_state_trans_str.split(">>")[1].strip())
            else:
                print(f'No assigned charge state transition for rawdataID {rawdataid}, skipping...')
                continue
            try:
                charge_macrostate_pre=ChargeMacroState.objects.get(molecule=molecule, charge=charge_state_pre)
                charge_macrostate_post=ChargeMacroState.objects.get(molecule=molecule, charge=charge_state_post)
            except ChargeMacroState.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'ChargeMacroState with charge {charge_state_pre} or {charge_state_post} for molecule {molid} does not exist, skipping...'))
                continue

            #parse experimental pka value
            try:
                exp_macro_pka=float(exp_macro_pka_str)
            except:
                self.stdout.write(self.style.ERROR(f'Could not parse experimental macro pKa value: {exp_macro_pka_str}, skipping...'))
                continue
            #parse assignment error
            assignment_error=None
            if assignment_error_str is not None:
                if assignment_error_str.strip()!='':
                    try:
                        assignment_error=float(assignment_error_str)
                    except:
                        self.stdout.write(self.style.WARNING(f'Could not parse assignment error value: {assignment_error_str}, setting to None'))
                        assignment_error=None
            #parse temperature and ionic strength
            T=None
            if T_str is not None:
                if T_str.strip()!='':
                    try:
                        T=float(T_str)
                    except:
                        print(f'Could not parse temperature value: {T_str}, setting to None')
                        T=None
            I=None
            if I_str is not None:
                if I_str.strip()!='':
                    try:
                        I=float(I_str)
                    except:
                        print(f'Could not parse ionic strength value: {I_str}, setting to None')
                        I=None
            
            #get comments
            comments_list=[]
            if comments_str is not None:
                if comments_str.strip()!='':
                    comments_str_list=comments_str.split(";")
                    if len(comments_str_list)>0:
                        for commentfull in comments_str_list:
                            if ":" in commentfull:
                                #print(f'Processing comment: {commentfull}')
                                comment_type=commentfull.split(":")[0].strip()
                                comment_text=commentfull.split(":")[1].strip()
                                comments_list.append((comment_type, comment_text, rawdataid))
                            else:
                                print(f"wrong comment format (missing colon): {commentfull}, skipping this comment...")
            comments_to_create.extend(comments_list)

            #get dataset
            dataset=Dataset.objects.get(idname=dataset_str)

            #get source
            source=None
            if primary_source is not None:
                if primary_source.strip()!='':
                    source=Source.objects.get(name=primary_source.strip())
            
            #create ExperimentalMacroPka object
            datapoint_obj=ExperimentalMacroPka(
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
            #bulk create new datapoints
            if len(data_to_create)>0:
                created_datapoints=ExperimentalMacroPka.objects.bulk_create(data_to_create)
                self.stdout.write(self.style.SUCCESS(f'Created {len(created_datapoints)} new ExperimentalMacroPka datapoints.'))
            
            #overwrite existing datapoints
            if len(data_to_overwrite)>0:
                for datapoint in data_to_overwrite:
                    ExperimentalMacroPka.objects.filter(rawdataID=datapoint.rawdataID).delete()
                overwritten_datapoints=ExperimentalMacroPka.objects.bulk_create(data_to_overwrite)
                self.stdout.write(self.style.SUCCESS(f'Overwritten {len(overwritten_datapoints)} existing ExperimentalMacroPka datapoints.'))
            
            #create comments
            if len(comments_to_create)>0:
                comment_objs=[]
                for comment_tuple in comments_to_create:
                    comment_type, comment_text, rawdataid=comment_tuple
                    try:
                        datapoint_obj=ExperimentalMacroPka.objects.get(rawdataID=rawdataid)
                    except ExperimentalMacroPka.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f'Could not find ExperimentalMacroPka with rawdataID {rawdataid} for adding comment, skipping comment...'))
                        continue
                    comment_obj=ExperimentalMacroPkaComment(
                        comment_type=comment_type,
                        datapoint=datapoint_obj,
                        comment_text=comment_text
                    )
                    if rawdataid in existing_rawdataids and not overwrite:
                        #skip adding comments to non-overwritten datapoints
                        continue
                    else:
                        comment_objs.append(comment_obj)
                created_comments=ExperimentalMacroPkaComment.objects.bulk_create(comment_objs)
                self.stdout.write(self.style.SUCCESS(f'Created {len(created_comments)} ExperimentalMacroPka comments.'))

