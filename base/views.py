from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_POST
from .models import TaskModel,TrashModel,CompleteModel

# Create your views here.
def landing(request):
    context={}
    if request.user.is_authenticated:
        context={
            'open_count':TaskModel.objects.filter(user=request.user).count(),
            'done_count':CompleteModel.objects.filter(user=request.user).count(),
            'trash_count':TrashModel.objects.filter(user=request.user).count()
        }
    return render(request,'landing.html',context)

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    form=UserCreationForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        user=form.save()
        login(request,user)
        messages.success(request,f'Welcome aboard, {user.username}! Add your first task.')
        return redirect('home')
    return render(request,'registration/register.html',{'form':form})

@login_required
def home(request):
    all_data=TaskModel.objects.filter(user=request.user)
    context={'data':all_data}
    return render(request,'home.html',context)

@login_required
def add(request):
    if request.method=='POST':
        title_data=request.POST['title']
        desc_data=request.POST['desc']
        TaskModel.objects.create(
            user=request.user,
            title=title_data,
            desc=desc_data
        )
        return redirect('home')
    return render(request,'add.html')

@login_required
def complete(request):
    data=CompleteModel.objects.filter(user=request.user)
    context3={
        'data':data
    }
    return render(request,'complete.html',context3)

@login_required
def trash(request):
    data=TrashModel.objects.filter(user=request.user)
    context1={
        'data':data
    }
    return render(request,'trash.html',context1)

def about(request):
    return render(request,'about.html')

@login_required
@require_POST
def delete(request,pk):
    a=get_object_or_404(TaskModel,id=pk,user=request.user)
    TrashModel.objects.create(
        user=request.user,
        title=a.title,
        desc=a.desc
    )
    a.delete()
    return redirect('home')

@login_required
def update(request,pk):
    update_data=get_object_or_404(TaskModel,id=pk,user=request.user)
    if request.method=="POST":
        title_data=request.POST['title']
        desc_data=request.POST['desc']
        update_data.title=title_data
        update_data.desc=desc_data
        update_data.save()
        return redirect('home')
    return render(request,'update.html',{"data":update_data})

@login_required
@require_POST
def recover(request,pk):
     recover_data=get_object_or_404(TrashModel,id=pk,user=request.user)
     TaskModel.objects.create(
         user=request.user,
         title=recover_data.title,
         desc=recover_data.desc
     )
     recover_data.delete()
     return redirect('home')

@login_required
@require_POST
def hcomplete(request,pk):
    complete_data=get_object_or_404(TaskModel,id=pk,user=request.user)
    CompleteModel.objects.create(
        user=request.user,
        title=complete_data.title,
        desc=complete_data.desc
    )

    complete_data.delete()
    return redirect('home')

@login_required
@require_POST
def complete_all(request):
    all_data=TaskModel.objects.filter(user=request.user)
    for i in all_data:
        CompleteModel.objects.create(
        user=request.user,
        title=i.title,
        desc=i.desc
      )
        i.delete()
    return redirect('home')

@login_required
@require_POST
def delete_all(request):
    all_data=TaskModel.objects.filter(user=request.user)
    for i in all_data:
        TrashModel.objects.create(
        user=request.user,
        title=i.title,
        desc=i.desc
      )
        i.delete()
    return redirect('home')

@login_required
@require_POST
def restore_all(request):
    all_data=CompleteModel.objects.filter(user=request.user)
    for i in all_data:
        TaskModel.objects.create(
        user=request.user,
        title=i.title,
        desc=i.desc
      )
        i.delete()
    return redirect('complete')

@login_required
@require_POST
def delete_all_per(request):
    delete_data=TrashModel.objects.filter(user=request.user)
    for i in delete_data:
        i.delete()
    return redirect('trash')

@login_required
@require_POST
def hdelete(request,pk):
    b=get_object_or_404(TrashModel,id=pk,user=request.user)
    b.delete()
    return redirect('trash')

@login_required
@require_POST
def restore(request,pk):
    restore_data=get_object_or_404(CompleteModel,id=pk,user=request.user)
    TaskModel.objects.create(
        user=request.user,
        title=restore_data.title,
        desc=restore_data.desc
    )
    restore_data.delete()
    return redirect('complete')

@login_required
@require_POST
def clear_complete(request):
    all_data=CompleteModel.objects.filter(user=request.user)
    for i in all_data:
        TrashModel.objects.create(
        user=request.user,
        title=i.title,
        desc=i.desc
      )
        i.delete()
    return redirect('complete')
