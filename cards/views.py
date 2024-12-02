# need to edit

# The view will assemble requested data and style it before generating a HTTP response

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import SignUpForm, FlashcardSetTitle, FlashcardTermDefs
from django.forms import modelform_factory, modelformset_factory
from django.contrib import messages
from django import forms  # Import forms if not already done
from django.forms import modelformset_factory
from django.shortcuts import render, redirect, get_object_or_404
from .models import FlashcardSet, Flashcard

from django.views.generic import (
    ListView,
    CreateView,
    UpdateView
)


import random
from .models import Flashcard, FlashcardSet, Profile

def landing_page(request):
    return render(request, 'cards/landing.html')

def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return redirect('signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return redirect('signup')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('signup')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save() 

        login(request, user)
        return redirect('dashboard')

    return render(request, 'cards/signup.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Incorrect username or password.")
            return redirect('login')
    
    return render(request, 'cards/login.html')




@login_required
def dashboard(request):
    flashcard_sets = FlashcardSet.objects.filter(user=request.user.profile)

    return render(request, 'cards/dashboard.html', {
        'flashcard_sets': flashcard_sets,
        'username': request.user.username,
    })


@login_required
def user_logout(request):
    logout(request)
    return redirect('login')


@login_required
def create(request):
    FlashcardSetTitle = modelform_factory(
        FlashcardSet, 
        fields=['name'], 
        widgets={'name': forms.TextInput(attrs={'placeholder': 'Title', 'class': 'form-control'})}
    )

    FlashcardTermDefs = modelformset_factory(
        Flashcard,
        fields=['term', 'definition'],
        widgets={
            'term': forms.TextInput(attrs={'placeholder': 'Term', 'class': 'form-control'}),
            'definition': forms.TextInput(attrs={'placeholder': 'Definition', 'class': 'form-control'})
        },
        extra=1,
        can_delete=True,
    )

    if request.method == 'POST':
        set_form = FlashcardSetTitle(request.POST)
        formset = FlashcardTermDefs(request.POST, queryset=Flashcard.objects.none())

        if set_form.is_valid() and formset.is_valid():
            all_filled = True  # Flag to track if all forms are complete
            for form in formset:
                if form.cleaned_data:
                    term = form.cleaned_data.get('term')
                    definition = form.cleaned_data.get('definition')

                    # Check if either term or definition is empty
                    if not term or not definition:
                        all_filled = False
                        form.add_error(None, "Both term and definition are required.")

            if all_filled:
                flashcard_set = set_form.save(commit=False)
                flashcard_set.user = request.user.profile
                flashcard_set.save()

                for form in formset:
                    if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                        flashcard = form.save(commit=False)
                        flashcard.set = flashcard_set
                        flashcard.save()

                messages.success(request, "Flashcard set created successfully!")
                return redirect('dashboard')
            else:
                messages.error(request, "Please fill out all terms and definitions.")
        else:
            messages.error(request, "Error saving the flashcard set. Please make sure all fields are filled out.")
    else:
        set_form = FlashcardSetTitle()
        formset = FlashcardTermDefs(queryset=Flashcard.objects.none())

    return render(
        request,
        'cards/create.html',
        {
            'flashcard_set_form': set_form,
            'formset': formset,
        }
    )


def study_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)
    flashcards = flashcard_set.flashcards.all()
    return render(request, 'cards/study.html', {
        'flashcard_set': flashcard_set,
        'flashcards': flashcards,
    })


def edit_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, pk=set_id)

    if request.method == 'POST':
        flashcard_set_form = FlashcardSetTitle(request.POST, instance=flashcard_set)
        flashcard_formset = FlashcardTermDefs(request.POST, instance=flashcard_set)
        print("trying to save")
        if flashcard_set_form.is_valid() and flashcard_formset.is_valid():
            flashcard_set_form.save()
            flashcard_formset.save()
            return redirect('dashboard')
        print("Failed to save")
        print("Flashcard set form errors:", flashcard_set_form.errors)
        print("Flashcard formset errors:", flashcard_formset.errors)
    else:
        flashcard_set_form = FlashcardSetTitle(instance=flashcard_set)
        flashcard_formset = FlashcardTermDefs(instance=flashcard_set)

    return render(request, 'cards/edit.html', {
        'flashcard_set_form': flashcard_set_form,
        'flashcard_formset': flashcard_formset,
        'flashcard_set': flashcard_set,
    })


def delete_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)
    
    if request.method == 'POST':
        flashcard_set.delete()
        messages.success(request, 'Flashcard set deleted successfully.')
        return redirect('dashboard')
    
    return redirect('dashboard')

# @login_required
# def view_set(request, set_id):
#     flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user)
#     flashcards = flashcard_set.flashcards.all()
#     return render(request, 'cards/view_set.html', {'flashcard_set': flashcard_set, 'flashcards': flashcards})

# @login_required
# def edit_flashcard(request, card_id):
#     flashcard = get_object_or_404(Flashcard, id=card_id, set__user=request.user)
#     if request.method == 'POST':
#         form = CardForm(request.POST, instance=flashcard)
#         if form.is_valid():
#             form.save()
#             messages.success(request, "Flashcard updated successfully.")
#             return redirect('view_set', set_id=flashcard.set.id)
#     else:
#         form = CardForm(instance=flashcard)
#     return render(request, 'cards/edit_flashcard.html', {'form': form, 'flashcard': flashcard})

# @login_required
# def delete_flashcard(request, card_id):
#     flashcard = get_object_or_404(Flashcard, id=card_id, set__user=request.user)
#     set_id = flashcard.set.id
#     flashcard.delete()
#     messages.success(request, "Flashcard deleted successfully.")
#     return redirect('view_set', set_id=set_id)