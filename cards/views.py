
# The view will assemble requested data and style it before generating a HTTP response

import sys
import time
from datetime import datetime
import random
from random import sample, shuffle
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy, reverse
from django.contrib.auth import login, authenticate, logout
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import SignUpForm, FlashcardSetTitle, FlashcardTermDefs
from django.forms import modelform_factory, modelformset_factory
from django.contrib import messages
from django import forms
from .models import FlashcardSet, Flashcard, Badge, UserBadge, Profile, Friendship, League, LeagueUser
from django.db.models import Case, When, Q
from spaced_repetition import get_lineup, get_overdue_flashcards, ease_factor_calculation
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

import nltk
nltk.download('punkt_tab')
nltk.download('wordnet')
nltk.download('omw-1.4')
nltk.download('stopwords')
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

from django.views.generic import (
    ListView,
    CreateView,
    UpdateView
)

def landing_page(request):
    return render(request, 'cards/landing.html')

def about(request):
    return render(request, 'cards/about.html')


def profile(request):
    displayed_badges = Badge.objects.filter(id__in=UserBadge.objects.filter(user=request.user.profile, displayed=True).values("badge_id"))
    owned_badges = Badge.objects.filter(id__in=UserBadge.objects.filter(user=request.user.profile).values("badge_id"))

    friend_profiles = request.user.profile.get_friends()
    friends = User.objects.filter(profile__in=friend_profiles)

    friends_with_badges = []
    for friend in friends:
        friend_badges = Badge.objects.filter(id__in=UserBadge.objects.filter(user=friend.profile, displayed=True).values("badge_id"))
        friends_with_badges.append({
            'friend': friend,
            'badges': friend_badges
        })

    leagues = League.objects.filter(owner=request.user.profile)

    return render(request, 'cards/profile.html', {
        'displayed_badges': displayed_badges,
        'owned_badges': owned_badges,
        'friends_with_badges': friends_with_badges,
        'leagues': leagues,
    })


def select_badges(request):
    user_badges = UserBadge.objects.filter(user=request.user.profile)
    return render(request, "cards/partials/select_badges.html", {"all_badges": user_badges})


def update_displayed_badges(request):
    if request.method == "POST":
        selected_badges = request.POST.getlist("selected_badges")
        print(f"Selected badges: {selected_badges}")

        if len(selected_badges) > 4:
            return JsonResponse({"error": "You can only select up to 4 badges."}, status=400)

        user_profile = request.user.profile

        UserBadge.objects.filter(user=user_profile).update(displayed=False)
        UserBadge.objects.filter(user=user_profile, badge_id__in=selected_badges).update(displayed=True)

        displayed_badges = Badge.objects.filter(
            id__in=UserBadge.objects.filter(user=user_profile, displayed=True).values("badge_id")
        )

        updated_html = render(request, "cards/partials/displayed_badges.html", {"displayed_badges": displayed_badges}).content.decode("utf-8")

        return JsonResponse({"updated_html": updated_html})

    return JsonResponse({"error": "Invalid request"}, status=400)




def search_users(request):
    query = request.GET.get("search", "").strip()
    profile = request.user.profile

    if query:
        users = Profile.objects.filter(Q(user__username__icontains=query)).exclude(user=request.user)
        friends = profile.get_friends()
        requests = profile.get_requests()
        requested = profile.get_sent_requests()
    else:
        users = Profile.objects.none()


    return render(request, "cards/partials/search_results.html", {
        "users": users,
        "friends": friends,
        "requests": requests,
        "requested": requested,
        })


def send_friend_request(request, user_id):
    sender = request.user.profile
    receiver = get_object_or_404(Profile, id=user_id)

    if Friendship.objects.filter(sender=sender, receiver=receiver).exists():
        return HttpResponse("<p>Request Sent</p>", status=400)

    Friendship.objects.create(sender=sender, receiver=receiver)
    return HttpResponse("<p>Request Sent</p>")


def view_friend_requests(request):
    profile = request.user.profile
    friend_requests = Friendship.objects.filter(receiver=profile, status='pending')
    return render(request, "cards/partials/friend_requests.html", {"friend_requests": friend_requests})


def accept_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id, receiver=request.user.profile)
    friend_request.accept()
    profile = request.user.profile
    profile.friends.add(friend_request.sender)
    friend_request.sender.friends.add(profile)
    return view_friend_requests(request)


