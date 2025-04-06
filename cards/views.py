
# The view will assemble requested data and style it before generating a HTTP response

import json
import sys
import time
from datetime import datetime, timedelta
import random
from random import sample, shuffle
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy, reverse
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import SignUpForm, FlashcardSetTitle, FlashcardTermDefs
from django.forms import modelform_factory, modelformset_factory
from django.contrib import messages
from django import forms
from django.core.mail import send_mail
from django.conf import settings
import uuid
from .models import FlashcardSet, Flashcard, Badge, UserBadge, Profile, Friendship, League, LeagueUser
from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import Case, When, Q
from spaced_repetition import get_lineup, get_overdue_flashcards, ease_factor_calculation
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model

import os
from django.http import HttpResponse

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


def email_verified_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.profile.is_verified:
            return redirect('verify_email_prompt')
        return view_func(request, *args, **kwargs)
    return wrapper



def landing_page(request):
    return render(request, 'cards/landing.html')

def about(request):
    return render(request, 'cards/about.html')

@email_verified_required
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

    leagues = request.user.profile.get_leagues()

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

        # validation checks
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

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password
                )

                if hasattr(user, 'profile'):
                    profile = user.profile
                    profile.verification_token = str(uuid.uuid4())
                    profile.is_verified = False
                else:
                    profile = Profile.objects.create(
                        user=user,
                        verification_token=str(uuid.uuid4()),
                        is_verified=False
                    )

                profile.save()

                verification_link = f"{settings.SITE_URL}/verify-email/{profile.verification_token}/"
                send_mail(
                    'BrainSpace: Verify Your Email',
                    f'Click the link to verify your email: {verification_link}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )

                messages.success(request, "Registration successful! Check your email for verification.")
                login(request, user)
                return redirect('dashboard')

        except IntegrityError as e:
            if User.objects.filter(username=username).exists():
                User.objects.filter(username=username).delete()
            messages.error(request, "Registration failed due to database error. Please try again.")
            return redirect('signup')

        except Exception as e:
            if User.objects.filter(username=username).exists():
                User.objects.filter(username=username).delete()
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect('signup')

    return render(request, 'cards/signup.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if not user.profile.is_verified:
                return redirect('verify_email_prompt')
            return redirect('dashboard')
        else:
            messages.error(request, "Incorrect username or password.")
            return redirect('login')

    return render(request, 'cards/login.html')


@login_required
def verify_email_prompt(request):
    return render(request, 'cards/verify_email_prompt.html')


def verify_email(request, token):
    try:
        profile = Profile.objects.get(verification_token=token)

        profile.is_verified = True
        profile.verification_token = None
        profile.save()

        messages.success(request, "Your email has been successfully verified!")
        return redirect('login')

    except Profile.DoesNotExist:
        messages.error(request, "Invalid verification link. Please request a new verification email.")
        return redirect('verify_email_prompt')

    except Exception as e:
        messages.error(request, "An error occurred during verification. Please try again.")
        return redirect('verify_email_prompt')


def resend_verification_email(request):
    profile = request.user.profile
    if not profile.is_verified:
        # Generate a new verification token
        verification_token = str(uuid.uuid4())
        profile.verification_token = verification_token
        profile.save()

        verification_link = f"{settings.SITE_URL}/verify-email/{verification_token}/"
        try:
            send_mail(
                'BrainSpace: Verify Your Email',
                f'Click the link to verify your email: {verification_link}',
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email],
                fail_silently=False,
            )
            messages.success(request, "A verification email has been sent to your email address.")
        except Exception as e:
            messages.error(request, f"Failed to send verification email: {str(e)}")
    else:
        messages.warning(request, "Your email is already verified.")

    return redirect('verify_email_prompt')


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


def league(request, league_id):
    league = get_object_or_404(League, id=league_id)
    reset_time = max(league.last_rewarded + timedelta(weeks=1) - now(), timedelta(0))
    days = reset_time.days
    hours, remainder = divmod(reset_time.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    previous_top_users = json.loads(league.previous_top_users) if league.previous_top_users else []
    return render(request, 'cards/league.html', {
        'league': league,
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'previous_top_users': previous_top_users,
        })


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
    request.session['skipped'] = 0

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

    if request.GET.get('skip') == 'true':
        feedback_message = "⚠️ You skipped this card."
        request.session['feedback_message'] = feedback_message
        request.session['show_feedback'] = True
        request.session['current_flashcard'] = flashcard.id
        request.session['skipped'] = request.session.get('skipped', 0) + 1

        evaluate_and_update_flashcard(request, flashcard, flashcard_set, skipped=True)

        return redirect('true_false_feedback', set_id=set_id)


    # get the user's answer and time taken
    user_answer = request.GET.get('answer', 'false') == 'true'
    elapsed_time = int(request.GET.get('time', 0))

    is_correct = request.session.get('is_correct', False)

    if user_answer == is_correct:
        if is_correct:
            feedback_message = "✅ Correct! These cards were a match."
        else:
            feedback_message = "✅ Correct! The cards were not a match. Here is the pair:"
    else:
        if is_correct:
            feedback_message = "❌ Incorrect. These cards were a match."
        else:
            feedback_message = "❌ Incorrect. These cards were not a match. Here is the pair:"

    request.session['feedback_message'] = feedback_message
    request.session['show_feedback'] = True
    request.session['current_flashcard'] = flashcard.id  # store the flashcard for later use

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

    # move to the next question
    request.session['current_index'] = current_index + 1

    # clear feedback before proceeding
    request.session.pop('feedback_message', None)
    request.session.pop('show_feedback', None)

    return redirect('true_false', set_id=set_id)


def evaluate_and_update_flashcard(request, flashcard, flashcard_set, user_answer=None, is_correct=None, elapsed_time=0, skipped=False):
    if skipped:
        return handle_skipped_flashcard(flashcard, flashcard_set, elapsed_time)

    performance_level = update_performance_and_stats(request, flashcard, flashcard_set, user_answer, is_correct, elapsed_time)
    update_flashcard_interval(flashcard)
    update_review_timing(flashcard, flashcard_set, elapsed_time)

    flashcard.save()
    flashcard_set.save()

    return performance_level


def handle_skipped_flashcard(flashcard, flashcard_set, elapsed_time):
    flashcard.repetition = 1
    flashcard.interval = 86400  # 1 day
    flashcard.last_reviewed = now()
    flashcard_set.baseline = (flashcard_set.baseline + elapsed_time) / 2
    flashcard.save()
    flashcard_set.save()
    return 0


def update_performance_and_stats(request, flashcard, flashcard_set, user_answer, is_correct, elapsed_time):
    if user_answer == is_correct:
        request.session['correct'] += 1
        flashcard.repetition += 1

        if elapsed_time > 1.25 * flashcard_set.baseline:
            performance_level = 2
        elif elapsed_time > 0.75 * flashcard_set.baseline:
            performance_level = 3
        else:
            performance_level = 4

        flashcard.ease_factor = ease_factor_calculation(flashcard.ease_factor, performance_level)
    else:
        request.session['incorrect'] += 1
        flashcard.repetition = 1
        performance_level = 1

    return performance_level


def update_flashcard_interval(flashcard):
    if flashcard.repetition == 1:
        flashcard.interval = 86400  # 1 day
    elif flashcard.repetition == 2:
        flashcard.interval = 86400 * 6  # 6 days
    else:
        flashcard.interval = max(min(flashcard.interval * flashcard.ease_factor, 86400 * 365), 86400)


def update_review_timing(flashcard, flashcard_set, elapsed_time):
    flashcard.last_reviewed = now()
    flashcard_set.baseline = (flashcard_set.baseline + elapsed_time) / 2
    flashcard_set.save()


def preprocess_text(text):
    # preprocess the text
    tokens = word_tokenize(text.lower())
    stop_words = set(stopwords.words('english'))
    words = [word for word in tokens if word.isalnum() and word not in stop_words]
    return " ".join(words), words

# compute TF-IDF scores for definitions within a set
def calculate_tfidf_within_set(definitions):
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(definitions)
    feature_names = vectorizer.get_feature_names_out()
    return tfidf_matrix, feature_names, vectorizer

def select_word_to_blank(definition, tfidf_matrix, feature_names, vectorizer):
    # preprocess the definition
    preprocessed_definition, words = preprocess_text(definition)
    word_scores = {}

    # get TF-IDF scores for words in the current definition
    if preprocessed_definition:
        definition_vector = vectorizer.transform([preprocessed_definition])
        for word in words:
            if word in feature_names:
                idx = vectorizer.vocabulary_.get(word)
                word_scores[word] = definition_vector[0, idx]

    # select the word with the highest TF-IDF score
    top_n = 3
    if word_scores:
        sorted_words = sorted(word_scores.items(), key=lambda item: item[1], reverse=True)
        top_words = [word for word, score in sorted_words[:top_n]]

        # randomly pick a word from the top n TF-IDF words to create some variance
        return random.choice(top_words)
    else:
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
    words[index] = '<input type="text" class="blank" name="answer" id="fill-blank" tabindex="1" placeholder="Fill the blank" required />'
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
    request.session['skipped'] = 0

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

    # check if user skipped the question
    skipped = request.POST.get('skipped', 'false') == 'true'

    if skipped:
        is_correct = False
        request.session['skipped'] = request.session.get('skipped', 0) + 1
        feedback_message = f"⚠️ Skipped. The correct answer is '{flashcard_data['correct_answer']}'."
    else:
        user_answer = request.POST.get('answer', '').strip()
        correct_answer = flashcard_data['correct_answer']
        elapsed_time = int(request.POST.get('elapsed_time', 0))

        # evaluate the user's answer
        correctness = nltk.edit_distance(user_answer.lower(), correct_answer.lower())
        is_correct = correctness <= 1
        feedback_message = ("✅ Correct!" if correctness == 0
        else f"✅ Correct! You have a typo, but the answer is '{correct_answer}'." if correctness == 1
        else f"❌ Incorrect. The correct answer is '{correct_answer}'.")

        evaluate_and_update_flashcard(request, flashcard, flashcard_set, True, is_correct, elapsed_time)

    # update the current index
    current_index += 1
    request.session['current_index'] = current_index
    progress_percentage = (current_index / len(lineup)) * 100

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

    # check if the question was skipped
    skipped = request.POST.get('skipped', 'false') == 'true'

    if skipped:
        is_correct = False
        feedback_message = f"⚠️ Skipped. The correct answer is '{flashcard_data['correct_answer']}'."
        elapsed_time = 0
    else:

        user_answer = request.POST.get('selected_answer', '').strip()
        correct_answer = flashcard_data['correct_answer']
        elapsed_time = int(request.POST.get('elapsed_time', 0))
        is_correct = user_answer == correct_answer

        feedback_message = "✅ Correct!" if is_correct else f"❌ Incorrect. The correct answer is '{correct_answer}'."

    evaluate_and_update_flashcard(request, flashcard, flashcard_set, True, is_correct, elapsed_time)

    request.session['current_index'] += 1
    progress_percentage = (request.session['current_index'] / len(lineup)) * 100

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
    user_profile = request.user.profile
    league_users = LeagueUser.objects.filter(user=user_profile)
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=user_profile)
    start_time_str = request.session.get('start_time')
    correct = request.session.get('correct', 0)
    incorrect = request.session.get('incorrect', 0)
    skipped = request.session.get('skipped', 0)
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
        score = correct/(correct+incorrect+skipped)*100

    brainbuck_reward = int(score / 10) if score > 0 else 0

    if not request.session.get('reward_given'):
        user_profile.brainbucks += brainbuck_reward
        for league_user in league_users:
            league_user.update_score(score)
        user_profile.save()
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


@login_required
def settings_page(request):
    return render(request, 'cards/settings.html')

@login_required
def change_email(request):
    if request.method == 'POST':
        new_email = request.POST.get('new_email')

        try:
            # check if the new email is already in use
            if User.objects.filter(email=new_email).exists():
                messages.error(request, "This email is already in use.")
            else:
                # Update the email
                request.user.email = new_email
                request.user.save()

                # generate a new verification token
                profile = request.user.profile
                verification_token = str(uuid.uuid4())
                profile.verification_token = verification_token
                profile.is_verified = False  # Mark email as unverified
                profile.save()

                verification_link = f"{settings.SITE_URL}/verify-email/{verification_token}/"
                try:
                    send_mail(
                        'BrainSpace: Verify Your Email',
                        f'Click the link to verify your email: {verification_link}',
                        settings.DEFAULT_FROM_EMAIL,
                        [new_email], 
                        fail_silently=False,
                    )
                    messages.success(request, "Your email has been updated. A verification email has been sent to your new email address.")
                except Exception as e:
                    messages.error(request, f"Failed to send verification email: {str(e)}")
                    return redirect('verify_email_prompt')

        except ValidationError:
            messages.error(request, "Invalid email address.")

    return redirect('verify_email_prompt')


@login_required
def change_username(request):
    if request.method == 'POST':
        new_username = request.POST.get('new_username')

        if User.objects.filter(username=new_username).exists():
            messages.error(request, "This username is already taken.")
        else:
            request.user.username = new_username
            request.user.save()
            messages.success(request, "Your username has been updated.")

    return redirect('settings_page')

@login_required
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not request.user.check_password(old_password):
            messages.error(request, "Your current password is incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "The new passwords do not match.")
        else:
            try:
                validate_password(new_password)
            except ValidationError as e:
                messages.error(request, e.messages[0])
                return redirect('settings_page')

            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)  # keep the user logged in
            messages.success(request, "Your password has been updated.")

    return redirect('settings_page')

@login_required
def delete_account(request):
    if request.method == 'POST':
        request.user.delete()
        logout(request)
        return redirect('landing')

    return redirect('settings_page')


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No user found with this email address.")
            return redirect('forgot_password')

        # generate a password reset token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # create the reset link
        reset_link = request.build_absolute_uri(
            reverse('reset_password_confirm', kwargs={'uidb64': uid, 'token': token})
        )

        try:
            send_mail(
                'BrainSpace: Password Reset Request',
                f'Click the link to reset your password: {reset_link}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            messages.success(request, "A password reset link has been sent to your email address.")
            return redirect('login')
        except Exception as e:
            messages.error(request, f"Failed to send email: {str(e)}")
            return redirect('forgot_password')

    return render(request, 'cards/forgot_password.html')


def reset_password_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = get_user_model().objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)  # Keep the user logged in
                messages.success(request, "Your password has been reset successfully.")
                return redirect('login')
    else:
        messages.error(request, "Invalid or expired password reset link.")
        return redirect('forgot_password')

    return render(request, 'cards/reset_password_confirm.html', {'uidb64': uidb64, 'token': token})
