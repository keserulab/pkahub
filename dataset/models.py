from django.db import models
from sources.models import Source

# Create your models here.
class Dataset(models.Model):
    name=models.CharField(max_length=100, unique=True)
    idname=models.CharField(max_length=100, unique=True)
    priority=models.IntegerField(default=0) #lower number means higher priority
    source=models.ForeignKey(Source, on_delete=models.CASCADE)
    description=models.TextField()
    license=models.CharField(max_length=200, null=True, blank=True)