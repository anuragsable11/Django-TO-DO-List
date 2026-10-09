import datetime
import json
import secrets
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import Truncator
from django.views.decorators.http import require_GET, require_POST

from . import digest, services
from .context_processors import TaskCounts
from .dates import describe_due
from .forms import ListForm, SettingsForm, SignUpForm, TaskForm
from .middleware import valid_zone
from .models import Profile, Task, TaskList
from .quickadd import parse

OPEN, DONE, TRASHED = Task.Status.OPEN, Task.Status.DONE, Task.Status.TRASHED


# ---------- Helpers ----------

def short(title, length=48):
    return Truncator(title).chars(length)


def safe_next(request):
    """The `next` address from the form or query string, if it points back into this site."""
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return ''


def back(request, fallback):
    """Redirect to a safe `next`, else to `fallback` (a URL name or path)."""
    return redirect(safe_next(request) or fallback)


def remember_undo(request, items, text):
    """Keep the batch so the toast's Undo button can put it back."""
    if not items:
        return
    request.session['undo'] = {'token': secrets.token_urlsafe(9), 'items': items, 'at': time.time()}
    messages.success(request, text, extra_tags='undo')


def own(request, pk, *statuses):
    return get_object_or_404(Task, pk=pk, user=request.user, status__in=statuses)


def open_tasks(user):
    return Task.objects.filter(user=user, status=OPEN).select_related('task_list')


SCOPES = ('all', 'today', 'upcoming', 'overdue')


def scoped(user, scope, today):
    """Open tasks for a view: all, today (incl. overdue), upcoming, overdue, or one list ("list:<id>")."""
    tasks = open_tasks(user)
    if scope == 'today':
        return tasks.filter(due_date__lte=today)
    if scope == 'upcoming':
        return tasks.filter(due_date__gt=today)
    if scope == 'overdue':
        return tasks.filter(due_date__lt=today)
    if scope.startswith('list:') and scope[5:].isdigit():
        return tasks.filter(task_list_id=int(scope[5:]))
    return tasks


def plural(n, word, many=None):
    return f'{n} {word if n == 1 else many or word + "s"}'


def due_phrase(due, today):
    """'today', 'tomorrow', 'Friday', '12 Oct': reads naturally after "due"."""
    label = describe_due(due, today)
    return label.lower() if label in ('Today', 'Tomorrow', 'Yesterday') else label


def done_day_title(day, today):
    """Heading for a day in Completed: Today, Yesterday, a weekday this past week, else '12 Oct'."""
    days = (today - day).days
    if days == 0:
        return 'Today'
    if days == 1:
        return 'Yesterday'
    if 1 < days < 7:
        return f'{day:%A}'
    return f'{day.day} {day:%b}' + ('' if day.year == today.year else f' {day.year}')


# ---------- Public pages ----------

def landing(request):
    context = {'mascot': {'user': ''}}
    if request.user.is_authenticated:
        counts = TaskCounts(request.user)
        today = timezone.localdate()
        # What Stripes reminds the user about: overdue first, then due today, then the soonest due
        # (undated last), the more important first, then in the user's own order
        candidates = list(open_tasks(request.user).order_by('position', 'id')[:200])

        def urgency(task):
            due = task.due_date
            bucket = 0 if due and due < today else 1 if due == today else 2
            return (bucket, due or datetime.date.max, -task.priority, task.position)

        candidates.sort(key=urgency)
        last_done = Task.objects.filter(user=request.user, status=DONE).order_by('-completed_at', '-id').first()
        context = {
            'open_count': counts.open,
            'done_count': counts.done,
            'trash_count': counts.trash,
            'mascot': {
                'user': request.user.username,
                'open': counts.open,
                'done': counts.done,
                'trash': counts.trash,
                'overdue': counts.overdue,
                'due_today': counts.today - counts.overdue,
                'last_done': last_done.title if last_done else '',
                'tasks': [
                    {
                        'title': t.title,
                        'notes': Truncator(t.notes).chars(80),
                        'when': 'overdue' if t.due_date and t.due_date < today else 'today' if t.due_date == today else '',
                        'due': describe_due(t.due_date, today),
                        'done_url': reverse('hcomplete', args=[t.id]),
                    }
                    for t in candidates[:5]
                ],
            },
        }
    return render(request, 'landing.html', context)


