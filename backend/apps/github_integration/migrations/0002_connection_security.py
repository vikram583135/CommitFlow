from django.db import migrations, models


def quarantine_unverified_installations(apps, schema_editor):
    Connection = apps.get_model('github_integration', 'GitHubConnection')
    Repository = apps.get_model('github_integration', 'Repository')
    Automation = apps.get_model('automations', 'Automation')
    connections = Connection.objects.exclude(installation_id='oauth_user_account')
    connections.update(is_active=False, encrypted_access_token='')
    Repository.objects.filter(connection__is_active=False).update(is_active=False)
    Automation.objects.filter(repository__connection__is_active=False).update(enabled=False, next_run_at=None)


class Migration(migrations.Migration):
    dependencies = [('github_integration', '0001_initial'), ('automations', '0001_initial')]
    operations = [
        migrations.AddField('githubconnection', 'is_active', models.BooleanField(default=True)),
        migrations.RunPython(quarantine_unverified_installations, migrations.RunPython.noop),
        migrations.CreateModel(name='WebhookDelivery', fields=[
            ('body_hash', models.CharField(max_length=64, primary_key=True, serialize=False)),
            ('received_at', models.DateTimeField(auto_now_add=True)),
        ]),
    ]
