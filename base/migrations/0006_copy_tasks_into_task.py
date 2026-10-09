"""Copy every task from the three old tables (open, completed, trash) into the single Task table.

Rows keep their owner, title and note, and the open list keeps its order (oldest first).
The old tables had no dates, so completed and trashed tasks are stamped with the migration time.
Rows without an owner date from before accounts existed: nobody could see them, so they are skipped.
"""
from django.db import migrations
from django.utils import timezone


def copy_forward(apps, schema_editor):
    Task = apps.get_model('base', 'Task')
    sources = [
        (apps.get_model('base', 'TaskModel'), 'open'),
        (apps.get_model('base', 'CompleteModel'), 'done'),
        (apps.get_model('base', 'TrashModel'), 'trashed'),
    ]
    now = timezone.now()
    new_rows = []
    for model, status in sources:
        for position, old in enumerate(model.objects.filter(user__isnull=False).order_by('id'), start=1):
            new_rows.append(Task(
                user_id=old.user_id,
                title=old.title,
                notes=old.desc,
                status=status,
                position=position,
                created_at=now,
                completed_at=now if status == 'done' else None,
                trashed_at=now if status == 'trashed' else None,
            ))
    Task.objects.bulk_create(new_rows, batch_size=500)


def copy_backward(apps, schema_editor):
    targets = {
        'open': apps.get_model('base', 'TaskModel'),
        'done': apps.get_model('base', 'CompleteModel'),
        'trashed': apps.get_model('base', 'TrashModel'),
    }
    Task = apps.get_model('base', 'Task')
    for task in Task.objects.order_by('position', 'id'):
        targets[task.status].objects.create(user_id=task.user_id, title=task.title[:30], desc=task.notes[:30])
    Task.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0005_task_list_profile'),
    ]

    operations = [
        migrations.RunPython(copy_forward, copy_backward),
    ]
