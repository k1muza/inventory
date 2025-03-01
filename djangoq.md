# Background Task Processing with DjangoQ

This page describes how to set up and run [DjangoQ](https://django-q.readthedocs.io/en/latest/) as a background task scheduler and worker on your server. DjangoQ allows you to schedule recurring tasks and handle asynchronous jobs outside of the main Django process.

---

## 1. Install DjangoQ

In your virtual environment (within your project directory), install DjangoQ:

```bash
pip install django-q
```
Then add to your `settings.py`:

```python
INSTALLED_APPS = [
    ...
    'django_q',
]
```

## 2. Configure DjangoQ

In your `settings.py`:

```python
Q_CLUSTER = {
    'name': 'DjangoQ',
    "workers": 4,          # Number of worker processes
    "timeout": 120,        # Seconds before a task is timed out
    "retry": 180,          # Seconds to wait before retrying a failed task
    "queue_limit": 50,     # Maximum queued tasks before new tasks are rejected
    "bulk": 10,            # Number of tasks to process per worker iteration
    "orm": "default",      # Use Django ORM for broker and result backend
}
```
Adjust these settings based on your environment and workload.

## 3. Run DjangoQ
To verify everything works, run the following command:

```bash
python manage.py qcluster
```
You should see logs indicating that DjangoQ is starting workers and listening for tasks.

## 4. Create a Systemd Service for DjangoQ
To have DjangoQ run automatically on system startup:
1. **Create a systemd service file** in `/etc/systemd/system/djangoq.service`:

```bash
sudo nano /etc/systemd/system/djangoq.service
```

2. Add the following content, adjusting paths and user/group as needed:

```ini
[Unit]
Description=Django Q Cluster
After=network.target

[Service]
User=ubuntu
Group=www-data

WorkingDirectory=/home/ubuntu/inventory
Environment="PATH=/home/ubuntu/inventory/venv/bin"

ExecStart=/home/ubuntu/inventory/venv/bin/python manage.py qcluster

Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
- **User**: The system user that runs DjangoQ. Often the same user running your other services (e.g., ubuntu).
- **WorkingDirectory**: Path to your Django project root (where manage.py is located).
- **ExecStart**: Full path to your Python environment and the qcluster command.

## 5. Enable and Start DjangoQ
After creating the service file, run the following commands:

```bash
sudo systemctl daemon-reload
sudo systemctl start djangoq
sudo systemctl enable djangoq
```

Check the status:

```bash
sudo systemctl status djangoq
```
You should see logs indicating that DjangoQ is running with active workers.

## 6. Manage DjangoQ
### 6.1 Restarting DjangoQ
If you update your code or configuration:

```bash
sudo systemctl restart djangoq
```

### 6.2 Viewing DjangoQ Logs
```bash
journalctl -u djangoq -f
```
Use this command to follow the logs in real-time and troubleshoot any errors.


## 7. Using DjangoQ
- Scheduling Tasks: Use the schedule functions in DjangoQ to create recurring tasks, for example:

```python
from django_q.tasks import schedule, Schedule

schedule(
    'inventory.tasks.my_new_scheduled_task',
    schedule_type=Schedule.DAILY,  # or HOURLY, MINUTES, etc.
    repeats=-1,  # infinite repeats
)
```

- Async Tasks: Use the async function to run tasks asynchronously, for example:

```python
from django_q.tasks import async_task
...
async_task('inventory.tasks.recreate_batches')
```

## 8. Summary
Using DjangoQ allows you to:

- Schedule periodic tasks.
- Offload long-running or time-consuming operations from the main Django process.
- Keep your code neatly organized and your application responsive.
Once you have it configured and running as a service, you can trust that tasks will run reliably in the background. If anything goes wrong, consult the logs and restart the service as needed.
