from django.db import models

# Create your models here.
class MolecularProperties(models.Model):
    molecule=models.OneToOneField('Molecule', on_delete=models.CASCADE, related_name='molecular_properties', null=True, blank=True)
    molecular_weight=models.FloatField()
    heavy_atom_count=models.IntegerField()
    num_hbond_donors=models.IntegerField()
    num_hbond_acceptors=models.IntegerField()

class StereoParentMolecule(models.Model):
    name=models.CharField(max_length=100, default="")
    smiles=models.CharField(max_length=500)
    inchi=models.CharField(max_length=1000)
    inchikey=models.CharField(max_length=100)

class Molecule(models.Model):
    name=models.CharField(max_length=100, default="")
    molid=models.CharField(max_length=50, unique=True)
    smiles=models.CharField(max_length=500)
    smiles_atom_numbered=models.CharField(max_length=500)
    inchi=models.CharField(max_length=1000)
    inchikey=models.CharField(max_length=100)
    stereo_parent=models.ForeignKey(StereoParentMolecule, on_delete=models.CASCADE, null=True, blank=True)
    image_path=models.CharField(max_length=200, null=True, blank=True)

class MoleculeName(models.Model):
    molecule=models.ForeignKey(Molecule, on_delete=models.CASCADE)
    name_type=models.CharField(max_length=100) #IUPAC, COMMON, TRADE
    name_value=models.CharField(max_length=200)

class ChargeMacroState(models.Model):
    charge_state_id=models.CharField(max_length=10) #this is unique within a molecule
    molecule=models.ForeignKey(Molecule, on_delete=models.CASCADE)
    charge=models.IntegerField()

class MicroSpecies(models.Model):
    microspecies_id=models.CharField(max_length=10) #this is unique within a molecule
    #molecule=models.ForeignKey(Molecule, on_delete=models.CASCADE)
    smiles=models.CharField(max_length=500)
    #smiles_explicit_hydrogens=models.CharField(max_length=500)
    smiles_atom_numbered=models.CharField(max_length=500)
    total_charge=models.IntegerField()
    charge_macrostate=models.ForeignKey(ChargeMacroState, on_delete=models.CASCADE)
    image_path=models.CharField(max_length=200, null=True, blank=True)
    predicted_std_free_energy=models.FloatField(null=True, blank=True) #in kcal/mol
    ph_independent_pop=models.FloatField(null=True, blank=True) #between 0 and 1

class MicrospeciesConformer(models.Model):
    microspecies=models.ForeignKey(MicroSpecies, on_delete=models.CASCADE)
    conformer_id=models.CharField(max_length=20) #unique within microspecies
    sdfpath=models.CharField(max_length=200)
    energy=models.FloatField(null=True, blank=True)