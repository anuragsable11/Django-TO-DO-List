from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import LIST_COLORS, Task, TaskList


class TaskForm(forms.ModelForm):
    """The full New task / Edit task form."""

    class Meta:
        model = Task
        fields = ['title', 'notes', 'due_date', 'repeat', 'priority', 'task_list']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input input-lg', 'autofocus': True, 'placeholder': 'e.g. Send the weekly report'}),
            'notes': forms.Textarea(attrs={'class': 'input textarea', 'rows': 3, 'placeholder': 'Details, links, anything that helps'}),
            'due_date': forms.DateInput(attrs={'class': 'input', 'type': 'date'}, format='%Y-%m-%d'),
            'repeat': forms.Select(attrs={'class': 'input select'}),
            'priority': forms.RadioSelect(),
            'task_list': forms.Select(attrs={'class': 'input select'}),
        }
        labels = {'notes': 'Notes', 'due_date': 'Due date', 'task_list': 'List'}

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['task_list'].queryset = TaskList.objects.filter(user=user)
        self.fields['task_list'].empty_label = 'No list'
        self.fields['priority'].choices = [(p.value, p.label) for p in reversed(Task.Priority)]

    def clean_title(self):
        title = ' '.join(self.cleaned_data['title'].split())
        if not title:
            raise forms.ValidationError('Give the task a title.')
        return title

    def clean(self):
        cleaned = super().clean()
        # a repeat needs a date to count from
        if cleaned.get('repeat') and not cleaned.get('due_date'):
            cleaned['due_date'] = timezone.localdate()
        return cleaned


class ListForm(forms.ModelForm):
    class Meta:
        model = TaskList
        fields = ['name', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'e.g. Work', 'maxlength': 40}),
            'color': forms.RadioSelect(),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['color'].choices = [(c, c.title()) for c in LIST_COLORS]
        self.fields['color'].required = False

    def clean_name(self):
        name = ' '.join(self.cleaned_data['name'].split())
        if not name:
            raise forms.ValidationError('Give the list a name.')
        clash = TaskList.objects.filter(user=self.user, name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(f'You already have a list called “{clash.first().name}”.')
        return name

    def clean_color(self):
        return self.cleaned_data.get('color') or self.instance.color or LIST_COLORS[0]


class SettingsForm(forms.Form):
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={'class': 'input', 'placeholder': 'you@example.com', 'autocomplete': 'email'}))
    digest_enabled = forms.BooleanField(required=False, label='Morning email')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('digest_enabled') and not cleaned.get('email'):
            self.add_error('email', 'Add an email address to get the morning email.')
        return cleaned


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        help_text='Optional. Used only for the morning email, which you can turn on in Settings.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'email']
