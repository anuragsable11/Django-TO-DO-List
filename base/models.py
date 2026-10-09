from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


# Colours a list can wear: a small dot next to its name. Keys are stored, hex values live in the CSS.
LIST_COLORS = ['tangerine', 'blue', 'green', 'violet', 'pink', 'teal', 'amber', 'slate']


class TaskList(models.Model):
    """A named group of tasks, such as Work, Home or Study. Each task is in at most one list."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='task_lists')
    name = models.CharField(max_length=40)
    color = models.CharField(max_length=12, choices=[(c, c.title()) for c in LIST_COLORS], default=LIST_COLORS[0])
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(Lower('name'), 'user', name='unique_list_name_per_user'),
        ]

    def __str__(self):
        return self.name


class Task(models.Model):
    """One to-do. It stays the same row as it moves between the list, Completed and Trash."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        DONE = 'done', 'Done'
        TRASHED = 'trashed', 'Trashed'

    class Priority(models.IntegerChoices):
        LOW = 1, 'Low'
        NORMAL = 2, 'Normal'
        HIGH = 3, 'High'

    class Repeat(models.TextChoices):
        NONE = '', 'Does not repeat'
        DAILY = 'daily', 'Every day'
        WEEKDAYS = 'weekdays', 'Every weekday'
        WEEKLY = 'weekly', 'Every week'
        MONTHLY = 'monthly', 'Every month'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    notes = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.OPEN)
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, default=Priority.NORMAL)
    due_date = models.DateField(null=True, blank=True)
    repeat = models.CharField(max_length=8, choices=Repeat.choices, default=Repeat.NONE, blank=True)
    task_list = models.ForeignKey(TaskList, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    # Manual order on the task list, lowest first. New tasks go to the bottom.
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    trashed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['position', 'id']
        indexes = [
            models.Index(fields=['user', 'status', 'due_date'], name='task_user_status_due'),
            models.Index(fields=['user', 'status', 'position'], name='task_user_status_position'),
        ]

    def __str__(self):
        return self.title

    @property
    def is_high(self):
        return self.priority == self.Priority.HIGH

    @property
    def is_low(self):
        return self.priority == self.Priority.LOW


class Profile(models.Model):
    """Per-user preferences that Django's User model has no room for."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    # IANA name such as "Asia/Kolkata", picked up from the browser, so "today" means the user's today
    timezone = models.CharField(max_length=64, default='UTC')
    digest_enabled = models.BooleanField(default=False)
    digest_last_sent = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'Profile of {self.user}'
