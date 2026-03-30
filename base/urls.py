from django.urls import path
from .views import *

urlpatterns = [
    path('',home,name='home'),
    path('add/',add,name='add'),
    path('complete/',complete,name='complete'),
    path('trash/',trash,name='trash'),
    path('about/',about,name='about'),
    path('delete/<int:pk>',delete,name='delete'),
    path('update/<int:pk>',update,name='update'),
    path('recover/<int:pk>',recover,name='recover'),
    path('hcomplete/<int:pk>',hcomplete,name='hcomplete'),
    path('complete_all/',complete_all,name='complete_all'),
    path('delete_all/',delete_all,name='delete_all'),
    path('restore_all/',restore_all,name='restore_all'),
    path('delete_all_per/',delete_all_per,name='delete_all_per'),
    path('hdelete/<int:pk>',hdelete,name='hdelete')
]
