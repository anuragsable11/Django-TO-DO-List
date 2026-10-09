import datetime
import json

from django.contrib.auth.models import User
from django.core import mail
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import digest
from .dates import add_months, describe_due, next_occurrence
from .models import Profile, Task, TaskList
from .quickadd import parse

FRIDAY = datetime.date(2026, 10, 9)
DAY = datetime.timedelta(days=1)


def make(user, title, **fields):
    fields.setdefault('position', Task.objects.filter(user=user).count() + 1)
    return Task.objects.create(user=user, title=title, **fields)


class QuickAddParserTests(TestCase):
    def check(self, text, title, due=None, repeat='', priority=None, list_name=''):
        result = parse(text, FRIDAY)
        self.assertEqual(
            (result.title, result.due_date, result.repeat, result.priority, result.list_name),
            (title, due, repeat, priority, list_name), text)

    def test_dates_lists_and_priority(self):
        self.check('Pay rent friday #home !high', 'Pay rent', FRIDAY + 7 * DAY, priority=3, list_name='Home')
        self.check('Buy milk today', 'Buy milk', FRIDAY)
        self.check('Call mom tomorrow', 'Call mom', FRIDAY + DAY)
        self.check('Send report by 12 oct', 'Send report', datetime.date(2026, 10, 12))
        self.check('Visit jan 3', 'Visit', datetime.date(2027, 1, 3))
        self.check('Trip in 2 weeks', 'Trip', FRIDAY + 14 * DAY)
        self.check('Dentist next monday', 'Dentist', datetime.date(2026, 10, 12))
        self.check('Exam 2026-12-01', 'Exam', datetime.date(2026, 12, 1))
        self.check('Ship it due in three days', 'Ship it', FRIDAY + 3 * DAY)
        self.check('Read !!! #side-project', 'Read', priority=3, list_name='Side project')
        self.check('Tidy up !low', 'Tidy up', priority=1)

    def test_repeats(self):
        self.check('Water plants every monday', 'Water plants', datetime.date(2026, 10, 12), 'weekly')
        self.check('Standup tomorrow daily', 'Standup', FRIDAY + DAY, 'daily')
        self.check('Payday monthly', 'Payday', FRIDAY, 'monthly')
        self.check('Clean every weekday', 'Clean', FRIDAY, 'weekdays')

    def test_leaves_ordinary_titles_alone(self):
        self.check('Plan Friday party', 'Plan Friday party')
        self.check('Enjoy the sun', 'Enjoy the sun')
        self.check('Tomorrow', 'Tomorrow')
        self.check('Fix bug #123', 'Fix bug #123')
        self.check('Taxes 31 feb', 'Taxes 31 feb')


class DateTests(TestCase):
    def test_next_occurrence(self):
        self.assertEqual(next_occurrence('daily', FRIDAY, FRIDAY), FRIDAY + DAY)
        self.assertEqual(next_occurrence('daily', FRIDAY - 5 * DAY, FRIDAY), FRIDAY + DAY)  # overdue: tomorrow
        self.assertEqual(next_occurrence('weekdays', FRIDAY, FRIDAY), FRIDAY + 3 * DAY)    # skips the weekend
        self.assertEqual(next_occurrence('weekly', FRIDAY - 2 * DAY, FRIDAY), FRIDAY + 5 * DAY)
        self.assertEqual(next_occurrence('monthly', datetime.date(2026, 1, 31), datetime.date(2026, 1, 31)), datetime.date(2026, 2, 28))
        self.assertEqual(next_occurrence('daily', None, FRIDAY), FRIDAY + DAY)

    def test_add_months_and_labels(self):
        self.assertEqual(add_months(datetime.date(2024, 1, 31), 1), datetime.date(2024, 2, 29))
        self.assertEqual(add_months(datetime.date(2026, 11, 15), 3), datetime.date(2027, 2, 15))
        self.assertEqual(describe_due(FRIDAY, FRIDAY), 'Today')
        self.assertEqual(describe_due(FRIDAY + DAY, FRIDAY), 'Tomorrow')
        self.assertEqual(describe_due(FRIDAY + 3 * DAY, FRIDAY), 'Monday')
        self.assertEqual(describe_due(FRIDAY + 20 * DAY, FRIDAY), '29 Oct')
        self.assertEqual(describe_due(datetime.date(2027, 3, 1), FRIDAY), '1 Mar 2027')


