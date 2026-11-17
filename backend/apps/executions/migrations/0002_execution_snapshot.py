from django.db import migrations, models
from django.utils import timezone


def deduplicate_files(apps, schema_editor):
    File = apps.get_model('executions', 'GeneratedFile')
    seen = set()
    for file in File.objects.all().iterator():
        key = (file.execution_id, file.file_path)
        if key in seen:
            file.delete()
        seen.add(key)


def invalidate_legacy_proposals(apps, schema_editor):
    Execution = apps.get_model('executions', 'Execution')
    Execution.objects.filter(status='AWAITING_APPROVAL').update(status='REJECTED', completed_at=timezone.now(),
        error_message='Legacy proposal has no immutable snapshot. Generate a new proposal.')
    Execution.objects.filter(status='RUNNING').update(status='FAILED', completed_at=timezone.now(),
        error_message='Execution interrupted by upgrade. Retry or generate again.')
    Execution.objects.filter(published_change__commit_sha__startswith='simulated-').update(status='REJECTED',
        error_message='Legacy simulated publication; no GitHub publication was confirmed.')


class Migration(migrations.Migration):
    dependencies = [('executions', '0001_initial')]
    operations = [
        migrations.AddField('execution', 'snapshot', models.JSONField(blank=True, default=dict)),
        migrations.AddField('execution', 'proposal_hash', models.CharField(blank=True, max_length=64)),
        migrations.AddField('execution', 'approved_at', models.DateTimeField(blank=True, null=True)),
        migrations.AddField('execution', 'heartbeat_at', models.DateTimeField(blank=True, null=True)),
        migrations.AlterField('execution', 'status', models.CharField(db_index=True, default='PENDING', max_length=50,
            choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('PUBLISHING', 'Publishing'),
                     ('CANCELLED', 'Cancelled'), ('AWAITING_APPROVAL', 'Awaiting User Approval'),
                     ('SUCCESS', 'Success'), ('FAILED', 'Failed'), ('REJECTED', 'Rejected by Validation')])),
        migrations.RunPython(deduplicate_files, migrations.RunPython.noop),
        migrations.RunPython(invalidate_legacy_proposals, migrations.RunPython.noop),
        migrations.AddConstraint('generatedfile', models.UniqueConstraint(fields=['execution', 'file_path'], name='unique_execution_file')),
    ]
