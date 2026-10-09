"""Quick add: read a due date, a repeat, a list and a priority out of a one-line task.

    "Pay rent friday #home !high"   -> "Pay rent", due Friday, list Home, high priority
    "Water plants every monday"     -> repeats weekly, first due on the coming Monday
    "Send report by 12 oct"         -> due 12 October

#list and !priority may sit anywhere. Dates and repeats are only read at the end of the line,
so a title such as "Plan Friday party" keeps its words. Nothing is removed if the title would
end up empty: a task called just "Tomorrow" stays "Tomorrow".
"""
import datetime
import re
from dataclasses import dataclass

from .dates import WEEKDAYS, add_months, next_week_start, upcoming_weekday

PRIORITY_WORDS = {
    'high': 3, 'h': 3, '1': 3, 'urgent': 3,
    'normal': 2, 'medium': 2, 'n': 2, 'm': 2, '2': 2,
    'low': 1, 'l': 1, '3': 1,
}

MONTHS = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
    'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9, 'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

DAY_ABBR = {'mon': 0, 'tue': 1, 'tues': 1, 'wed': 2, 'thu': 3, 'thur': 3, 'thurs': 3, 'fri': 4, 'sat': 5, 'sun': 6}
NUMBER_WORDS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'ten': 10}


def _alternatives(words):
    return '|'.join(sorted(words, key=len, reverse=True))  # longest first, so "sept" beats "sep"


WEEKDAY = _alternatives(WEEKDAYS)
ABBR = _alternatives(DAY_ABBR)
MONTH = _alternatives(MONTHS)
NUMBER = r'\d{1,3}|' + _alternatives(NUMBER_WORDS)

LEAD = r'(?:^|\s)(?:(?:on|by|due|for)\s+)?'   # "due friday", "by 12 oct"
TAIL = r'\s*[.,]?\s*$'

# a list name starts with a letter, so "Fix bug #123" keeps its issue number
LIST_TOKEN = re.compile(r'(?:^|\s)#([^\W\d_][\w-]{0,39})(?=\s|$)')
PRIORITY_TOKEN = re.compile(r'(?:^|\s)(?:!(' + _alternatives(PRIORITY_WORDS) + r')|(!!!))(?=\s|$)', re.IGNORECASE)


@dataclass
class QuickAdd:
    title: str
    due_date: datetime.date | None = None
    repeat: str = ''
    priority: int | None = None
    list_name: str = ''


def _weekday(word):
    word = word.lower()
    return WEEKDAYS.index(word) if word in WEEKDAYS else DAY_ABBR[word]


def _calendar_date(today, month_word, day, year):
    date = datetime.date(int(year) if year else today.year, MONTHS[month_word.lower()], int(day))
    if not year and date < today:
        date = date.replace(year=today.year + 1)  # "3 jan" in October means next January
    return date


def _offset(today, amount, unit):
    n = int(amount) if amount.isdigit() else NUMBER_WORDS[amount.lower()]
    unit = unit.lower()
    if unit.startswith('month'):
        return add_months(today, n)
    return today + datetime.timedelta(days=n * (7 if unit.startswith('week') else 1))