class AuthPagesTests(TestCase):
    def test_task_pages_require_login(self):
        for name in ['home', 'today', 'upcoming', 'overdue', 'add', 'complete', 'trash', 'search', 'settings', 'list_create']:
            response = self.client.get(reverse(name))
            self.assertRedirects(response, f"{reverse('login')}?next={reverse(name)}")

    def test_public_pages_load(self):
        for name in ['landing', 'about', 'login', 'register']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(reverse('register'), {
            'username': 'hero', 'email': 'hero@example.com',
            'password1': 'Sup3r-secret-pass', 'password2': 'Sup3r-secret-pass',
        })
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(User.objects.get(username='hero').email, 'hero@example.com')
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)

    def test_register_email_is_optional(self):
        self.client.post(reverse('register'), {'username': 'quiet', 'password1': 'Sup3r-secret-pass', 'password2': 'Sup3r-secret-pass'})
        self.assertTrue(User.objects.filter(username='quiet', email='').exists())

    def test_register_shows_errors(self):
        response = self.client.post(reverse('register'), {'username': 'hero', 'password1': 'a', 'password2': 'b'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'field-error')

    def test_login_and_logout(self):
        User.objects.create_user('hero', password='Sup3r-secret-pass')
        response = self.client.post(reverse('login'), {'username': 'hero', 'password': 'Sup3r-secret-pass'})
        self.assertRedirects(response, reverse('home'))
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('landing'))
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)

    def test_bad_login_shows_error(self):
        response = self.client.post(reverse('login'), {'username': 'nobody', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'alert-error')


class SignedInTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', password='pass-Alice-123')
        self.client.force_login(self.user)
        self.today = timezone.localdate()

    def messages(self, response):
        return [str(m) for m in response.context['messages']] if response.context else []


class QuickAddViewTests(SignedInTestCase):
    def test_quick_add_reads_details_and_says_so(self):
        response = self.client.post(reverse('add'), {'quick': '1', 'title': 'Pay rent tomorrow #home !high', 'notes': 'by card'}, follow=True)
        task = Task.objects.get(user=self.user)
        self.assertEqual((task.title, task.notes, task.due_date, task.priority), ('Pay rent', 'by card', self.today + DAY, 3))
        self.assertEqual(task.task_list.name, 'Home')
        self.assertContains(response, 'due tomorrow, in Home (new list), high priority')

    def test_quick_add_reuses_lists_case_insensitively(self):
        TaskList.objects.create(user=self.user, name='Work')
        self.client.post(reverse('add'), {'quick': '1', 'title': 'Draft memo #work'})
        self.assertEqual(TaskList.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Task.objects.get().task_list.name, 'Work')

    def test_view_defaults(self):
        work = TaskList.objects.create(user=self.user, name='Work')
        self.client.post(reverse('add'), {'quick': '1', 'title': 'Alpha', 'default_due': 'today'})
        self.client.post(reverse('add'), {'quick': '1', 'title': 'Beta', 'default_due': 'tomorrow'})
        self.client.post(reverse('add'), {'quick': '1', 'title': 'Gamma', 'default_list': work.pk})
        self.assertEqual(Task.objects.get(title='Alpha').due_date, self.today)
        self.assertEqual(Task.objects.get(title='Beta').due_date, self.today + DAY)
        self.assertEqual(Task.objects.get(title='Gamma').task_list, work)

    def test_new_tasks_go_to_the_bottom(self):
        for title in ['one', 'two', 'three']:
            self.client.post(reverse('add'), {'quick': '1', 'title': title})
        self.assertEqual(list(Task.objects.values_list('title', flat=True)), ['one', 'two', 'three'])

    def test_blank_title_is_rejected(self):
        self.client.post(reverse('add'), {'quick': '1', 'title': '   '})
        self.assertFalse(Task.objects.exists())

    def test_returns_to_the_view_it_came_from(self):
        response = self.client.post(reverse('add'), {'quick': '1', 'title': 'x', 'next': reverse('today')})
        self.assertRedirects(response, reverse('today'))
        response = self.client.post(reverse('add'), {'quick': '1', 'title': 'y', 'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('home'))


class TaskFormTests(SignedInTestCase):
    def test_full_form(self):
        work = TaskList.objects.create(user=self.user, name='Work')
        response = self.client.post(reverse('add'), {
            'title': '  Quarterly   report ', 'notes': 'Numbers from finance', 'due_date': '2026-12-01',
            'repeat': 'monthly', 'priority': '3', 'task_list': work.pk,
        })
        self.assertRedirects(response, reverse('home'))
        task = Task.objects.get()
        self.assertEqual((task.title, task.repeat, task.priority, task.task_list), ('Quarterly report', 'monthly', 3, work))

    def test_repeat_without_date_starts_today(self):
        self.client.post(reverse('add'), {'title': 'Stretch', 'repeat': 'daily', 'priority': '2'})
        self.assertEqual(Task.objects.get().due_date, self.today)

    def test_cannot_file_into_someone_elses_list(self):
        other = TaskList.objects.create(user=User.objects.create_user('bob'), name='Bob')
        response = self.client.post(reverse('add'), {'title': 'Sneaky', 'priority': '2', 'task_list': other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Task.objects.exists())

    def test_edit_keeps_a_safe_next(self):
        task = make(self.user, 'Old')
        response = self.client.get(reverse('update', args=[task.pk]) + '?next=javascript:alert(1)')
        self.assertNotContains(response, 'javascript:')
        response = self.client.post(reverse('update', args=[task.pk]) + f'?next={reverse("today")}',
                                    {'title': 'New', 'priority': '2', 'next': reverse('today')})
        self.assertRedirects(response, reverse('today'))
        task.refresh_from_db()
        self.assertEqual(task.title, 'New')


class ActionAndUndoTests(SignedInTestCase):
    def undo(self, response=None):
        token = self.client.session['undo']['token']
        return self.client.post(reverse('undo'), {'token': token}, follow=True)

    def test_complete_and_undo(self):
        task = make(self.user, 'Write it')
        response = self.client.post(reverse('hcomplete', args=[task.pk]), follow=True)
        self.assertContains(response, 'data-undo')
        task.refresh_from_db()
        self.assertEqual(task.status, 'done')
        self.assertIsNotNone(task.completed_at)
        self.undo()
        task.refresh_from_db()
        self.assertEqual((task.status, task.completed_at), ('open', None))

    def test_repeating_task_comes_back_and_undo_puts_it_back(self):
        task = make(self.user, 'Stretch', repeat='daily', due_date=self.today)
        response = self.client.post(reverse('hcomplete', args=[task.pk]), follow=True)
        self.assertContains(response, 'The next one is due tomorrow')
        task.refresh_from_db()
        self.assertEqual((task.status, task.due_date), ('open', self.today + DAY))
        self.assertEqual(Task.objects.filter(status='done', title='Stretch').count(), 1)
        self.undo()
        task.refresh_from_db()
        self.assertEqual(task.due_date, self.today)
        self.assertFalse(Task.objects.filter(status='done').exists())

    def test_trash_restore_recover_and_delete(self):
        task = make(self.user, 'Shuffle')
        self.client.post(reverse('delete', args=[task.pk]))
        task.refresh_from_db()
        self.assertEqual(task.status, 'trashed')
        self.undo()
        task.refresh_from_db()
        self.assertEqual(task.status, 'open')

        self.client.post(reverse('hcomplete', args=[task.pk]))
        self.client.post(reverse('restore', args=[task.pk]))
        task.refresh_from_db()
        self.assertEqual(task.status, 'open')

        self.client.post(reverse('delete', args=[task.pk]))
        self.client.post(reverse('recover', args=[task.pk]))
        task.refresh_from_db()
        self.assertEqual(task.status, 'open')

        self.client.post(reverse('delete', args=[task.pk]))
        self.client.post(reverse('hdelete', args=[task.pk]))
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_bulk_actions_follow_the_view(self):
        due = make(self.user, 'Due', due_date=self.today)
        late = make(self.user, 'Late', due_date=self.today - DAY)
        later = make(self.user, 'Later', due_date=self.today + 5 * DAY)
        loose = make(self.user, 'Loose')
        self.client.post(reverse('complete_all'), {'scope': 'today'})
        statuses = dict(Task.objects.values_list('title', 'status'))
        self.assertEqual(statuses, {'Due': 'done', 'Late': 'done', 'Later': 'open', 'Loose': 'open'})
        self.undo()
        self.assertEqual(Task.objects.filter(status='open').count(), 4)
        self.client.post(reverse('delete_all'), {'scope': 'upcoming'})
        self.assertEqual(Task.objects.get(pk=later.pk).status, 'trashed')
        self.client.post(reverse('delete_all'), {'scope': 'nonsense'})  # unknown scope means everything
        self.assertEqual(Task.objects.filter(status='trashed').count(), 4)
        self.client.post(reverse('delete_all_per'))
        self.assertFalse(Task.objects.exists())
        for task in (due, late, loose):
            self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_completed_bulk_actions(self):
        for title in ['a', 'b']:
            make(self.user, title, status='done', completed_at=timezone.now())
        self.client.post(reverse('restore_all'))
        self.assertEqual(Task.objects.filter(status='open').count(), 2)
        Task.objects.update(status='done')
        self.client.post(reverse('clear_complete'))
        self.assertEqual(Task.objects.filter(status='trashed').count(), 2)

    def test_undo_needs_the_right_token_in_time(self):
        task = make(self.user, 'Careful')
        self.client.post(reverse('hcomplete', args=[task.pk]))
        response = self.client.post(reverse('undo'), {'token': 'wrong'}, follow=True)
        self.assertContains(response, 'can no longer be undone')
        session = self.client.session
        session['undo']['at'] -= 3600
        session.save()
        self.client.post(reverse('undo'), {'token': session['undo']['token']})
        task.refresh_from_db()
        self.assertEqual(task.status, 'done')

    def test_undo_only_touches_own_tasks(self):
        bob = User.objects.create_user('bob')
        bobs = make(bob, 'Bob task', status='done')
        session = self.client.session
        session['undo'] = {'token': 't', 'at': __import__('time').time(),
                           'items': [{'id': bobs.pk, 'status': 'open', 'due_date': None, 'completed_at': None, 'trashed_at': None}]}
        session.save()
        self.client.post(reverse('undo'), {'token': 't'})
        bobs.refresh_from_db()
        self.assertEqual(bobs.status, 'done')


class ViewTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        self.late = make(self.user, 'Late one', due_date=self.today - 2 * DAY)
        self.due = make(self.user, 'Due one', due_date=self.today, priority=3)
        self.soon = make(self.user, 'Soon one', due_date=self.today + DAY)
        self.loose = make(self.user, 'Loose one', notes='no date at all')

    def titles(self, response):
        return [t.title for g in response.context['groups'] for t in g['tasks']]

    def test_today_shows_overdue_then_today(self):
        response = self.client.get(reverse('today'))
        self.assertEqual([g['title'] for g in response.context['groups']], ['Overdue', 'Today'])
        self.assertEqual(self.titles(response), ['Late one', 'Due one'])

    def test_upcoming_and_overdue(self):
        response = self.client.get(reverse('upcoming'))
        self.assertEqual(self.titles(response), ['Soon one'])
        self.assertEqual(response.context['groups'][0]['title'], 'Tomorrow')
        self.assertEqual(self.titles(self.client.get(reverse('overdue'))), ['Late one'])

    def test_all_tasks_sorting(self):
        self.assertEqual(self.titles(self.client.get(reverse('home'))), ['Late one', 'Due one', 'Soon one', 'Loose one'])
        self.assertEqual(self.titles(self.client.get(reverse('home') + '?sort=priority'))[0], 'Due one')
        self.assertEqual(self.titles(self.client.get(reverse('home') + '?sort=due'))[-1], 'Loose one')
        self.assertTrue(self.client.get(reverse('home')).context['draggable'])
        self.assertFalse(self.client.get(reverse('home') + '?sort=due').context['draggable'])

    def test_rail_counts(self):
        counts = self.client.get(reverse('home')).context['task_counts']
        self.assertEqual((counts.open, counts.today, counts.upcoming, counts.overdue), (4, 2, 1, 1))
        self.assertEqual(counts.attention['kind'], 'overdue')

    def test_completed_groups_by_day(self):
        self.client.post(reverse('hcomplete', args=[self.loose.pk]))
        response = self.client.get(reverse('complete'))
        self.assertEqual(response.context['groups'][0]['title'], 'Today')

    def test_search_title_and_notes_only_mine(self):
        make(User.objects.create_user('bob'), 'Loose bob')
        response = self.client.get(reverse('search'), {'q': 'loose'})
        self.assertEqual(self.titles(response), ['Loose one'])
        self.assertContains(response, '<mark>Loose</mark>')
        self.assertEqual(self.titles(self.client.get(reverse('search'), {'q': 'AT ALL'})), ['Loose one'])

    def test_search_escapes_html(self):
        make(self.user, '<b>bold</b> idea')
        response = self.client.get(reverse('search'), {'q': 'bold'})
        self.assertContains(response, '&lt;b&gt;<mark>bold</mark>&lt;/b&gt; idea')

    def test_landing_feeds_stripes_the_urgent_tasks_first(self):
        data = self.client.get(reverse('landing')).context['mascot']
        self.assertEqual([t['title'] for t in data['tasks']][:2], ['Late one', 'Due one'])
        self.assertEqual(data['tasks'][0]['when'], 'overdue')
        self.assertEqual((data['overdue'], data['due_today']), (1, 1))


class ReorderTests(SignedInTestCase):
    def post(self, ids, client=None):
        return (client or self.client).post(reverse('reorder'), json.dumps({'ids': ids}), content_type='application/json')

    def test_reorder_and_subset(self):
        a, b, c, d = (make(self.user, t) for t in 'abcd')
        self.assertEqual(self.post([c.pk, a.pk, b.pk, d.pk]).json(), {'ok': True})
        self.assertEqual(list(Task.objects.values_list('title', flat=True)), ['c', 'a', 'b', 'd'])
        # reordering just two of them (a filtered view) leaves the others in their places
        self.post([d.pk, a.pk])
        self.assertEqual(list(Task.objects.values_list('title', flat=True)), ['c', 'd', 'b', 'a'])

    def test_rejects_bad_input_and_other_peoples_tasks(self):
        mine = make(self.user, 'mine')
        theirs = make(User.objects.create_user('bob'), 'theirs')
        self.assertEqual(self.post([mine.pk, theirs.pk]).status_code, 409)
        self.assertEqual(self.post(['x']).status_code, 400)
        self.assertEqual(self.post([mine.pk, mine.pk]).status_code, 400)
        self.assertEqual(self.client.get(reverse('reorder')).status_code, 405)

    def test_needs_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(self.post([make(self.user, 'x').pk], client).status_code, 403)


class ListTests(SignedInTestCase):
    def test_create_edit_delete(self):
        response = self.client.post(reverse('list_create'), {'name': ' Work ', 'color': 'blue'})
        work = TaskList.objects.get()
        self.assertRedirects(response, reverse('list', args=[work.pk]))
        self.assertEqual((work.name, work.color), ('Work', 'blue'))

        response = self.client.post(reverse('list_create'), {'name': 'work'})
        self.assertContains(response, 'You already have a list called')

        self.client.post(reverse('list_edit', args=[work.pk]), {'name': 'Office', 'color': 'green'})
        work.refresh_from_db()
        self.assertEqual((work.name, work.color), ('Office', 'green'))

        task = make(self.user, 'Filed', task_list=work)
        self.assertEqual([t.title for g in self.client.get(reverse('list', args=[work.pk])).context['groups'] for t in g['tasks']], ['Filed'])
        self.client.post(reverse('list_delete', args=[work.pk]))
        task.refresh_from_db()
        self.assertIsNone(task.task_list)
        self.assertEqual(task.status, 'open')

    def test_other_peoples_lists_are_hidden(self):
        theirs = TaskList.objects.create(user=User.objects.create_user('bob'), name='Bob')
        self.assertEqual(self.client.get(reverse('list', args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('list_edit', args=[theirs.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('list_delete', args=[theirs.pk])).status_code, 404)


class IsolationAndMethodTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        self.bob = User.objects.create_user('bob', password='pass-Bob-123')
        self.mine = make(self.user, 'Alice task')
        self.open = make(self.bob, 'Bob task')
        self.done = make(self.bob, 'Bob done', status='done')
        self.trashed = make(self.bob, 'Bob trash', status='trashed')

    def test_lists_only_show_own_tasks(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Alice task')
        self.assertNotContains(response, 'Bob task')

    def test_cannot_touch_other_users_tasks(self):
        self.assertEqual(self.client.get(reverse('update', args=[self.open.pk])).status_code, 404)
        for name, task in [('delete', self.open), ('hcomplete', self.open), ('restore', self.done),
                           ('recover', self.trashed), ('hdelete', self.trashed)]:
            self.assertEqual(self.client.post(reverse(name, args=[task.pk])).status_code, 404, name)
        self.client.post(reverse('complete_all'))
        self.client.post(reverse('delete_all_per'))
        self.assertEqual(Task.objects.filter(user=self.bob).count(), 3)
        self.assertEqual(Task.objects.get(pk=self.open.pk).status, 'open')

    def action_urls(self):
        done = make(self.user, 'd', status='done')
        trashed = make(self.user, 't', status='trashed')
        return [
            reverse('delete', args=[self.mine.pk]), reverse('hcomplete', args=[self.mine.pk]),
            reverse('recover', args=[trashed.pk]), reverse('hdelete', args=[trashed.pk]),
            reverse('restore', args=[done.pk]), reverse('complete_all'), reverse('delete_all'),
            reverse('restore_all'), reverse('delete_all_per'), reverse('clear_complete'), reverse('undo'),
            reverse('digest_test'), reverse('list_delete', args=[TaskList.objects.create(user=self.user, name='L').pk]),
        ]

    def test_get_is_rejected(self):
        for url in self.action_urls():
            self.assertEqual(self.client.get(url).status_code, 405, url)
        self.assertEqual(Task.objects.get(pk=self.mine.pk).status, 'open')

    def test_post_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for url in self.action_urls():
            self.assertEqual(client.post(url).status_code, 403, url)
        self.assertEqual(Task.objects.get(pk=self.mine.pk).status, 'open')

    def test_pages_render_with_csrf_tokens(self):
        make(self.user, 'done one', status='done')
        make(self.user, 'trash one', status='trashed')
        for name in ['home', 'today', 'upcoming', 'overdue', 'complete', 'trash', 'settings']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, 'csrfmiddlewaretoken')


class TimezoneTests(SignedInTestCase):
    def test_browser_zone_is_used_and_saved(self):
        self.client.cookies['tz'] = 'Asia/Kolkata'
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Profile.objects.get(user=self.user).timezone, 'Asia/Kolkata')

    def test_bad_zone_is_ignored(self):
        self.client.cookies['tz'] = 'Mars/Olympus_Mons'
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)
        self.assertFalse(Profile.objects.filter(user=self.user).exists())

    def test_today_follows_the_zone(self):
        # 23:30 UTC is already tomorrow in Kolkata (UTC+5:30): a task due "tomorrow UTC" is due today there
        profile = Profile.objects.create(user=self.user, timezone='Asia/Kolkata')
        late_evening = datetime.datetime(2026, 10, 9, 23, 30, tzinfo=datetime.timezone.utc)
        self.assertEqual(digest.user_today(profile, late_evening), datetime.date(2026, 10, 10))


class SettingsTests(SignedInTestCase):
    def test_save_email_and_digest(self):
        response = self.client.post(reverse('settings'), {'email': 'alice@example.com', 'digest_enabled': 'on'})
        self.assertRedirects(response, reverse('settings'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'alice@example.com')
        self.assertTrue(Profile.objects.get(user=self.user).digest_enabled)

    def test_digest_needs_an_email(self):
        response = self.client.post(reverse('settings'), {'email': '', 'digest_enabled': 'on'})
        self.assertContains(response, 'Add an email address')

    def test_test_email(self):
        self.user.email = 'alice@example.com'
        self.user.save()
        make(self.user, 'Due now', due_date=self.today)
        self.client.post(reverse('digest_test'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Due now', mail.outbox[0].body)


class DigestTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('alice', email='alice@example.com')
        self.profile = Profile.objects.create(user=self.user, digest_enabled=True, timezone='UTC')
        self.now = timezone.now()
        self.today = self.now.date()

    def test_sends_overdue_and_due_today_once_a_day(self):
        make(self.user, 'Overdue thing', due_date=self.today - DAY)
        make(self.user, 'Today thing', due_date=self.today)
        make(self.user, 'Later thing', due_date=self.today + DAY)
        stats = digest.send_all('https://doneward.test', self.now)
        self.assertEqual(stats['sent'], 1)
        body = mail.outbox[0].body
        self.assertIn('Overdue thing', body)
        self.assertIn('Today thing', body)
        self.assertNotIn('Later thing', body)
        self.assertEqual(mail.outbox[0].subject, 'Your day: 1 due today and 1 overdue')
        self.assertIn('https://doneward.test/tasks/today/', mail.outbox[0].alternatives[0][0])
        self.assertEqual(digest.send_all('https://doneward.test', self.now)['already_sent'], 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_nothing_due_means_no_email(self):
        make(self.user, 'Someday')
        self.assertEqual(digest.send_all('https://doneward.test', self.now)['nothing_due'], 1)
        self.assertEqual(mail.outbox, [])

    def test_only_people_who_opted_in(self):
        make(self.user, 'Due', due_date=self.today)
        self.profile.digest_enabled = False
        self.profile.save()
        self.assertEqual(digest.send_all('https://doneward.test', self.now)['sent'], 0)

    @override_settings(CRON_SECRET='s3cret', EMAIL_CONFIGURED=True)
    def test_cron_endpoint(self):
        make(self.user, 'Due', due_date=self.today)
        self.assertEqual(self.client.get(reverse('cron_digest')).status_code, 401)
        self.assertEqual(self.client.get(reverse('cron_digest'), HTTP_AUTHORIZATION='Bearer wrong').status_code, 401)
        response = self.client.get(reverse('cron_digest'), HTTP_AUTHORIZATION='Bearer s3cret')
        self.assertEqual(response.json()['sent'], 1)

    @override_settings(CRON_SECRET='s3cret', EMAIL_CONFIGURED=False)
    def test_cron_without_email_settings(self):
        response = self.client.get(reverse('cron_digest'), HTTP_AUTHORIZATION='Bearer s3cret')
        self.assertEqual(response.status_code, 503)

    @override_settings(CRON_SECRET='')
    def test_cron_is_closed_without_a_secret(self):
        self.assertEqual(self.client.get(reverse('cron_digest'), HTTP_AUTHORIZATION='Bearer ').status_code, 401)


class DataMigrationTests(TransactionTestCase):
    """0006 moves rows from the three old tables into Task without losing order or owners."""

    before = [('base', '0004_completemodel_user_taskmodel_user_trashmodel_user')]
    after = [('base', '0007_remove_legacy_tables')]

    def test_rows_are_copied(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old = executor.loader.project_state(self.before).apps
        OldUser = old.get_model('auth', 'User')
        user = OldUser.objects.create(username='legacy', password='!')
        old.get_model('base', 'TaskModel').objects.create(user=user, title='first', desc='a')
        old.get_model('base', 'TaskModel').objects.create(user=user, title='second', desc='b')
        old.get_model('base', 'CompleteModel').objects.create(user=user, title='won', desc='')
        old.get_model('base', 'TrashModel').objects.create(user=user, title='binned', desc='')
        old.get_model('base', 'TaskModel').objects.create(user=None, title='orphan', desc='')

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)
        new = executor.loader.project_state(self.after).apps
        rows = list(new.get_model('base', 'Task').objects.order_by('status', 'position')
                    .values_list('user__username', 'title', 'notes', 'status', 'position'))
        self.assertEqual(rows, [
            ('legacy', 'won', '', 'done', 1),
            ('legacy', 'first', 'a', 'open', 1),
            ('legacy', 'second', 'b', 'open', 2),
            ('legacy', 'binned', '', 'trashed', 1),
        ])
