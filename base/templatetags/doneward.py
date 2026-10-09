import re

from django import template
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe

from base.dates import describe_due

register = template.Library()


@register.inclusion_tag('partials/due_chip.html', takes_context=True)
def due_chip(context, task):
    """A small date badge: red when overdue, orange for today, quiet otherwise."""
    today = context.get('today') or timezone.localdate()
    due = task.due_date
    if due is None or task.status != 'open':
        return {'show': False}
    days = (due - today).days
    repeat = task.get_repeat_display() if task.repeat else ''
    # Under a date heading (Upcoming, or Today's "Today" group) the date would only repeat it:
    # show just the repeat, if there is one
    if context.get('view') == 'upcoming' or (context.get('view') == 'today' and days == 0):
        if not repeat:
            return {'show': False}
        return {'show': True, 'tone': 'later', 'label': repeat, 'iso': due.isoformat(),
                'long': due.strftime('%A, %d %B %Y').replace(' 0', ' '), 'repeat': repeat, 'repeat_only': True}
    if days < 0:
        tone = 'overdue'
    elif days == 0:
        tone = 'today'
    elif days <= 2:
        tone = 'soon'
    else:
        tone = 'later'
    return {
        'show': True,
        'tone': tone,
        'label': describe_due(due, today),
        'iso': due.isoformat(),
        'long': due.strftime('%A, %d %B %Y').replace(' 0', ' '),
        'repeat': repeat,
    }


@register.filter
def highlight(text, query):
    """Wrap each case-insensitive match of `query` in <mark>, escaping everything else."""
    text = str(text or '')
    query = (query or '').strip()
    if not query:
        return escape(text)
    pieces = re.split(f'({re.escape(query)})', text, flags=re.IGNORECASE)
    out = [f'<mark>{escape(p)}</mark>' if i % 2 else escape(p) for i, p in enumerate(pieces)]
    return mark_safe(''.join(out))
