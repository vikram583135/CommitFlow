from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from apps.automations.models import Automation
from apps.automations.scheduling import sync_schedule


class Command(BaseCommand):
    help = 'Register existing automations and interrupted-execution recovery with Celery Beat.'

    def handle(self, **options):
        for automation in Automation.objects.all().iterator():
            try:
                sync_schedule(automation)
            except ValueError:
                Automation.objects.filter(pk=automation.pk).update(enabled=False, next_run_at=None)
                PeriodicTask.objects.filter(name=f'automation:{automation.pk}').update(enabled=False)
                self.stderr.write(f'Disabled automation {automation.pk}: invalid schedule.')
        interval, _ = IntervalSchedule.objects.get_or_create(every=5, period=IntervalSchedule.MINUTES)
        PeriodicTask.objects.update_or_create(name='recover-interrupted-executions', defaults={
            'task': 'apps.executions.tasks.recover_interrupted_executions', 'interval': interval, 'enabled': True})
        self.stdout.write('Schedules reconciled.')
