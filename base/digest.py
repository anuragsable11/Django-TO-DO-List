"""The morning email: overdue and due-today tasks, sent once a day to people who turned it on.

Vercel Cron calls /cron/digest/ once a day (see vercel.json); `python manage.py send_digests` does the
same by hand. Each user's "today" is their own, from the time zone saved on their profile, and
digest_last_sent stops a second run on the same day from sending twice.
"""
import datetime
import logging
import zoneinfo

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.utils import timezone

from .dates import describe_due
from .models import Profile, Task

log = logging.getLogger(__name__)


def user_today(profile, now=None):
    try:
        zone = zoneinfo.ZoneInfo(profile.timezone)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        zone = datetime.timezone.utc
    return (now or timezone.now()).astimezone(zone).date()


def build(user, today, site_url):
    """The email for one user, or None when nothing is overdue or due today."""
    open_tasks = Task.objects.filter(user=user, status=Task.Status.OPEN, due_date__lte=today).select_related('task_list')
    overdue = [t for t in open_tasks.order_by('due_date', '-priority', 'position') if t.due_date < today]
    due_today = [t for t in open_tasks.order_by('-priority', 'position') if t.due_date == today]
    if not overdue and not due_today:
        return None
    for task in overdue:
        task.due_label = describe_due(task.due_date, today)
    parts = []
    if due_today:
        parts.append(f'{len(due_today)} due today')
    if overdue:
        parts.append(f'{len(overdue)} overdue')
    context = {
        'user': user, 'today': today, 'overdue': overdue, 'due_today': due_today,
        'summary': ' and '.join(parts), 'site_url': site_url,
    }
    subject = f'Your day: {context["summary"]}'
    text = render_to_string('email/digest.txt', context)
    html = render_to_string('email/digest.html', context)
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html, 'text/html')
    return message


def send_all(site_url, now=None):
    """Send today's email to everyone who wants one and hasn't had it yet. Returns counts."""
    stats = {'sent': 0, 'nothing_due': 0, 'already_sent': 0, 'failed': 0}
    profiles = (Profile.objects.filter(digest_enabled=True, user__is_active=True)
                .exclude(user__email='').select_related('user'))
    connection = get_connection(fail_silently=False)
    for profile in profiles:
        today = user_today(profile, now)
        if profile.digest_last_sent == today:
            stats['already_sent'] += 1
            continue
        message = build(profile.user, today, site_url)
        if message is None:
            stats['nothing_due'] += 1
            continue
        message.connection = connection
        try:
            message.send()
        except Exception:  # one bad address must not stop everyone else's email
            log.exception('Morning email to user %s failed', profile.user_id)
            stats['failed'] += 1
            continue
        profile.digest_last_sent = today
        profile.save(update_fields=['digest_last_sent'])
        stats['sent'] += 1
    return stats


def send_test(user, site_url):
    """Settings' "Send a test email": today's real digest, or a short note if nothing is due."""
    profile, _ = Profile.objects.get_or_create(user=user)
    today = user_today(profile)
    message = build(user, today, site_url)
    if message is None:
        context = {'user': user, 'site_url': site_url}
        message = EmailMultiAlternatives(
            'Your morning email is set up',
            render_to_string('email/test.txt', context),
            settings.DEFAULT_FROM_EMAIL, [user.email],
        )
    message.send()
