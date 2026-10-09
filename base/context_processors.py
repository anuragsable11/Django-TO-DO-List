from django.db.models import Count, Q
from django.utils import timezone
from django.utils.functional import cached_property

from .models import Task, TaskList


class TaskCounts:
    """The signed-in user's numbers for the sidebar. Nothing is queried until a template asks,
    and all the counts come from a single query (the database may be far away)."""

    def __init__(self, user):
        self.user = user

    @cached_property
    def today_date(self):
        return timezone.localdate()

    @cached_property
    def _counts(self):
        today = self.today_date
        is_open = Q(status=Task.Status.OPEN)
        return Task.objects.filter(user=self.user).aggregate(
            open=Count('id', filter=is_open),
            done=Count('id', filter=Q(status=Task.Status.DONE)),
            trash=Count('id', filter=Q(status=Task.Status.TRASHED)),
            overdue=Count('id', filter=is_open & Q(due_date__lt=today)),
            today=Count('id', filter=is_open & Q(due_date__lte=today)),  # what the Today view shows
            upcoming=Count('id', filter=is_open & Q(due_date__gt=today)),
        )

    def __getattr__(self, name):
        if name in ('open', 'done', 'trash', 'overdue', 'today', 'upcoming'):
            return self._counts[name]
        raise AttributeError(name)

    @cached_property
    def progress(self):
        """Share of all tasks (open + completed) that are completed, as a whole percent."""
        total = self.open + self.done
        return round(self.done * 100 / total) if total else 0

    @cached_property
    def lists(self):
        return list(TaskList.objects.filter(user=self.user).annotate(
            open=Count('tasks', filter=Q(tasks__status=Task.Status.OPEN))))

    @cached_property
    def attention(self):
        """What Stripes mentions in the sidebar: the oldest overdue task, else the most important
        one due today, else the one that has waited longest. Returns (kind, task) or None."""
        tasks = Task.objects.filter(user=self.user, status=Task.Status.OPEN)
        today = self.today_date
        task = tasks.filter(due_date__lt=today).order_by('due_date', '-priority', 'position').first()
        if task:
            return {'kind': 'overdue', 'task': task}
        task = tasks.filter(due_date=today).order_by('-priority', 'position').first()
        if task:
            return {'kind': 'today', 'task': task}
        task = tasks.order_by('created_at', 'id').first()
        return {'kind': 'oldest', 'task': task} if task else None


def task_counts(request):
    if not request.user.is_authenticated:
        return {}
    return {'task_counts': TaskCounts(request.user)}
