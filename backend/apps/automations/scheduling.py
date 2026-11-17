"""Database-backed schedules. Missing DST times are skipped; repeated wall slots deduplicate."""
import json
from datetime import datetime, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from celery.schedules import crontab
from django.utils import timezone


def parse_schedule(expression, zone):
    if not isinstance(expression, str) or len(expression.split()) != 5:
        raise ValueError('Use a five-field cron expression.')
    try:
        ZoneInfo(zone)
        minute, hour, day, month, weekday = expression.split()
        crontab(minute=minute, hour=hour, day_of_month=day, month_of_year=month, day_of_week=weekday)
    except (ValueError, KeyError, ZoneInfoNotFoundError) as exc:
        raise ValueError('Invalid cron expression or IANA timezone.') from exc
    return minute, hour, day, month, weekday


def next_scheduled_at(expression, zone, now=None):
    minute, hour, day, month, weekday = parse_schedule(expression, zone)
    rule = crontab(minute=minute, hour=hour, day_of_month=day, month_of_year=month, day_of_week=weekday)
    tz = ZoneInfo(zone)
    now = (now or timezone.now()).astimezone(datetime_timezone.utc)
    first_day = now.astimezone(tz).date()
    for offset in range(366 * 8):
        date = first_day + timedelta(days=offset)
        if date.month not in rule.month_of_year or date.day not in rule.day_of_month or (date.isoweekday() % 7) not in rule.day_of_week:
            continue
        candidates = set()
        for hour_value in sorted(rule.hour):
            for minute_value in sorted(rule.minute):
                wall_time = datetime(date.year, date.month, date.day, hour_value, minute_value)
                for fold in (0, 1):
                    candidate = wall_time.replace(tzinfo=tz, fold=fold).astimezone(datetime_timezone.utc)
                    # A nonexistent DST wall time does not roundtrip.
                    if candidate > now and candidate.astimezone(tz).replace(tzinfo=None) == wall_time:
                        candidates.add(candidate)
        if candidates:
            return min(candidates)
    raise ValueError('Schedule has no valid occurrence within the next eight years.')


def sync_schedule(automation):
    from django_celery_beat.models import CrontabSchedule, PeriodicTask
    minute, hour, day, month, weekday = parse_schedule(automation.cron_expression, automation.timezone)
    schedule, _ = CrontabSchedule.objects.get_or_create(minute=minute, hour=hour, day_of_month=day,
        month_of_year=month, day_of_week=weekday, timezone=automation.timezone)
    task, created = PeriodicTask.objects.get_or_create(name=f'automation:{automation.pk}', defaults={
        'task': 'apps.executions.tasks.dispatch_scheduled_automation',
        'args': json.dumps([str(automation.pk)]), 'crontab': schedule, 'enabled': automation.enabled,
    })
    changed = not created and task.crontab_id != schedule.pk
    task.crontab = schedule
    task.enabled = automation.enabled
    if changed:
        task.last_run_at = None
    task.save()
    next_run = next_scheduled_at(automation.cron_expression, automation.timezone) if automation.enabled else None
    automation.__class__.objects.filter(pk=automation.pk).update(next_run_at=next_run)
    automation.next_run_at = next_run


def register_schedule_signals():
    from django.db.models.signals import post_save, post_delete
    from django.dispatch import receiver
    from django_celery_beat.models import PeriodicTask
    from .models import Automation

    @receiver(post_save, sender=Automation, weak=False, dispatch_uid='commitflow.schedule.save')
    def saved(sender, instance, raw=False, update_fields=None, **kwargs):
        if not raw and (update_fields is None or set(update_fields) & {'cron_expression', 'timezone', 'enabled'}):
            sync_schedule(instance)

    @receiver(post_delete, sender=Automation, weak=False, dispatch_uid='commitflow.schedule.delete')
    def deleted(sender, instance, **kwargs):
        PeriodicTask.objects.filter(name=f'automation:{instance.pk}').delete()
