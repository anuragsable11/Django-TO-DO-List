from django.conf import settings
from django.db import models

# Create your models here.
class TaskModel(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,null=True)
    title=models.CharField(max_length=30)
    desc=models.CharField(max_length=30)

class TrashModel(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,null=True)
    title=models.CharField(max_length=30)
    desc=models.CharField(max_length=30)

class CompleteModel(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,null=True)
    title=models.CharField(max_length=30)
    desc=models.CharField(max_length=30)

