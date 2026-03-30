from django.db import models

# Create your models here.
class TaskModel(models.Model):
    title=models.CharField(max_length=30)
    desc=models.CharField(max_length=30)
    
class TrashModel(models.Model):
    title=models.CharField(max_length=30)
    desc=models.CharField(max_length=30)   
    
class CompleteModel(models.Model):
    title=models.CharField(max_length=30)
    desc=models.CharField(max_length=30)      
    
