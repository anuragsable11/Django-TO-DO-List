"""Everything that changes a task's state, in one place, so every change can be undone.

Each change returns an "undo item": a small JSON-safe dict with what the task looked like before.
Views keep the latest batch of items in the session; undo() puts those tasks back.
"""
import datetime

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .dates import next_occurrence
from .models import Task, TaskList, LIST_COLORS

UNDO_SECONDS = 10 * 60   # how long an Undo button keeps working


def _iso(value):
    return value.isoformat() if value else None


def snapshot(task, **extra):
    return {
        'id': task.id,
        'status': task.status,
        'due_date': _iso(task.due_date),
        'completed_at': _iso(task.completed_at),
        'trashed_at': _iso(task.trashed_at),
        **extra,
    }


def next_position(user):
    top = Task.objects.filter(user=user, status=Task.Status.OPEN).aggregate(top=Max('position'))['top']
    return (top or 0) + 1


def complete(task, today):
    """Check a task off. A repeating task stays on the list with its next due date,
    and a done copy is kept in Completed as the record of this occurrence."""
    item = snapshot(task)
    now = timezone.now()
    if task.repeat and task.status == Task.Status.OPEN:
        copy = Task.objects.create(
            user=task.user, title=task.title, notes=task.notes, priority=task.priority,
            due_date=task.due_date, task_list=task.task_list, status=Task.Status.DONE,
            created_at=task.created_at, completed_at=now,
        )
        item['copy_id'] = copy.id
        task.due_date = next_occurrence(task.repeat, task.due_date, today)
        task.save(update_fields=['due_date', 'updated_at'])
        return item
    task.status = Task.Status.DONE
    task.completed_at = now
    task.save(update_fields=['status', 'completed_at', 'updated_at'])
    return item


def trash(task):
    item = snapshot(task)
    task.status = Task.Status.TRASHED
    task.trashed_at = timezone.now()
    task.save(update_fields=['status', 'trashed_at', 'updated_at'])
    return item


def reopen(task):
    """Back onto the open list (from Completed or Trash), at the bottom."""
    item = snapshot(task)
    task.status = Task.Status.OPEN
    task.completed_at = None
    task.trashed_at = None
    task.position = next_position(task.user)
    task.save(update_fields=['status', 'completed_at', 'trashed_at', 'position', 'updated_at'])
    return item


def _date(value):
    return datetime.date.fromisoformat(value) if value else None


def _datetime(value):
    return datetime.datetime.fromisoformat(value) if value else None


@transaction.atomic
def undo(user, items):
    """Put tasks back the way their undo items describe. Only touches the user's own tasks."""
    restored = 0
    tasks = Task.objects.select_for_update().filter(user=user, id__in=[i['id'] for i in items]).in_bulk()
    for item in items:
        task = tasks.get(item['id'])
        if task is None:
            continue
        if item.get('copy_id'):
            Task.objects.filter(user=user, id=item['copy_id'], status=Task.Status.DONE).delete()
        task.status = item['status']
        task.due_date = _date(item['due_date'])
        task.completed_at = _datetime(item['completed_at'])
        task.trashed_at = _datetime(item['trashed_at'])
        task.save(update_fields=['status', 'due_date', 'completed_at', 'trashed_at', 'updated_at'])
        restored += 1
    return restored


def find_or_create_list(user, name):
    existing = TaskList.objects.filter(user=user, name__iexact=name).first()
    if existing:
        return existing, False
    return create_list(user, name), True


def create_list(user, name):
    count = TaskList.objects.filter(user=user).count()
    top = TaskList.objects.filter(user=user).aggregate(top=Max('position'))['top'] or 0
    return TaskList.objects.create(user=user, name=name, color=LIST_COLORS[count % len(LIST_COLORS)], position=top + 1)


@transaction.atomic
def reorder(user, ids):
    """Give the user's open tasks `ids` the order listed, reusing the positions they already hold,
    so reordering a filtered view (one list) leaves every other task where it was."""
    tasks = list(Task.objects.select_for_update().filter(user=user, status=Task.Status.OPEN, id__in=ids))
    if len(tasks) != len(set(ids)):
        return False
    by_id = {t.id: t for t in tasks}
    slots = sorted(t.position for t in tasks)
    # equal positions (old data) would make the order ambiguous: spread them out first
    if len(set(slots)) != len(slots):
        slots = list(range(slots[0], slots[0] + len(slots)))
    changed = []
    for task_id, position in zip(ids, slots):
        task = by_id[task_id]
        if task.position != position:
            task.position = position
            changed.append(task)
    Task.objects.bulk_update(changed, ['position'])
    return True
