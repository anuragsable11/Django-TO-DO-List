from django.shortcuts import render,redirect
from .models import TaskModel,TrashModel,CompleteModel

# Create your views here.
def home(request):
    all_data=TaskModel.objects.all()
    context={'data':all_data}
    return render(request,'home.html',context)

def add(request):
    if request.method=='POST':
        title_data=request.POST['title']
        desc_data=request.POST['desc']
        TaskModel.objects.create(
            title=title_data,
            desc=desc_data
            
        )
        return redirect('home')
    return render(request,'add.html')

def complete(request):
    data=CompleteModel.objects.all()
    context3={
        'data':data
    }
    return render(request,'complete.html',context3)

def trash(request):
    data=TrashModel.objects.all()
    context1={
        'data':data
    }
    return render(request,'trash.html',context1)

def about(request):
    return render(request,'about.html')
def delete(request,pk):
    a=TaskModel.objects.get(id=pk)
    TrashModel.objects.create(
        title=a.title,
        desc=a.desc
    )
    a.delete()
    return redirect('home')

def update(request,pk):
    update_data=TaskModel.objects.get(id=pk)
    if request.method=="POST":
        title_data=request.POST['title']
        desc_data=request.POST['desc']
        update_data.title=title_data
        update_data.desc=desc_data
        update_data.save()
        return redirect('home')
    return render(request,'update.html',{"data":update_data})
def recover(request,pk):
     recover_data=TrashModel.objects.get(id=pk)
     TaskModel.objects.create(
         title=recover_data.title,
         desc=recover_data.desc
     )
     recover_data.delete()
     return redirect('home')
 
def hcomplete(request,pk):
    complete_data=TaskModel.objects.get(id=pk)
    CompleteModel.objects.create(
        title=complete_data.title,
        desc=complete_data.desc
    )
    
    complete_data.delete()
    return redirect('home')

def complete_all(request):
    all_data=TaskModel.objects.all()
    for i in all_data:
        CompleteModel.objects.create(
        title=i.title,
        desc=i.desc
      )
        i.delete()
    return redirect('home')

def delete_all(request):
    all_data=TaskModel.objects.all()
    for i in all_data:
        TrashModel.objects.create(
        title=i.title,
        desc=i.desc
      )
        i.delete()
    return redirect('home')

def restore_all(request):
    all_data=CompleteModel.objects.all()
    for i in all_data:
        TaskModel.objects.create(
        title=i.title,
        desc=i.desc
      )
        i.delete()
    return redirect('complete') 

def delete_all_per(request):
    delete_data=TrashModel.objects.all()
    for i in delete_data:
        i.delete()
    return redirect('trash')     

def hdelete(request,pk):
    b=TrashModel.objects.get(id=pk)
    b.delete()
    return redirect('trash')            