def reject_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id, receiver=request.user.profile)
    friend_request.reject()
    return view_friend_requests(request)


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

        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, e.messages[0])
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
    brainbucks = request.user.profile.brainbucks
    badges = Badge.objects.all()
    user_badges = UserBadge.objects.filter(user=request.user.profile)
    purchased_badges = Badge.objects.filter(user_badges__in=user_badges)

    return render(request, 'cards/dashboard.html', {
        'flashcard_sets': flashcard_sets,
        'username': request.user.username,
        'brainbucks': brainbucks,
        'badges': badges,
        'purchased_badges': purchased_badges,
    })


def flashcard_sidebar(request):
    flashcard_sets = FlashcardSet.objects.filter(user=request.user.profile)
    return render(request, 'cards/flashcard_sidebar.html', {'flashcard_sets': flashcard_sets})


def badge_shop(request):
    brainbucks = request.user.profile.brainbucks
    badges = Badge.objects.all()
    user_badges = UserBadge.objects.filter(user=request.user.profile)
    purchased_badges = Badge.objects.filter(user_badges__in=user_badges)
    return render(request, 'cards/badge_shop.html', {
        'badges': badges, 
        'brainbucks': brainbucks,
        'purchased_badges': purchased_badges,
    })


def purchase_badge(request, badge_id):
    badge = get_object_or_404(Badge, id=badge_id)
    user_profile = request.user.profile
    
    UserBadge.objects.create(user=user_profile, badge=badge)
    user_profile.brainbucks -= badge.price
    user_profile.save()

    messages.success(request, f"You successfully purchased the {badge.name} badge!")
    return redirect('dashboard')


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

def create_league(request):
    profile = request.user.profile
    friends = profile.get_friends()

    if request.method == "POST":
        league_name = request.POST.get("league_name")
        selected_friends = request.POST.getlist("friends")

        league = League.objects.create(name=league_name, owner=profile)
        LeagueUser.objects.create(league=league, user=profile)

        for friend_id in selected_friends:
            friend_profile = Profile.objects.get(id=friend_id)
            LeagueUser.objects.create(league=league, user=friend_profile)

        return redirect("profile")

    return render(request, "cards/create_league.html", {"friends": friends})


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
    new_lineup = get_lineup(flashcards, 10)

    # store the lineup and reset the index
    request.session['lineup'] = [card.id for card in new_lineup]
    request.session['current_index'] = 0
    request.session['start_time'] = None
    request.session['correct'] = 0
    request.session['incorrect'] = 0
    
    return redirect('true_false', set_id=set_id)


def true_false(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup_ids = request.session.get('lineup', [])
    if not lineup_ids:
        return redirect('setup_true_false', set_id=set_id)

    flashcards = Flashcard.objects.filter(id__in=lineup_ids)
    flashcard_map = {card.id: card for card in flashcards}
    lineup = [flashcard_map[card_id] for card_id in lineup_ids if card_id in flashcard_map]

    current_index = request.session.get('current_index', 0)

    if current_index >= len(lineup):
        return redirect('game_end', set_id=set_id)
    
    # calculate progress percentage
    total_questions = len(lineup)
    progress_percentage = (current_index / total_questions) * 100

    flashcard = lineup[current_index]
    request.session['current_flashcard_id'] = flashcard.id

    term = flashcard.term

    # randomise the definition
    if random.choice([True, False]) or len(flashcards) == 1:
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
        'progress_percentage': progress_percentage,
    })


