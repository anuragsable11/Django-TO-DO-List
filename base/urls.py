from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('about/', views.about, name='about'),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),

    # Views of the list
    path('tasks/', views.home, name='home'),
    path('tasks/today/', views.today_view, name='today'),
    path('tasks/upcoming/', views.upcoming, name='upcoming'),
    path('tasks/overdue/', views.overdue, name='overdue'),
    path('complete/', views.complete, name='complete'),
    path('trash/', views.trash, name='trash'),
    path('search/', views.search, name='search'),

    # Adding and editing
    path('add/', views.add, name='add'),
    path('update/<int:pk>', views.update, name='update'),
    path('tasks/reorder/', views.reorder, name='reorder'),

    # One task
    path('hcomplete/<int:pk>', views.hcomplete, name='hcomplete'),
    path('delete/<int:pk>', views.delete, name='delete'),
    path('restore/<int:pk>', views.restore, name='restore'),
    path('recover/<int:pk>', views.recover, name='recover'),
    path('hdelete/<int:pk>', views.hdelete, name='hdelete'),

    # Many at once
    path('complete_all/', views.complete_all, name='complete_all'),
    path('delete_all/', views.delete_all, name='delete_all'),
    path('restore_all/', views.restore_all, name='restore_all'),
    path('clear_complete/', views.clear_complete, name='clear_complete'),
    path('delete_all_per/', views.delete_all_per, name='delete_all_per'),
    path('undo/', views.undo, name='undo'),

    # Lists
    path('lists/new/', views.list_create, name='list_create'),
    path('lists/<int:pk>/', views.list_detail, name='list'),
    path('lists/<int:pk>/edit/', views.list_edit, name='list_edit'),
    path('lists/<int:pk>/delete/', views.list_delete, name='list_delete'),

    # Settings and the morning email
    path('settings/', views.settings_view, name='settings'),
    path('settings/test-email/', views.digest_test, name='digest_test'),
    path('cron/digest/', views.cron_digest, name='cron_digest'),
]
