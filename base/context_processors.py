from django.utils.functional import cached_property

from .models import TaskModel,TrashModel,CompleteModel


class TaskCounts:
    """The signed-in user's list sizes for the sidebar. Each one is only queried if a template uses it."""

    def __init__(self,user):
        self.user=user

    @cached_property
    def open(self):
        return TaskModel.objects.filter(user=self.user).count()

    @cached_property
    def done(self):
        return CompleteModel.objects.filter(user=self.user).count()

    @cached_property
    def trash(self):
        return TrashModel.objects.filter(user=self.user).count()

    @cached_property
    def progress(self):
        """Share of all tasks (open + completed) that are completed, as a whole percent."""
        total=self.open+self.done
        return round(self.done*100/total) if total else 0

    @cached_property
    def oldest(self):
        """The open task that has waited the longest, for Stripes' sidebar reminder."""
        return TaskModel.objects.filter(user=self.user).order_by('id').first()


def task_counts(request):
    if not request.user.is_authenticated:
        return {}
    return {'task_counts':TaskCounts(request.user)}