def _date_rules(today):
    """(pattern, builder) pairs, tried in order against the end of the text."""
    day = datetime.timedelta(days=1)
    return [
        # day abbreviations ("fri") only after on/by/due/this, so "Enjoy the sun" stays a title
        (r'(?:^|\s)(?:on|by|due|this)\s+(' + ABBR + ')', lambda m: upcoming_weekday(today, _weekday(m.group(1)))),
        (LEAD + r'(?:today|tonight)', lambda m: today),
        (LEAD + r'(?:the )?day after tomorrow', lambda m: today + 2 * day),
        (LEAD + r'(?:tomorrow|tomorow|tmrw|tmr)', lambda m: today + day),
        (LEAD + r'next week', lambda m: next_week_start(today)),
        (LEAD + r'next weekend', lambda m: next_week_start(today) + 5 * day),
        (LEAD + r'(?:this )?weekend', lambda m: today if today.weekday() >= 5 else upcoming_weekday(today, 5)),
        (LEAD + r'next month', lambda m: add_months(today.replace(day=1), 1)),
        (LEAD + r'in (' + NUMBER + r') (days?|weeks?|months?)', lambda m: _offset(today, m.group(1), m.group(2))),
        (LEAD + r'next (' + WEEKDAY + '|' + ABBR + ')', lambda m: next_week_start(today) + _weekday(m.group(1)) * day),
        (LEAD + r'(?:this )?(' + WEEKDAY + ')', lambda m: upcoming_weekday(today, _weekday(m.group(1)))),
        (LEAD + r'(\d{4})-(\d{2})-(\d{2})', lambda m: datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (LEAD + r'(' + MONTH + r')\.? (\d{1,2})(?:st|nd|rd|th)?(?:,? (\d{4}))?',
         lambda m: _calendar_date(today, m.group(1), m.group(2), m.group(3))),
        (LEAD + r'(?:the )?(\d{1,2})(?:st|nd|rd|th)? (?:of )?(' + MONTH + r')\.?(?:,? (\d{4}))?',
         lambda m: _calendar_date(today, m.group(2), m.group(1), m.group(3))),
    ]


def _repeat_rules(today):
    weekday_start = today if today.weekday() < 5 else next_week_start(today)
    return [
        (r'(?:^|\s)(?:every\s?day|daily)', lambda m: ('daily', today)),
        (r'(?:^|\s)(?:every (?:weekday|workday)|weekdays|on weekdays)', lambda m: ('weekdays', weekday_start)),
        (r'(?:^|\s)(?:every week|weekly)', lambda m: ('weekly', today)),
        (r'(?:^|\s)(?:every month|monthly)', lambda m: ('monthly', today)),
        (r'(?:^|\s)every (' + WEEKDAY + '|' + ABBR + ')',
         lambda m: ('weekly', upcoming_weekday(today, _weekday(m.group(1)), include_today=True))),
    ]


def _match_tail(text, rules):
    """First rule matching the end of `text` that leaves a title behind: (value, remaining text)."""
    for pattern, build in rules:
        m = re.search(pattern + TAIL, text, re.IGNORECASE)
        if not m:
            continue
        rest = text[:m.start()].rstrip(' ,.-')
        if not rest:
            return None
        try:
            return build(m), rest
        except (ValueError, OverflowError):  # 31 feb and friends: leave the text alone
            return None
    return None


def _remove(text, m):
    return ' '.join((text[:m.start()] + ' ' + text[m.end():]).split())


def clean_list_name(raw):
    name = ' '.join(raw.replace('_', ' ').replace('-', ' ').split())[:40]
    return name[:1].upper() + name[1:] if name.islower() else name


def parse(text, today):
    """Split a quick-add line into a clean title and the details it mentions."""
    text = ' '.join((text or '').split())
    result = QuickAdd(title=text)

    m = LIST_TOKEN.search(text)
    if m and _remove(text, m):
        result.list_name = clean_list_name(m.group(1))
        text = _remove(text, m)

    m = PRIORITY_TOKEN.search(text)
    if m and _remove(text, m):
        result.priority = 3 if m.group(2) else PRIORITY_WORDS[m.group(1).lower()]
        text = _remove(text, m)

    # A repeat and a date may both trail the title, in either order: "Standup tomorrow daily".
    # An explicit date wins over the first date a repeat implies.
    explicit_due = repeat_due = None
    for _ in range(2):
        if not result.repeat:
            found = _match_tail(text, _repeat_rules(today))
            if found:
                (result.repeat, repeat_due), text = found
                continue
        if explicit_due is None:
            found = _match_tail(text, _date_rules(today))
            if found:
                explicit_due, text = found
                continue
        break

    result.title = text
    result.due_date = explicit_due or repeat_due
    return result
