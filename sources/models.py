from django.db import models

# Create your models here.
class Source(models.Model):
    name=models.CharField(max_length=100, unique=True)
    idname=models.CharField(max_length=100, unique=True)
    type=models.CharField(max_length=100) #article or weblink or book
    citation=models.CharField(max_length=1000)
    doi=models.CharField(max_length=200, null=True, blank=True)
    url=models.CharField(max_length=200, null=True, blank=True)