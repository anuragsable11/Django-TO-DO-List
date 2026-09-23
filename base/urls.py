from django.contrib.auth import views as auth_views
from django.urls import path
from .views import *

urlpatterns = [
    path('',landing,name='landing'),
    path('tasks/',home,name='home'),
    path('login/',auth_views.LoginView.as_view(redirect_authenticated_user=True),name='login'),
    path('logout/',auth_views.LogoutView.as_view(),name='logout'),
    path('register/',register,name='register'),
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
    path('hdelete/<int:pk>',hdelete,name='hdelete'),
    path('restore/<int:pk>',restore,name='restore'),
    path('clear_complete/',clear_complete,name='clear_complete'),
]
