from django.db import migrations, models
import django.db.models.deletion


def migrate_identities(apps, schema_editor):
    User = apps.get_model('authentication', 'User')
    Identity = apps.get_model('authentication', 'SocialIdentity')
    for user in User.objects.exclude(provider_id='').filter(auth_provider__in=['github', 'google']).iterator():
        if User.objects.filter(auth_provider=user.auth_provider, provider_id=user.provider_id).count() == 1:
            Identity.objects.create(user=user, provider=user.auth_provider, subject=user.provider_id)


class Migration(migrations.Migration):
    dependencies = [('authentication', '0002_user_auth_provider_user_avatar_url_user_provider_id')]
    operations = [
        migrations.AddField('user', 'email_verified', models.BooleanField(default=False)),
        migrations.CreateModel(name='OAuthAttempt', fields=[
            ('state_hash', models.CharField(max_length=64, primary_key=True, serialize=False)),
            ('provider', models.CharField(max_length=20)),
            ('redirect_uri', models.URLField()),
            ('code_challenge', models.CharField(max_length=43)),
            ('expires_at', models.DateTimeField()),
            ('consumed', models.BooleanField(default=False)),
            ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='authentication.user')),
        ]),
        migrations.CreateModel(name='SocialIdentity', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('provider', models.CharField(max_length=20)),
            ('subject', models.CharField(max_length=255)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_identities', to='authentication.user')),
        ], options={'constraints': [
            models.UniqueConstraint(fields=['provider', 'subject'], name='unique_social_subject'),
            models.UniqueConstraint(fields=['user', 'provider'], name='unique_user_provider'),
        ]}),
        migrations.RunPython(migrate_identities, migrations.RunPython.noop),
    ]
