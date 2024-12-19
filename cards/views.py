
# The view will assemble requested data and style it before generating a HTTP response

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib.auth import login, authenticate, logout
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import SignUpForm, FlashcardSetTitle, FlashcardTermDefs
from django.forms import modelform_factory, modelformset_factory
from django.contrib import messages
from django import forms
from django.forms import modelformset_factory
from .models import FlashcardSet, Flashcard
from django.db.models import Case, When
from spaced_repetition import get_lineup, get_overdue_flashcards, ease_factor_calculation


from django.views.generic import (
    ListView,
    CreateView,
    UpdateView
)


import random
import datetime
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
        set_title = FlashcardSetTitle(request.POST)
        set_contents = FlashcardTermDefs(request.POST, queryset=Flashcard.objects.none())

        if set_title.is_valid() and set_contents.is_valid():
            all_filled = True
            for form in set_contents:
                if form.cleaned_data:
                    term = form.cleaned_data.get('term')
                    definition = form.cleaned_data.get('definition')

                    if not term or not definition:
                        all_filled = False
                        form.add_error(None, "Both term and definition are required.")

            if all_filled:
                flashcard_set = set_title.save(commit=False)
                flashcard_set.user = request.user.profile
                flashcard_set.save()
                for entry in set_contents:
                    if entry.cleaned_data and not entry.cleaned_data.get('DELETE'):
                        flashcard = entry.save(commit=False)
                        flashcard.set = flashcard_set
                        flashcard.save()
                return redirect('dashboard')
            else:
                messages.error(request, "Please fill out all terms and definitions.")
        else:
            messages.error(request, "Error saving the flashcard set. Please make sure all fields are filled out.")
    else:
        set_title = FlashcardSetTitle()
        set_contents = FlashcardTermDefs(queryset=Flashcard.objects.none())

    return render(
        request,
        'cards/create.html',
        {
            'set_title': set_title,
            'formset': set_contents,
        }
    )


def study_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)
    flashcards = flashcard_set.flashcards.all()
    return render(request, 'cards/study.html', {
        'flashcard_set': flashcard_set,
        'flashcards': flashcards,
    })


def setup_true_false(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    # generate a new lineup
    flashcards = list(flashcard_set.flashcards.all())
    new_lineup = get_lineup(flashcards)
    print("New lineup:", new_lineup)

    # store the lineup and reset the index
    request.session['lineup'] = [card.id for card in new_lineup]
    request.session['current_index'] = 0

    return redirect('true_false', set_id=set_id)


def true_false(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup_ids = request.session.get('lineup', [])
    if not lineup_ids:
        return redirect('setup_true_false', set_id=set_id)

    flashcards = Flashcard.objects.filter(id__in=lineup_ids)
    flashcard_map = {card.id: card for card in flashcards}
    lineup = [flashcard_map[card_id] for card_id in lineup_ids if card_id in flashcard_map]

    print("Lineup:", lineup)
    current_index = request.session.get('current_index', 0)

    if current_index >= len(lineup):
        return redirect('landing')

    flashcard = lineup[current_index]
    request.session['current_flashcard_id'] = flashcard.id

    term = flashcard.term

    # randomise the definition
    if random.choice([True, False]):
        definition = flashcard.definition
        is_correct = True
    else:
        other_flashcard = random.choice([card for card in lineup if card != flashcard])
        definition = other_flashcard.definition
        is_correct = False

    request.session['is_correct'] = is_correct

    return render(request, 'cards/true_false.html', {
        'flashcard_set': flashcard_set,
        'flashcard': {'term': term, 'definition': definition},
    })


def true_false_check(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup_ids = request.session.get('lineup', [])
    flashcards = Flashcard.objects.filter(id__in=lineup_ids)
    flashcard_map = {card.id: card for card in flashcards}
    lineup = [flashcard_map[card_id] for card_id in lineup_ids if card_id in flashcard_map]
    current_index = request.session.get('current_index', 0)

    if current_index >= len(lineup):
        return redirect('game_finished', set_id=set_id)

    flashcard = get_object_or_404(Flashcard, id=request.session.get('current_flashcard_id'))

    # get the user's answer and time taken
    user_answer = request.GET.get('answer', 'false') == 'true'
    elapsed_time = int(request.GET.get('time', 0))

    is_correct = request.session.get('is_correct', False)

    # evaluate the user's answer
    if user_answer == is_correct:
        if elapsed_time > 1.25 * flashcard_set.baseline:
            print("Slow")
            performance_level = 2
        elif elapsed_time > 0.75 * flashcard_set.baseline:
            print("Average")
            performance_level = 3
        else:
            print("Fast")
            performance_level = 4
    else:
        print("Incorrect")
        performance_level = 1

    # update flashcard's ease factor, interval, and last reviewed
    flashcard.ease_factor = ease_factor_calculation(flashcard.ease_factor, performance_level)
    print(f"New ease factor for the flashcard '{flashcard.term}' is: {flashcard.ease_factor:.2f}")
    flashcard.interval = max(flashcard.interval * flashcard.ease_factor, 86400)
    flashcard.last_reviewed = now()
    flashcard.save()

    # update the flashcard set's baseline
    new_baseline = (flashcard_set.baseline + elapsed_time) / 2
    flashcard_set.baseline = new_baseline
    flashcard_set.save()

    current_index += 1
    request.session['current_index'] = current_index

    if current_index >= len(lineup):
        return redirect('landing')

    return redirect('true_false', set_id=set_id)




def edit_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, pk=set_id)

    if request.method == 'POST':
        set_title = FlashcardSetTitle(request.POST, instance=flashcard_set)
        set_contents = FlashcardTermDefs(request.POST, instance=flashcard_set)

        print("POST data:", request.POST)

        print(set_contents)
        for form in set_contents.forms:
            if not form.cleaned_data.get('term') and not form.cleaned_data.get('definition'):
                form.cleaned_data['DELETE'] = True

        if set_title.is_valid() and set_contents.is_valid():
            set_title.save()
            set_contents.save()
            return redirect('dashboard')

        else:
            for form in set_contents:
                print("Form errors:", form.errors)
                print("Form data:", form.cleaned_data)
        
    else:
        set_title = FlashcardSetTitle(instance=flashcard_set)
        set_contents = FlashcardTermDefs(instance=flashcard_set)

    return render(request, 'cards/edit.html', {
        'set_title': set_title,
        'flashcard_formset': set_contents,
        'flashcard_set': flashcard_set,
    })


def delete_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)
    
    if request.method == 'POST':
        flashcard_set.delete()
        messages.success(request, 'Flashcard set deleted successfully.')
        return redirect('dashboard')
    
    return redirect('dashboard')
