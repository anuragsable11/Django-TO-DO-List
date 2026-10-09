from django.contrib import admin

from .models import Profile, Task, TaskList


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'status', 'due_date', 'priority', 'repeat', 'task_list']
    list_filter = ['status', 'priority', 'repeat']
    search_fields = ['title', 'notes', 'user__username']
    raw_id_fields = ['user', 'task_list']


@admin.register(TaskList)
class TaskListAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'color']
    search_fields = ['name', 'user__username']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'timezone', 'digest_enabled', 'digest_last_sent']
