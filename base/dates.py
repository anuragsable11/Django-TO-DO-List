"""Small date helpers shared by quick add, repeating tasks and the views."""
import calendar
import datetime

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def add_months(day, months):
    """Same day of the month, `months` later; clamped to the month's last day (31 Jan + 1 = 28/29 Feb)."""
    index = day.month - 1 + months
    year, month = day.year + index // 12, index % 12 + 1
    return day.replace(year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1]))


def upcoming_weekday(today, weekday, include_today=False):
    """The next date falling on `weekday` (0 = Monday). Today only counts when include_today is set."""
    ahead = (weekday - today.weekday()) % 7
    if ahead == 0 and not include_today:
        ahead = 7
    return today + datetime.timedelta(days=ahead)


def next_week_start(today):
    return today + datetime.timedelta(days=7 - today.weekday())


def next_occurrence(repeat, due, today):
    """When a repeating task comes back after being checked off: the first date after today
    on its schedule, counted from its due date (or from today if it had none)."""
    base = due or today
    if repeat == 'monthly':
        months = 1
        while add_months(base, months) <= today:
            months += 1
        return add_months(base, months)
    step = datetime.timedelta(days=7 if repeat == 'weekly' else 1)
    nxt = base + step
    while nxt <= today or (repeat == 'weekdays' and nxt.weekday() >= 5):
        nxt += step
    return nxt


def describe_due(due, today):
    """Short human label: Today, Tomorrow, Yesterday, a weekday within the week, else '12 Oct'."""
    if due is None:
        return ''
    delta = (due - today).days
    if delta == 0:
        return 'Today'
    if delta == 1:
        return 'Tomorrow'
    if delta == -1:
        return 'Yesterday'
    if 1 < delta < 7:
        return due.strftime('%A')
    label = f'{due.day} {due.strftime("%b")}'
    return label if due.year == today.year else f'{label} {due.year}'