def true_false_check(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup_ids = request.session.get('lineup', [])
    flashcards = Flashcard.objects.filter(id__in=lineup_ids)
    flashcard_map = {card.id: card for card in flashcards}
    lineup = [flashcard_map[card_id] for card_id in lineup_ids if card_id in flashcard_map]
    current_index = request.session.get('current_index', 0)

    flashcard = get_object_or_404(Flashcard, id=request.session.get('current_flashcard_id'))

    # get the user's answer and time taken
    user_answer = request.GET.get('answer', 'false') == 'true'
    elapsed_time = int(request.GET.get('time', 0))

    is_correct = request.session.get('is_correct', False)
    
    if user_answer == is_correct:
        if is_correct:
            feedback_message = "✅ Correct! These cards were a match."
        else:
            feedback_message = "✅ Correct! These cards were not a match."
    else:
        if is_correct:
            feedback_message = "❌ Incorrect. These cards were a match."
        else:
            feedback_message = "❌ Incorrect. These cards were not a match."
            
    request.session['feedback_message'] = feedback_message
    request.session['show_feedback'] = True
    request.session['current_flashcard'] = flashcard.id  # Store the flashcard for later use

    evaluate_and_update_flashcard(request, flashcard, flashcard_set, user_answer, is_correct, elapsed_time)

    return redirect('true_false_feedback', set_id=set_id)


def true_false_feedback(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    feedback_message = request.session.get('feedback_message', "No feedback available.")
    show_feedback = request.session.get('show_feedback', False)
    current_flashcard_id = request.session.get('current_flashcard', None)
    flashcard = Flashcard.objects.get(id=current_flashcard_id) if current_flashcard_id else None

    return render(request, 'cards/true_false_feedback.html', {
        'flashcard_set': flashcard_set,
        'feedback_message': feedback_message,
        'show_feedback': show_feedback,
        'flashcard': flashcard,
    })


def true_false_next(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup_ids = request.session.get('lineup', [])
    current_index = request.session.get('current_index', 0)

    if current_index >= len(lineup_ids):
        return redirect('game_end', set_id=set_id)

    # Move to the next question
    request.session['current_index'] = current_index + 1

    # Clear feedback before proceeding
    request.session.pop('feedback_message', None)
    request.session.pop('show_feedback', None)

    return redirect('true_false', set_id=set_id)


def evaluate_and_update_flashcard(request, flashcard, flashcard_set, user_answer, is_correct, elapsed_time):
    if user_answer == is_correct:
        request.session['correct'] += 1
        flashcard.repetition += 1

        if elapsed_time > 1.25 * flashcard_set.baseline:
            print("Slow")
            performance_level = 2
        elif elapsed_time > 0.75 * flashcard_set.baseline:
            print("Average")
            performance_level = 3
        else:
            print("Fast")
            performance_level = 4

        flashcard.ease_factor = ease_factor_calculation(flashcard.ease_factor, performance_level)
        print(f"New ease factor for the flashcard '{flashcard.term}' is: {flashcard.ease_factor:.2f}")
    
    else:
        request.session['incorrect'] += 1
        print("Incorrect")
        performance_level = 1
        flashcard.repetition = 1
    
    if flashcard.repetition == 1:
        flashcard.interval = 86400
    elif flashcard.repetition == 2:
        flashcard.interval = 86400 * 6
    else:
        flashcard.interval = max(min(flashcard.interval * flashcard.ease_factor, 86400 * 365), 86400)

    flashcard.last_reviewed = now()
    flashcard.save()

    # update flashcard set's baseline time
    new_baseline = (flashcard_set.baseline + elapsed_time) / 2
    flashcard_set.baseline = new_baseline
    flashcard_set.save()

    return performance_level


def preprocess_text(text):
    # Tokenize and preprocess the text
    tokens = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    words = [word for word in tokens if word.isalnum() and word not in stop_words]
    return " ".join(words), words

def calculate_tfidf_within_set(definitions):
    # Compute TF-IDF scores for definitions within a set
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(definitions)
    feature_names = vectorizer.get_feature_names_out()
    return tfidf_matrix, feature_names, vectorizer

def select_word_to_blank(definition, tfidf_matrix, feature_names, vectorizer):
    # Preprocess the definition
    preprocessed_definition, words = preprocess_text(definition)
    word_scores = {}
    
    # Get TF-IDF scores for words in the current definition
    if preprocessed_definition:
        definition_vector = vectorizer.transform([preprocessed_definition])
        for word in words:
            if word in feature_names:
                idx = vectorizer.vocabulary_.get(word)
                word_scores[word] = definition_vector[0, idx]
    
    # Select the word with the highest TF-IDF score
    if word_scores:
        return max(word_scores, key=word_scores.get)
    else:
        # Fallback: Random word selection if no scores
        return random.choice(words)


def create_blank_definition_within_set(flashcard, flashcard_set):
    definitions = [card.definition for card in flashcard_set.flashcards.all()]
    
    # calculate TF-IDF
    preprocessed_corpus = [preprocess_text(defn)[0] for defn in definitions]
    tfidf_matrix, feature_names, vectorizer = calculate_tfidf_within_set(preprocessed_corpus)
    
    blanked_word = select_word_to_blank(flashcard.definition, tfidf_matrix, feature_names, vectorizer)
    
    # split the definition
    words = flashcard.definition.split()
    if blanked_word not in words:
        blanked_word = random.choice(words)
    
    # replace the blanked word with an HTML input field
    index = words.index(blanked_word)
    words[index] = '<input type="text" class="blank" name="answer" id="fill-blank" placeholder="Fill the blank" required />'
    blanked_definition = " ".join(words)
    return blanked_definition, blanked_word


def setup_fill_the_blanks(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    flashcards = list(flashcard_set.flashcards.all())
    new_lineup = get_lineup(flashcards, 10)

    # process each flashcard to create blanks in definitions
    blanked_flashcards = []
    for card in new_lineup:
        blanked_definition, blanked_phrase = create_blank_definition_within_set(card, flashcard_set)
        blanked_flashcards.append({
            'id': card.id,
            'term': card.term,
            'blanked_definition': blanked_definition,
            'correct_answer': blanked_phrase,
        })

    # store the processed lineup and reset the index
    request.session['lineup'] = blanked_flashcards
    request.session['current_index'] = 0
    request.session['start_time'] = None

    # keep track of correct and incorrect answers
    request.session['correct'] = 0
    request.session['incorrect'] = 0
    
    return redirect('fill_the_blanks', set_id=set_id)


def fill_the_blanks(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup = request.session.get('lineup', [])
    current_index = request.session.get('current_index', 0)

    if current_index >= len(lineup):
        return redirect('game_end', set_id=set_id)
    
    # get current flashcard details
    current_flashcard = lineup[current_index]
    progress_percentage = (current_index / len(lineup)) * 100

    # store the correct answer in the session for validation later
    request.session['correct_answer'] = current_flashcard['correct_answer']

    return render(request, 'cards/fill_the_blanks.html', {
        'flashcard_set': flashcard_set,
        'flashcard': current_flashcard,
        'progress_percentage': progress_percentage,
    })


def fill_the_blanks_check(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup = request.session.get('lineup', [])
    current_index = request.session.get('current_index', 0)
    flashcard_data = lineup[current_index]
    flashcard = get_object_or_404(Flashcard, id=flashcard_data['id'])

    # get the user's answer, correct answer, and time taken
    user_answer = request.POST.get('answer', '').strip()
    correct_answer = flashcard_data['correct_answer']
    elapsed_time = int(request.POST.get('elapsed_time', 0))

    # evaluate the user's answer and update the flashcard
    correctness = nltk.edit_distance(user_answer.lower(), correct_answer.lower())
    is_correct = correctness <= 1
    evaluate_and_update_flashcard(request, flashcard, flashcard_set, True, is_correct, elapsed_time)

    current_index += 1
    request.session['current_index'] = current_index

    progress_percentage = (request.session['current_index'] / len(lineup)) * 100
    feedback_message = ("✅ Correct!" if correctness == 0  
    else f"✅ Correct! You have a typo, but the answer is '{correct_answer}'." if correctness == 1
    else f"❌ Incorrect. The correct answer is '{correct_answer}'.")

    return JsonResponse({
        'is_correct': is_correct,
        'feedback_message': feedback_message,
        'progress_percentage': progress_percentage,
    })



def setup_quiz(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    # generate a new lineup
    flashcards = list(flashcard_set.flashcards.all())
    new_lineup = get_lineup(flashcards, 10)

    # process each flashcard to create multiple-choice options
    multiple_choice_flashcards = []
    for card in new_lineup:
        # get the correct definition
        correct_definition = card.definition

        # get other flashcards' definitions as incorrect options
        other_cards = [f.definition for f in flashcards if f.id != card.id]
        incorrect_definitions = sample(other_cards, min(3, len(other_cards)))

        # combine correct and incorrect definitions and shuffle
        all_options = incorrect_definitions + [correct_definition]
        shuffle(all_options)

        multiple_choice_flashcards.append({
            'id': card.id,
            'term': card.term,
            'options': all_options,
            'correct_answer': correct_definition,
        })

    # store the processed lineup and reset the index
    request.session['lineup'] = multiple_choice_flashcards
    request.session['current_index'] = 0
    request.session['start_time'] = None

    # keep track of correct and incorrect answers
    request.session['correct'] = 0
    request.session['incorrect'] = 0
    
    return redirect('quiz', set_id=set_id)


def quiz(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup = request.session.get('lineup', [])
    current_index = request.session.get('current_index', 0)

    if current_index >= len(lineup):
        return redirect('game_end', set_id=set_id)
    
    # get current flashcard details
    current_flashcard = lineup[current_index]
    progress_percentage = (current_index / len(lineup)) * 100

    # store the correct answer in the session for validation later
    request.session['correct_answer'] = current_flashcard['correct_answer']

    return render(request, 'cards/quiz.html', {
        'flashcard_set': flashcard_set,
        'flashcard': current_flashcard,
        'progress_percentage': progress_percentage,
    })


def quiz_check(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)
    lineup = request.session.get('lineup', [])
    current_index = request.session.get('current_index', 0)

    if current_index >= len(lineup):
        del request.session['lineup']  # clear lineup when the game ends
        del request.session['current_index']
        return JsonResponse({'redirect': True, 'url': reverse('game_end', args=[set_id])})

    flashcard_data = lineup[current_index]
    flashcard = get_object_or_404(Flashcard, id=flashcard_data['id'])

    user_answer = request.POST.get('selected_answer', '').strip()
    correct_answer = flashcard_data['correct_answer']
    elapsed_time = int(request.POST.get('elapsed_time', 0))
    is_correct = user_answer == correct_answer

    evaluate_and_update_flashcard(request, flashcard, flashcard_set, True, is_correct, elapsed_time)

    request.session['current_index'] += 1
    progress_percentage = (request.session['current_index'] / len(lineup)) * 100
    feedback_message = "✅ Correct!" if is_correct else f"❌ Incorrect. The correct answer is '{correct_answer}'."

    return JsonResponse({
        'is_correct': is_correct,
        'feedback_message': feedback_message,
        'progress_percentage': progress_percentage,
    })


def setup_match(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    # generate a new lineup
    flashcards = list(flashcard_set.flashcards.all())
    new_lineup = get_lineup(flashcards, 6)

    # store the lineup and reset the index
    request.session['lineup'] = [card.id for card in new_lineup]
    request.session['current_index'] = 0
    request.session['correct'] = 0
    request.session['incorrect'] = 0
    request.session['start_time'] = datetime.now().isoformat()

    return redirect('match', set_id=set_id)


def match(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup_ids = request.session.get('lineup', [])
    if not lineup_ids:
        return redirect('setup_match', set_id=set_id)

    flashcards = Flashcard.objects.filter(id__in=lineup_ids)
    flashcard_map = {card.id: card for card in flashcards}
    flashcards = [flashcard_map[card_id] for card_id in lineup_ids if card_id in flashcard_map]

    items = []
    for flashcard in flashcards:
        items.append({'id': flashcard.id, 'value': flashcard.term})
        items.append({'id': flashcard.id, 'value': flashcard.definition})

    random.shuffle(items)

    return render(request, 'cards/match.html', {
        'flashcard_set': flashcard_set,
        'items': items,
    })


def evaluate_match(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    flashcard_id = request.GET.get('first_id')
    is_correct = request.GET.get('is_correct') == 'true'
    elapsed_time = int(request.GET.get('time', 0))

    flashcard = get_object_or_404(Flashcard, id=flashcard_id)

    evaluate_and_update_flashcard(request, flashcard, flashcard_set, True, is_correct, elapsed_time)

    return JsonResponse({'success': True, 'message': 'Evaluation complete'})


def clear_feedback(request):
    request.session.pop('feedback', None)
    return JsonResponse({'success': True})


def game_end(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)
    start_time_str = request.session.get('start_time')
    correct = request.session.get('correct', 0)
    incorrect = request.session.get('incorrect', 0)
    score = 0
    request.session['reward_given'] = False

    if start_time_str:
        start_time = datetime.fromisoformat(start_time_str)
        total_time = (datetime.now() - start_time).total_seconds()

        if flashcard_set.quickest_time is None or total_time < flashcard_set.quickest_time:
            flashcard_set.quickest_time = total_time
            flashcard_set.save()

        score = 50

    else:
        total_time = None
        score = correct/(correct+incorrect)*100

    brainbuck_reward = int(score / 10) if score > 0 else 0
    
    if not request.session.get('reward_given'):
        request.user.profile.brainbucks += brainbuck_reward
        request.user.profile.save()
        request.session['reward_given'] = True

    return render(request, 'cards/game_end.html', {
        'flashcard_set': flashcard_set,
        'total_time': total_time,
        'score':score,
        'brainbuck_reward': brainbuck_reward,
        'quickest_time': flashcard_set.quickest_time,
    })

def edit_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, pk=set_id)

    if request.method == 'POST':
        set_title = FlashcardSetTitle(request.POST, instance=flashcard_set)
        set_contents = FlashcardTermDefs(request.POST, instance=flashcard_set)

        if set_title.is_valid() and set_contents.is_valid():
            set_title.save()
            set_contents.save()
            return redirect('dashboard')

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
