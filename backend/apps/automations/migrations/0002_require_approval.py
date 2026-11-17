from django.db import migrations, models


def enable_approval(apps, schema_editor):
    apps.get_model('automations', 'Automation').objects.update(require_approval=True)


class Migration(migrations.Migration):
    dependencies = [('automations', '0001_initial')]
    operations = [
        migrations.AlterField('automation', 'require_approval', models.BooleanField(default=True)),
        migrations.RunPython(enable_approval, migrations.RunPython.noop),
    ]
