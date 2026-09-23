from django.contrib.auth.models import User
from django.test import Client,TestCase
from django.urls import reverse

from .models import TaskModel,TrashModel,CompleteModel


class AuthPagesTests(TestCase):
    def test_task_pages_require_login(self):
        for name in ['home','add','complete','trash']:
            response=self.client.get(reverse(name))
            self.assertRedirects(response,f"{reverse('login')}?next={reverse(name)}")

    def test_public_pages_load(self):
        for name in ['landing','about','login','register']:
            self.assertEqual(self.client.get(reverse(name)).status_code,200)

    def test_register_creates_user_and_logs_in(self):
        response=self.client.post(reverse('register'),{
            'username':'hero',
            'password1':'Sup3r-secret-pass',
            'password2':'Sup3r-secret-pass',
        })
        self.assertRedirects(response,reverse('home'))
        self.assertTrue(User.objects.filter(username='hero').exists())
        self.assertEqual(self.client.get(reverse('home')).status_code,200)

    def test_register_shows_errors(self):
        response=self.client.post(reverse('register'),{
            'username':'hero','password1':'a','password2':'b',
        })
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'field-error')

    def test_login_and_logout(self):
        User.objects.create_user('hero',password='Sup3r-secret-pass')
        response=self.client.post(reverse('login'),{'username':'hero','password':'Sup3r-secret-pass'})
        self.assertRedirects(response,reverse('home'))
        response=self.client.post(reverse('logout'))
        self.assertRedirects(response,reverse('landing'))
        self.assertEqual(self.client.get(reverse('home')).status_code,302)

    def test_bad_login_shows_error(self):
        response=self.client.post(reverse('login'),{'username':'nobody','password':'wrong'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'alert-error')


class TaskIsolationTests(TestCase):
    def setUp(self):
        self.alice=User.objects.create_user('alice',password='pass-Alice-123')
        self.bob=User.objects.create_user('bob',password='pass-Bob-123')
        self.alice_task=TaskModel.objects.create(user=self.alice,title='Alice task',desc='a')
        self.bob_task=TaskModel.objects.create(user=self.bob,title='Bob task',desc='b')
        self.client.force_login(self.alice)

    def test_add_assigns_owner(self):
        self.client.post(reverse('add'),{'title':'New one','desc':''})
        self.assertEqual(TaskModel.objects.get(title='New one').user,self.alice)

    def test_lists_only_show_own_tasks(self):
        response=self.client.get(reverse('home'))
        self.assertContains(response,'Alice task')
        self.assertNotContains(response,'Bob task')

    def test_cannot_touch_other_users_task(self):
        pk=self.bob_task.id
        self.assertEqual(self.client.get(reverse('update',args=[pk])).status_code,404)
        for name in ['delete','hcomplete']:
            self.assertEqual(self.client.post(reverse(name,args=[pk])).status_code,404)
        self.client.post(reverse('update',args=[pk]),{'title':'hacked','desc':''})
        self.bob_task.refresh_from_db()
        self.assertEqual(self.bob_task.title,'Bob task')

    def test_cannot_touch_other_users_trash_or_completed(self):
        trash=TrashModel.objects.create(user=self.bob,title='Bob trash',desc='')
        done=CompleteModel.objects.create(user=self.bob,title='Bob done',desc='')
        self.assertEqual(self.client.post(reverse('recover',args=[trash.id])).status_code,404)
        self.assertEqual(self.client.post(reverse('hdelete',args=[trash.id])).status_code,404)
        self.assertEqual(self.client.post(reverse('restore',args=[done.id])).status_code,404)

    def test_bulk_actions_only_affect_own_tasks(self):
        self.client.post(reverse('delete_all'))
        self.assertTrue(TaskModel.objects.filter(id=self.bob_task.id).exists())
        self.assertTrue(TrashModel.objects.filter(user=self.alice,title='Alice task').exists())
        self.client.post(reverse('delete_all_per'))
        self.assertFalse(TrashModel.objects.filter(user=self.alice).exists())

    def test_task_keeps_owner_through_complete_and_restore(self):
        self.client.post(reverse('hcomplete',args=[self.alice_task.id]))
        done=CompleteModel.objects.get(title='Alice task')
        self.assertEqual(done.user,self.alice)
        self.client.post(reverse('restore',args=[done.id]))
        self.assertEqual(TaskModel.objects.get(title='Alice task').user,self.alice)


class ActionMethodTests(TestCase):
    """State-changing actions must be POST + CSRF so other sites can't trigger them."""

    def setUp(self):
        self.user=User.objects.create_user('alice',password='pass-Alice-123')
        self.task=TaskModel.objects.create(user=self.user,title='Keep me',desc='')
        self.client.force_login(self.user)

    def action_urls(self):
        trash=TrashModel.objects.create(user=self.user,title='t',desc='')
        done=CompleteModel.objects.create(user=self.user,title='d',desc='')
        return [
            reverse('delete',args=[self.task.id]),
            reverse('hcomplete',args=[self.task.id]),
            reverse('recover',args=[trash.id]),
            reverse('hdelete',args=[trash.id]),
            reverse('restore',args=[done.id]),
            reverse('complete_all'),
            reverse('delete_all'),
            reverse('restore_all'),
            reverse('delete_all_per'),
            reverse('clear_complete'),
        ]

    def test_get_is_rejected(self):
        for url in self.action_urls():
            self.assertEqual(self.client.get(url).status_code,405,url)
        self.assertTrue(TaskModel.objects.filter(id=self.task.id).exists())

    def test_post_without_csrf_token_is_rejected(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for url in self.action_urls():
            self.assertEqual(client.post(url).status_code,403,url)
        self.assertTrue(TaskModel.objects.filter(id=self.task.id).exists())

    def test_pages_render_action_forms_with_csrf_token(self):
        TrashModel.objects.create(user=self.user,title='t',desc='')
        CompleteModel.objects.create(user=self.user,title='d',desc='')
        for name in ['home','complete','trash']:
            response=self.client.get(reverse(name))
            self.assertContains(response,'method="POST"')
            self.assertContains(response,'csrfmiddlewaretoken')
