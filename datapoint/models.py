from django.db import models
from molecule.models import ChargeMacroState, MicroSpecies
from dataset.models import Dataset
from sources.models import Source

# Create your models here.
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

#review this model design later
class ExperimentalMicroPka(models.Model):
    rawdataID=models.CharField(max_length=100, unique=True)
    pre_microspecies=models.ForeignKey(MicroSpecies, on_delete=models.CASCADE, related_name='pre_microspecies')
    post_microspecies=models.ForeignKey(MicroSpecies, on_delete=models.CASCADE, related_name='post_microspecies')
    pka_value=models.FloatField()
    temperature=models.FloatField(null=True, blank=True) #temperature
    ionic_strength=models.FloatField(null=True, blank=True) #ionic strength
    primary_source=models.ForeignKey(Source, on_delete=models.CASCADE, null=True, blank=True)
    dataset=models.ForeignKey(Dataset, on_delete=models.CASCADE, null=True, blank=True)

class CalculatedMacroPka(models.Model):
    calculationID=models.CharField(max_length=100, unique=True)
    pre_charge_macrostate=models.ForeignKey(ChargeMacroState, on_delete=models.CASCADE, related_name='calc_pre_charge_macrostate')
    post_charge_macrostate=models.ForeignKey(ChargeMacroState, on_delete=models.CASCADE, related_name='calc_post_charge_macrostate')
    pka_value=models.FloatField()
    temperature=models.FloatField(null=True, blank=True) #temperature
    ionic_strength=models.FloatField(null=True, blank=True) #ionic strength
    calculation_method=models.CharField(max_length=100)

class CalculatedMicroPka(models.Model):
    calculationID=models.CharField(max_length=100, unique=True)
    pre_microspecies=models.ForeignKey(MicroSpecies, on_delete=models.CASCADE, related_name='calc_pre_microspecies')
    post_microspecies=models.ForeignKey(MicroSpecies, on_delete=models.CASCADE, related_name='calc_post_microspecies')
    pka_value=models.FloatField()
    temperature=models.FloatField(null=True, blank=True) #temperature
    ionic_strength=models.FloatField(null=True, blank=True) #ionic strength
    calculation_method=models.CharField(max_length=100)

#comments
class ExperimentalMacroPkaComment(models.Model):
    comment_type=models.CharField(max_length=100) #PROCESSING, WARNING, MISC
    datapoint=models.ForeignKey(ExperimentalMacroPka, on_delete=models.CASCADE, related_name='comments')
    comment_text=models.CharField(max_length=200)