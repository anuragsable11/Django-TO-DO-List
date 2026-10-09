from django.db import migrations


class Migration(migrations.Migration):
    """The three old tables are empty copies now that 0006 moved their rows into Task."""

    dependencies = [
        ('base', '0006_copy_tasks_into_task'),
    ]

    operations = [
        migrations.DeleteModel(name='CompleteModel'),
        migrations.DeleteModel(name='TaskModel'),
        migrations.DeleteModel(name='TrashModel'),
    ]
