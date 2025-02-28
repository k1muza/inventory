from django_q.tasks import async_task
from django.core.management import call_command

def recreate_batches_task():
    call_command('recreate_batches')

def trigger_recreate_batches():
    task_id = async_task('inventory.tasks.recreate_batches_task')
    return task_id