def about(request):
    return render(request, 'about.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'Welcome aboard, {user.username}! Add your first task.')
        return redirect('home')
    return render(request, 'registration/register.html', {'form': form})


# ---------- Task views ----------

def render_tasks(request, *, view, title, kicker, groups, today, scope=None, draggable=False,
                 quick_add=None, empty=None, extra=None):
    context = {
        'view': view,
        'heading': title,
        'kicker': kicker,
        'groups': [g for g in groups if g['tasks']],
        'today': today,
        'scope': scope,
        'draggable': draggable,
        'quick_add': quick_add,
        'empty': empty or {},
        'count': sum(len(g['tasks']) for g in groups),
        'next': request.get_full_path(),
    }
    context.update(extra or {})
    return render(request, 'tasks.html', context)


@login_required
def home(request):
    today = timezone.localdate()
    sort = request.GET.get('sort', '')
    tasks = open_tasks(request.user)
    if sort == 'due':
        tasks = tasks.order_by(F('due_date').asc(nulls_last=True), '-priority', 'position')
    elif sort == 'priority':
        tasks = tasks.order_by('-priority', F('due_date').asc(nulls_last=True), 'position')
    else:
        sort = ''
    tasks = list(tasks)
    return render_tasks(
        request, view='home', title='Tasks', today=today, scope='all',
        kicker=f'Your list · {len(tasks)} open' if tasks else 'Your list · all clear',
        groups=[{'tasks': tasks}], draggable=not sort and len(tasks) > 1,
        quick_add={},
        empty={'title': 'Nothing on your list.', 'accent': 'Bliss.', 'text': 'Write a task above and press Enter. Stripes will keep an eye on it.'},
        extra={'sort': sort, 'sorts': [('', 'My order'), ('due', 'Due date'), ('priority', 'Priority')]},
    )


@login_required
def today_view(request):
    today = timezone.localdate()
    tasks = scoped(request.user, 'today', today).order_by('due_date', '-priority', 'position')
    overdue = [t for t in tasks if t.due_date < today]
    due_today = sorted((t for t in tasks if t.due_date == today), key=lambda t: (-t.priority, t.position))
    return render_tasks(
        request, view='today', title='Today', today=today, scope='today',
        kicker=f'{today:%A} · {plural(len(due_today), "task")} due' + (f', {len(overdue)} overdue' if overdue else ''),
        groups=[
            {'title': 'Overdue', 'tone': 'overdue', 'tasks': overdue},
            {'title': 'Today', 'tasks': due_today},
        ],
        quick_add={'default_due': 'today', 'placeholder': 'Add a task for today…'},
        empty={'title': 'Nothing due today.', 'accent': 'Breathe.', 'text': 'Tasks with today’s date land here, along with anything overdue.'},
    )


@login_required
def upcoming(request):
    today = timezone.localdate()
    tasks = scoped(request.user, 'upcoming', today).order_by('due_date', '-priority', 'position')
    groups, current = [], None
    for task in tasks:
        if current is None or current['date'] != task.due_date:
            due = task.due_date
            title = describe_due(due, today)
            # "Tomorrow · Sat 10 Oct", "Monday · Mon 12 Oct", "21 Oct · Wednesday"
            subtitle = f'{due:%A}' if title[0].isdigit() else f'{due:%a} {due.day} {due:%b}'
            current = {'date': due, 'title': title, 'subtitle': subtitle, 'tasks': []}
            groups.append(current)
        current['tasks'].append(task)
    count = sum(len(g['tasks']) for g in groups)
    return render_tasks(
        request, view='upcoming', title='Upcoming', today=today, scope='upcoming',
        kicker=f'Coming up · {plural(count, "task")}' if count else 'Coming up · nothing planned',
        groups=groups,
        quick_add={'default_due': 'tomorrow', 'placeholder': 'Plan a task… try “Call Sam friday”'},
        empty={'title': 'Nothing planned yet.', 'accent': 'Open road.', 'text': 'Give a task a future date and it shows up here, grouped by day.'},
    )


@login_required
def overdue(request):
    today = timezone.localdate()
    tasks = list(scoped(request.user, 'overdue', today).order_by('due_date', '-priority', 'position'))
    return render_tasks(
        request, view='overdue', title='Overdue', today=today, scope='overdue',
        kicker=f'Slipped past · {plural(len(tasks), "task")}' if tasks else 'Slipped past · none',
        groups=[{'tasks': tasks}],
        empty={'title': 'Nothing overdue.', 'accent': 'On time.', 'text': 'Tasks whose date has passed wait here until you finish them or pick a new day.'},
    )


@login_required
def list_detail(request, pk):
    task_list = get_object_or_404(TaskList, pk=pk, user=request.user)
    today = timezone.localdate()
    tasks = list(scoped(request.user, f'list:{pk}', today))
    return render_tasks(
        request, view='list', title=task_list.name, today=today, scope=f'list:{pk}',
        kicker=f'List · {len(tasks)} open' if tasks else 'List · all clear',
        groups=[{'tasks': tasks}], draggable=len(tasks) > 1,
        quick_add={'default_list': task_list.pk, 'placeholder': f'Add to {task_list.name}…'},
        empty={'title': f'Nothing in {task_list.name}.', 'accent': 'Yet.', 'text': f'Add a task here, or type #{task_list.name.replace(" ", "-").lower()} at the end of any task.'},
        extra={'task_list': task_list},
    )


@login_required
def complete(request):
    today = timezone.localdate()
    tasks = Task.objects.filter(user=request.user, status=DONE).select_related('task_list').order_by('-completed_at', '-id')
    groups, current = [], None
    for task in tasks:
        day = timezone.localtime(task.completed_at).date() if task.completed_at else None
        if current is None or current['date'] != day:
            current = {'date': day, 'title': done_day_title(day, today) if day else 'Earlier',
                       'subtitle': f'{day:%a} {day.day} {day:%b}' if day and (today - day).days < 7 else '', 'tasks': []}
            groups.append(current)
        current['tasks'].append(task)
    count = sum(len(g['tasks']) for g in groups)
    return render_tasks(
        request, view='complete', title='Completed', today=today,
        kicker=f'Done · {plural(count, "task")}', groups=groups,
        empty={'title': 'No wins yet.', 'accent': 'Soon.', 'text': 'Tasks you check off collect here, a quiet record of everything you’ve done.', 'link': True},
    )


@login_required
def trash(request):
    today = timezone.localdate()
    tasks = list(Task.objects.filter(user=request.user, status=TRASHED).select_related('task_list').order_by('-trashed_at', '-id'))
    return render_tasks(
        request, view='trash', title='Trash', today=today,
        kicker=f'Trash · {plural(len(tasks), "item")}', groups=[{'tasks': tasks}],
        empty={'title': 'Trash is empty.', 'accent': 'Tidy.', 'text': 'Deleted tasks wait here, so you can bring them back or remove them for good.', 'link': True},
    )


@login_required
def search(request):
    query = ' '.join(request.GET.get('q', '').split())[:100]
    today = timezone.localdate()
    groups = []
    if query:
        matches = (Task.objects.filter(user=request.user).filter(Q(title__icontains=query) | Q(notes__icontains=query))
                   .select_related('task_list').order_by('position', '-completed_at', '-id'))
        for status, title in ((OPEN, 'Open'), (DONE, 'Completed'), (TRASHED, 'In the trash')):
            groups.append({'title': title, 'status': status, 'tasks': [t for t in matches if t.status == status][:50]})
    count = sum(len(g['tasks']) for g in groups)
    return render_tasks(
        request, view='search', title='Search', today=today,
        kicker=(f'{plural(count, "match", "matches")} for “{short(query, 30)}”' if query else 'Find any task'),
        groups=groups,
        empty={'title': 'No matches.' if query else 'Look for anything.',
               'text': 'Try a shorter word, or check the spelling.' if query else 'Search titles and notes across your list, Completed and Trash.'},
        extra={'query': query},
    )


# ---------- Adding and editing ----------

@login_required
def add(request):
    if request.method == 'POST' and request.POST.get('quick'):
        return quick_add(request)
    initial = {}
    list_id = request.GET.get('list', '')
    if list_id.isdigit():
        initial['task_list'] = TaskList.objects.filter(user=request.user, pk=int(list_id)).first()
    if request.GET.get('due') == 'today':
        initial['due_date'] = timezone.localdate()
    form = TaskForm(request.POST or None, user=request.user, initial=initial)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.user = request.user
        task.position = services.next_position(request.user)
        task.save()
        messages.success(request, f'Added “{short(task.title)}”.')
        return back(request, 'home')
    return render(request, 'add.html', {'form': form, 'next': safe_next(request)})


def quick_add(request):
    today = timezone.localdate()
    parsed = parse(request.POST.get('title', ''), today)
    title = parsed.title[:200]
    if not title:
        messages.error(request, 'Write a title for the task first.')
        return back(request, 'home')

    due = parsed.due_date
    default_due = request.POST.get('default_due')
    if due is None and default_due == 'today':
        due = today
    elif due is None and default_due == 'tomorrow':
        due = today + datetime.timedelta(days=1)

    task_list, new_list = None, False
    if parsed.list_name:
        task_list, new_list = services.find_or_create_list(request.user, parsed.list_name)
    elif request.POST.get('default_list', '').isdigit():
        task_list = TaskList.objects.filter(user=request.user, pk=int(request.POST['default_list'])).first()

    task = Task.objects.create(
        user=request.user, title=title, notes=request.POST.get('notes', '').strip()[:2000],
        due_date=due, repeat=parsed.repeat, priority=parsed.priority or Task.Priority.NORMAL,
        task_list=task_list, position=services.next_position(request.user),
    )

    # Say what was understood, so a date or list read from the title is never a surprise
    understood = []
    if parsed.due_date:
        understood.append(f'due {due_phrase(due, today)}')
    if parsed.repeat:
        understood.append(task.get_repeat_display().lower())
    if parsed.list_name:
        understood.append(f'in {task_list.name}' + (' (new list)' if new_list else ''))
    if parsed.priority and parsed.priority != Task.Priority.NORMAL:
        understood.append(f'{task.get_priority_display().lower()} priority')
    if understood:
        messages.success(request, f'Added “{short(title)}”, ' + ', '.join(understood) + '.')
    return back(request, 'home')


@login_required
def update(request, pk):
    task = own(request, pk, OPEN, DONE)
    form = TaskForm(request.POST or None, instance=task, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return back(request, 'home' if task.status == OPEN else 'complete')
    return render(request, 'update.html', {'form': form, 'data': task, 'next': safe_next(request)})


# ---------- One task at a time ----------

@login_required
@require_POST
def hcomplete(request, pk):
    task = own(request, pk, OPEN)
    today = timezone.localdate()
    item = services.complete(task, today)
    text = f'Done: “{short(task.title)}”.'
    if task.repeat:
        text += f' The next one is due {due_phrase(task.due_date, today)}.'
    remember_undo(request, [item], text)
    return back(request, 'home')


@login_required
@require_POST
def delete(request, pk):
    task = own(request, pk, OPEN, DONE)
    remember_undo(request, [services.trash(task)], f'Moved “{short(task.title)}” to the trash.')
    return back(request, 'home')


@login_required
@require_POST
def restore(request, pk):
    task = own(request, pk, DONE)
    remember_undo(request, [services.reopen(task)], f'“{short(task.title)}” is back on your list.')
    return back(request, 'complete')


@login_required
@require_POST
def recover(request, pk):
    task = own(request, pk, TRASHED)
    remember_undo(request, [services.reopen(task)], f'Restored “{short(task.title)}” to your list.')
    return back(request, 'trash')


@login_required
@require_POST
def hdelete(request, pk):
    own(request, pk, TRASHED).delete()
    return back(request, 'trash')


# ---------- Many at once ----------

def bulk_scope(request):
    scope = request.POST.get('scope', 'all')
    return scope if scope in SCOPES or (scope.startswith('list:') and scope[5:].isdigit()) else 'all'


@login_required
@require_POST
def complete_all(request):
    today = timezone.localdate()
    tasks = list(scoped(request.user, bulk_scope(request), today))
    items = [services.complete(t, today) for t in tasks]
    remember_undo(request, items, f'Checked off {plural(len(items), "task")}.')
    return back(request, 'home')


@login_required
@require_POST
def delete_all(request):
    tasks = list(scoped(request.user, bulk_scope(request), timezone.localdate()))
    items = [services.trash(t) for t in tasks]
    remember_undo(request, items, f'Moved {plural(len(items), "task")} to the trash.')
    return back(request, 'home')


@login_required
@require_POST
def restore_all(request):
    tasks = Task.objects.filter(user=request.user, status=DONE).order_by('completed_at', 'id')
    items = [services.reopen(t) for t in tasks]
    remember_undo(request, items, f'Moved {plural(len(items), "task")} back to your list.')
    return back(request, 'complete')


@login_required
@require_POST
def clear_complete(request):
    tasks = Task.objects.filter(user=request.user, status=DONE)
    items = [services.trash(t) for t in tasks]
    remember_undo(request, items, f'Moved {plural(len(items), "completed task")} to the trash.')
    return back(request, 'complete')


@login_required
@require_POST
def delete_all_per(request):
    Task.objects.filter(user=request.user, status=TRASHED).delete()
    return back(request, 'trash')


@login_required
@require_POST
def undo(request):
    saved = request.session.get('undo')
    if (not saved or not secrets.compare_digest(saved.get('token', ''), request.POST.get('token', ''))
            or time.time() - saved.get('at', 0) > services.UNDO_SECONDS):
        messages.error(request, 'That can no longer be undone.')
        return back(request, 'home')
    del request.session['undo']
    count = services.undo(request.user, saved['items'])
    messages.info(request, 'Undone.' if count == 1 else f'Undone: {plural(count, "task")} put back.')
    return back(request, 'home')


@login_required
@require_POST
def reorder(request):
    """Drag-to-reorder saves here: {"ids": [3, 1, 2]} in their new order."""
    try:
        ids = json.loads(request.body or b'{}').get('ids', [])
        ids = [int(i) for i in ids]
    except (ValueError, TypeError, AttributeError):
        return HttpResponseBadRequest('Expected {"ids": [...]}')
    if not ids or len(ids) > 2000 or len(ids) != len(set(ids)):
        return HttpResponseBadRequest('Expected a list of distinct task ids')
    if not services.reorder(request.user, ids):
        return JsonResponse({'ok': False, 'error': 'Some tasks were not found. Reload and try again.'}, status=409)
    return JsonResponse({'ok': True})


# ---------- Lists ----------

@login_required
def list_create(request):
    form = ListForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        task_list = services.create_list(request.user, form.cleaned_data['name'])
        if request.POST.get('color'):
            task_list.color = form.cleaned_data['color']
            task_list.save(update_fields=['color'])
        return redirect('list', pk=task_list.pk)
    return render(request, 'list_form.html', {'form': form, 'creating': True})


@login_required
def list_edit(request, pk):
    task_list = get_object_or_404(TaskList, pk=pk, user=request.user)
    form = ListForm(request.POST or None, instance=task_list, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('list', pk=task_list.pk)
    return render(request, 'list_form.html', {'form': form, 'task_list': task_list})


@login_required
@require_POST
def list_delete(request, pk):
    task_list = get_object_or_404(TaskList, pk=pk, user=request.user)
    name = task_list.name
    task_list.delete()  # its tasks stay, just without a list
    messages.success(request, f'Deleted the list “{short(name)}”. Its tasks are still in Tasks.')
    return redirect('home')


# ---------- Settings and the morning email ----------

def site_url(request):
    return settings.SITE_URL or request.build_absolute_uri('/').rstrip('/')


@login_required
def settings_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = SettingsForm(request.POST or None, initial={'email': request.user.email, 'digest_enabled': profile.digest_enabled})
    if request.method == 'POST' and form.is_valid():
        request.user.email = form.cleaned_data['email']
        request.user.save(update_fields=['email'])
        profile.digest_enabled = form.cleaned_data['digest_enabled']
        profile.save(update_fields=['digest_enabled'])
        messages.success(request, 'Settings saved.')
        return redirect('settings')
    # when the daily run happens, in the time zone the email itself uses
    run = timezone.now().replace(hour=settings.DIGEST_UTC_HOUR, minute=30, second=0, microsecond=0)
    zone = valid_zone(profile.timezone) or datetime.timezone.utc
    return render(request, 'settings.html', {
        'form': form,
        'profile': profile,
        'email_ready': settings.EMAIL_CONFIGURED,
        'on_vercel': settings.ON_VERCEL,
        'digest_time': run.astimezone(zone).strftime('%I:%M %p').lstrip('0'),
    })


@login_required
@require_POST
def digest_test(request):
    if not request.user.email:
        messages.error(request, 'Add your email address first.')
    elif settings.ON_VERCEL and not settings.EMAIL_CONFIGURED:
        messages.error(request, 'Email sending is not set up on this server yet.')
    else:
        try:
            digest.send_test(request.user, site_url(request))
        except Exception:  # SMTP refused, wrong password, no network...
            messages.error(request, 'The test email could not be sent. Check the email settings on the server.')
        else:
            messages.success(request, f'Test email sent to {request.user.email}.')
    return redirect('settings')


@require_GET
def cron_digest(request):
    """Called once a day by Vercel Cron, which sends "Authorization: Bearer <CRON_SECRET>"."""
    expected = f'Bearer {settings.CRON_SECRET}'
    if not settings.CRON_SECRET or not secrets.compare_digest(request.headers.get('Authorization', ''), expected):
        return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)
    if not settings.EMAIL_CONFIGURED:
        return JsonResponse({'ok': False, 'error': 'email is not configured'}, status=503)
    return JsonResponse({'ok': True, **digest.send_all(site_url(request))})
