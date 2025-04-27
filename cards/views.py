
# The view will assemble requested data and style it before generating a HTTP response

# standard library imports
import json
import uuid
import random
from random import sample, shuffle
from datetime import datetime, timedelta

# django core imports
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import FlashcardSetTitle, FlashcardTermDefs
from django.forms import modelform_factory, modelformset_factory
from django.contrib import messages
from django import forms
from django.core.mail import send_mail
from django.conf import settings
import uuid
from .models import FlashcardSet, Flashcard, Badge, UserBadge, Profile, Friendship, League, LeagueUser
from django.db import transaction
from django.db.utils import IntegrityError
from django.db.models import Q
from spaced_repetition import get_lineup, ease_factor_calculation
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model

import nltk
nltk.download('punkt_tab')
nltk.download('wordnet')
nltk.download('omw-1.4')
nltk.download('stopwords')
from sklearn.feature_extraction.text import TfidfVectorizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords


# custom wrappers

# decorator to check if the user has verified their email before accessing certain views
def email_verified_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.profile.is_verified:
            return redirect('verify_email_prompt')
        return view_func(request, *args, **kwargs)
    return wrapper


#------------------------------------------------------------------------------------------------------------
# spaced repetition functions

# evaluates and updates flashcard performance based on user answer or if skipped
def evaluate_and_update_flashcard(request, flashcard, flashcard_set, user_answer=None, is_correct=None, elapsed_time=0, skipped=False):
    if skipped:
        return handle_skipped_flashcard(flashcard, flashcard_set, elapsed_time)

    # if the user answered the flashcard, update the performance stats
    performance_level = update_performance_and_stats(request, flashcard, flashcard_set, user_answer, is_correct, elapsed_time)
    update_flashcard_interval(flashcard)
    update_review_timing(flashcard, flashcard_set, elapsed_time)

    flashcard.save()
    flashcard_set.save()

    return performance_level


# handles the skipped flashcard scenario, resetting repetition and adjusting baseline time
def handle_skipped_flashcard(flashcard, flashcard_set, elapsed_time):
    flashcard.repetition = 1
    flashcard.interval = 86400  # 1 day
    update_review_timing(flashcard, flashcard_set, elapsed_time)
    flashcard_set.save()
    return 0


# updates performance stats, repetition, and ease factor based on user answer and elapsed time
def update_performance_and_stats(request, flashcard, flashcard_set, user_answer, is_correct, elapsed_time):
    if user_answer == is_correct:
        request.session['correct'] += 1 # increment correct answers
        flashcard.repetition += 1

        # the performance level is determined based on the elapsed time compared to the baseline time
        if elapsed_time > 1.25 * flashcard_set.baseline:
            performance_level = 2
        elif elapsed_time > 0.75 * flashcard_set.baseline:
            performance_level = 3
        else:
            performance_level = 4

        flashcard.ease_factor = ease_factor_calculation(flashcard.ease_factor, performance_level)

    # if the user answered incorrectly, reset the repetition and set performance level to 1
    else:
        request.session['incorrect'] += 1 # increment incorrect answers
        flashcard.repetition = 1
        performance_level = 1

    return performance_level


# updates the review interval based on repetition and ease factor
def update_flashcard_interval(flashcard):
    if flashcard.repetition == 1:
        flashcard.interval = 86400  # 1 day
    elif flashcard.repetition == 2:
        flashcard.interval = 86400 * 6  # 6 days
    else:
        flashcard.interval = max(min(flashcard.interval * flashcard.ease_factor, 86400 * 365), 86400) # cap at 1 year


# updates the last review time and adjusts the flashcard set's baseline time
def update_review_timing(flashcard, flashcard_set, elapsed_time):
    flashcard.last_reviewed = now()
    flashcard_set.baseline = (flashcard_set.baseline + elapsed_time) / 2 # adjust the baseline time with new average
    flashcard_set.save()

#------------------------------------------------------------------------------------------------------------
# validation and verification functions

# handles user signup, including email verification and password validation
def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')


        # validation checks
        # checks if the username and email are already taken
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return redirect('signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return redirect('signup')

        # uses the custom password validation function to check the password strength
        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, e.messages[0])
            return redirect('signup')

        # checks if the password and confirm password match
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('signup')


        # create the user and profile, and send verification email
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

                # create a verification link and send it to the user's email
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


# checks the user's credentials and logs them in
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password) # authenticate the user

        if user is not None:
            login(request, user)

            # if user is not verified, redirect to verification prompt
            if not user.profile.is_verified:
                return redirect('verify_email_prompt')
            
            return redirect('dashboard')
        
        else:
            messages.error(request, "Incorrect username or password.")
            return redirect('login')

    return render(request, 'cards/login.html')


# logs the user out and redirects to the login page
@login_required
def user_logout(request):
    logout(request)
    return redirect('login')


#------------------------------------------------------------------------------------------------------------
# email related functions

# renders the email verification prompt page
@login_required
def verify_email_prompt(request):
    return render(request, 'cards/verify_email_prompt.html')


# verifies the user's email using the token sent to their email address
def verify_email(request, token):
    try:
        profile = Profile.objects.get(verification_token=token)
        profile.is_verified = True
        profile.verification_token = None
        profile.save()

        messages.success(request, "Your email has been successfully verified!")
        return redirect('login')

    # if the token is invalid or expired, redirect to the verification prompt page
    except Profile.DoesNotExist:
        messages.error(request, "Invalid verification link. Please request a new verification email.")
        return redirect('verify_email_prompt')

    except Exception as e:
        messages.error(request, "An error occurred during verification. Please try again.")
        return redirect('verify_email_prompt')


# triggers the sending of a new verification email to the user
def resend_verification_email(request):
    profile = request.user.profile
    if not profile.is_verified:
        verification_token = str(uuid.uuid4()) # generate a new verification token
        profile.verification_token = verification_token
        profile.save()

        # create a new verification link and send it to the user's email
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

#------------------------------------------------------------------------------------------------------------
# general page rendering functions


# renders the dashboard page with flashcard sets, brainbucks, and badges
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


# renders the flashcard sidebar with a list of flashcard sets belonging to the user
def flashcard_sidebar(request):
    flashcard_sets = FlashcardSet.objects.filter(user=request.user.profile)
    return render(request, 'cards/flashcard_sidebar.html', {'flashcard_sets': flashcard_sets})


# renders the landing page
def landing_page(request):
    return render(request, 'cards/landing.html')


# renders the about page
def about(request):
    return render(request, 'cards/about.html')


# renders the profile page with user badges, friends, and leagues
@email_verified_required
def profile(request):
    # gets all badges belonging to the user and filters them based on whether they are displayed or not
    displayed_badges = Badge.objects.filter(id__in=UserBadge.objects.filter(user=request.user.profile, displayed=True).values("badge_id"))
    owned_badges = Badge.objects.filter(id__in=UserBadge.objects.filter(user=request.user.profile).values("badge_id"))

    # gets all friends of the user
    friend_profiles = request.user.profile.get_friends()
    friends = User.objects.filter(profile__in=friend_profiles)

    # gets all badges for each friend and stores them in a list
    friends_with_badges = []
    for friend in friends:
        friend_badges = Badge.objects.filter(id__in=UserBadge.objects.filter(user=friend.profile, displayed=True).values("badge_id"))
        friends_with_badges.append({
            'friend': friend,
            'badges': friend_badges
        })

    # gets all leagues the user is a part of
    leagues = request.user.profile.get_leagues()

    return render(request, 'cards/profile.html', {
        'displayed_badges': displayed_badges,
        'owned_badges': owned_badges,
        'friends_with_badges': friends_with_badges,
        'leagues': leagues,
    })


# renders the settings page
@login_required
def settings_page(request):
    return render(request, 'cards/settings.html')


# renders the study page for a specific flashcard set
@login_required
@email_verified_required
def study_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)
    flashcards = flashcard_set.flashcards.all()
    return render(request, 'cards/study.html', {
        'flashcard_set': flashcard_set,
        'flashcards': flashcards,
    })


#------------------------------------------------------------------------------------------------------------
# badge related functions

# renders the badge selection partial template for the user to choose which badges to display
def select_badges(request):
    user_badges = UserBadge.objects.filter(user=request.user.profile)
    return render(request, "cards/partials/select_badges.html", {"all_badges": user_badges})


# updates the displayed badges based on user selection
def update_displayed_badges(request):
    if request.method == "POST":
        selected_badges = request.POST.getlist("selected_badges")

        # limit the number of selected badges to 4
        if len(selected_badges) > 4:
            return JsonResponse({"error": "You can only select up to 4 badges."}, status=400)

        user_profile = request.user.profile

        # update the displayed status of badges
        UserBadge.objects.filter(user=user_profile).update(displayed=False)
        UserBadge.objects.filter(user=user_profile, badge_id__in=selected_badges).update(displayed=True)

        displayed_badges = Badge.objects.filter(
            id__in=UserBadge.objects.filter(user=user_profile, displayed=True).values("badge_id")
        )

        # render the updated badges HTML
        updated_html = render(request, "cards/partials/displayed_badges.html", {"displayed_badges": displayed_badges}).content.decode("utf-8")

        return JsonResponse({"updated_html": updated_html})

    return JsonResponse({"error": "Invalid request"}, status=400)


# renders the badge shop page with available badges and user's brainbucks
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


# handles the purchase of a badge by the user
def purchase_badge(request, badge_id):
    badge = get_object_or_404(Badge, id=badge_id)
    user_profile = request.user.profile
    UserBadge.objects.create(user=user_profile, badge=badge) # create a new UserBadge instance for the user and badge
    user_profile.brainbucks -= badge.price # deduct the badge price from user's brainbucks
    user_profile.save()

    messages.success(request, f"You successfully purchased the {badge.name} badge!")
    return redirect('dashboard')



#------------------------------------------------------------------------------------------------------------
# friendship related functions

# renders the search results for users based on the search query
def search_users(request):
    query = request.GET.get("search", "").strip()
    profile = request.user.profile

    # gets a list of users matching the search query, excluding the current user
    if query:
        users = Profile.objects.filter(Q(user__username__icontains=query)).exclude(user=request.user)
        friends = profile.get_friends() # for marking users as friends
        requests = profile.get_requests() # for informing users about requests
        requested = profile.get_sent_requests() # for marking users as requested
    else:
        users = Profile.objects.none()


    return render(request, "cards/partials/search_results.html", {
        "users": users,
        "friends": friends,
        "requests": requests,
        "requested": requested,
    })


# sends a friend request to another user
def send_friend_request(request, user_id):
    sender = request.user.profile
    receiver = get_object_or_404(Profile, id=user_id)

    # displays a message to show that the request has already been sent
    if Friendship.objects.filter(sender=sender, receiver=receiver).exists():
        return HttpResponse("<p>Request Sent</p>", status=400)

    Friendship.objects.create(sender=sender, receiver=receiver) # create a new Friendship instance for the sender and receiver
    return HttpResponse("<p>Request Sent</p>")


# renders the friend requests page with a list of pending requests
def view_friend_requests(request):
    profile = request.user.profile
    friend_requests = Friendship.objects.filter(receiver=profile, status='pending')
    return render(request, "cards/partials/friend_requests.html", {"friend_requests": friend_requests})


# accepts a friend request from another user
def accept_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id, receiver=request.user.profile)
    friend_request.accept() # function to change the status of the request to accepted
    return view_friend_requests(request)


# rejects a friend request from another user
def reject_friend_request(request, request_id):
    friend_request = get_object_or_404(Friendship, id=request_id, receiver=request.user.profile)
    friend_request.reject() # function to change the status of the request to rejected
    return view_friend_requests(request)


#------------------------------------------------------------------------------------------------------------
# flashcard management functions

# creates a new flashcard set and its contents
@login_required
def create(request):
    # formset for the flashcard set title
    FlashcardSetTitle = modelform_factory(
        FlashcardSet,
        fields=['name'],
        widgets={'name': forms.TextInput(attrs={'placeholder': 'Title', 'class': 'form-control'})}
    )

    # formset for the flashcard terms and definitions
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

    # if the request method is POST, process the form data
    if request.method == 'POST':
        set_title = FlashcardSetTitle(request.POST)
        set_contents = FlashcardTermDefs(request.POST, queryset=Flashcard.objects.none())

        if set_title.is_valid() and set_contents.is_valid():
            all_filled = True
            for form in set_contents:
                # cleans the data and checks if all fields are filled
                if form.cleaned_data:
                    term = form.cleaned_data.get('term')
                    definition = form.cleaned_data.get('definition')

                    if not term or not definition:
                        all_filled = False
                        form.add_error(None, "Both term and definition are required.")

            # if all terms and definitions are filled, save the flashcard set and its contents
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

    return render(request, 'cards/create.html', {
        'set_title': set_title,
        'formset': set_contents,
        })


# handles the editing of an existing flashcard set and its contents
@login_required
@email_verified_required
def edit_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, pk=set_id)

    # takes the inputted title and contents of the flashcard set
    if request.method == 'POST':
        set_title = FlashcardSetTitle(request.POST, instance=flashcard_set)
        set_contents = FlashcardTermDefs(request.POST, instance=flashcard_set)

        if set_title.is_valid() and set_contents.is_valid():
            set_title.save()
            set_contents.save()
            return redirect('dashboard')

    # populates the formset with the existing flashcard set data
    else:
        set_title = FlashcardSetTitle(instance=flashcard_set)
        set_contents = FlashcardTermDefs(instance=flashcard_set)

    return render(request, 'cards/edit.html', {
        'set_title': set_title,
        'flashcard_formset': set_contents,
        'flashcard_set': flashcard_set,
    })


# deletes a flashcard set and its contents
def delete_set(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    if request.method == 'POST':
        flashcard_set.delete() # delete the flashcard set, and the contents is deleted through cascade deletion
        messages.success(request, 'Flashcard set deleted successfully.')
        return redirect('dashboard')

    return redirect('dashboard')


#------------------------------------------------------------------------------------------------------------
# league related functions

# creates a new league with participating friends
@login_required
@email_verified_required
def create_league(request):
    profile = request.user.profile
    friends = profile.get_friends() # gets the user's friends as potential league members

    # if the request method is POST, process the form data
    if request.method == "POST":
        league_name = request.POST.get("league_name") # gets the league name from the form
        selected_friends = request.POST.getlist("friends") # gets the selected friends from the form

        league = League.objects.create(name=league_name, owner=profile)
        LeagueUser.objects.create(league=league, user=profile)

        # create LeagueUser instances for each selected friend
        for friend_id in selected_friends:
            friend_profile = Profile.objects.get(id=friend_id)
            LeagueUser.objects.create(league=league, user=friend_profile)

        return redirect("profile")

    return render(request, "cards/create_league.html", {"friends": friends})


# renders the league page with current leaderboard, reset time, and previous top users
@login_required
@email_verified_required
def league(request, league_id):
    league = get_object_or_404(League, id=league_id)

    # calculate the time until the next reset
    reset_time = max(league.last_rewarded + timedelta(weeks=1) - now(), timedelta(0))
    days = reset_time.days
    hours, remainder = divmod(reset_time.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    # get the podium of previous top users
    previous_top_users = json.loads(league.previous_top_users) if league.previous_top_users else []

    return render(request, 'cards/league.html', {
        'league': league,
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'previous_top_users': previous_top_users,
    })


#------------------------------------------------------------------------------------------------------------
# true or false mini game functions

# sets up the true or false game by generating a new lineup of flashcards
@login_required
@email_verified_required
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


# renders the true or false game page with the current flashcard and progress percentage
@login_required
@email_verified_required
def true_false(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    # gets the current lineup of flashcards from the session
    lineup_ids = request.session.get('lineup', [])
    if not lineup_ids:
        return redirect('setup_true_false', set_id=set_id)

    flashcards = Flashcard.objects.filter(id__in=lineup_ids)
    flashcard_map = {card.id: card for card in flashcards}
    lineup = [flashcard_map[card_id] for card_id in lineup_ids if card_id in flashcard_map]

    current_index = request.session.get('current_index', 0)

    # redirect to the end of the game if the current index exceeds the lineup length
    if current_index >= len(lineup):
        return redirect('game_end', set_id=set_id)

    # calculate progress percentage
    total_questions = len(lineup)
    progress_percentage = (current_index / total_questions) * 100

    flashcard = lineup[current_index]
    request.session['current_flashcard_id'] = flashcard.id

    term = flashcard.term

    # randomise the definition with a 50% chance of being correct or incorrect
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


# performs answer checking and produces feedback based on the user's answer
@login_required
@email_verified_required
def true_false_check(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)
    flashcard = get_object_or_404(Flashcard, id=request.session.get('current_flashcard_id'))

    # handle skipping the flashcard
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

    # generate feedback message based on the user's answer and correctness
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


# renders the feedback page after the user answers a question
@login_required
@email_verified_required
def true_false_feedback(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    # retrieve the feedback message and flashcard from the session
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


# triggers the next question in the true or false game
@login_required
@email_verified_required
def true_false_next(request, set_id):
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



#------------------------------------------------------------------------------------------------------------
# fill the blanks mini game functions

# preprocesses the definition text for blanking by tokenising, removing stop words, and normalising
def preprocess_text(text):
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


# select a word to blank based on its TF-IDF score
def select_word_to_blank(definition, tfidf_matrix, feature_names, vectorizer):
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

        if top_words:
            return random.choice(top_words)
        else:
            return random.choice(words)  # fall back to a random word
    else:
        # if no words in word_scores, fall back to random word from the input words list
        return random.choice(words)


# creates the definition with a blanked word for the game
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


# triggers the setup for the fill the blanks game
@login_required
@email_verified_required
def setup_fill_the_blanks(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    # generate a new lineup
    flashcards = list(flashcard_set.flashcards.all())
    new_lineup = get_lineup(flashcards, 10)

    # process each flashcard in the lineup to create blanks in definitions
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


# renders the fill the blanks game page with the current flashcard and progress percentage
def fill_the_blanks(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup = request.session.get('lineup', [])
    current_index = request.session.get('current_index', 0)

    # redirect to the end of the game if the current index exceeds the lineup length
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


# checks the user's answer for the fill the blanks game and generates feedback
def fill_the_blanks_check(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup = request.session.get('lineup', [])
    current_index = request.session.get('current_index', 0)
    flashcard_data = lineup[current_index]
    flashcard = get_object_or_404(Flashcard, id=flashcard_data['id'])

    # check if user skipped the question
    skipped = request.POST.get('skipped', 'false') == 'true'

    # handle skipping the flashcard
    if skipped:
        is_correct = False
        request.session['skipped'] = request.session.get('skipped', 0) + 1
        feedback_message = f"⚠️ Skipped. The correct answer is '{flashcard_data['correct_answer']}'."

    # otherwise, check the user's answer
    else:
        user_answer = request.POST.get('answer', '').strip()
        correct_answer = flashcard_data['correct_answer']
        elapsed_time = int(request.POST.get('elapsed_time', 0))

        # evaluate the user's answer
        correctness = nltk.edit_distance(user_answer.lower(), correct_answer.lower()) # allow for typos
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



#------------------------------------------------------------------------------------------------------------
# quiz mini game functions

# sets up the quiz game by generating a new lineup of flashcards and multiple choice options
@login_required
@email_verified_required
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


# renders the quiz game page with the current flashcard and progress percentage
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


# checks the user's answer for the quiz game and generates feedback
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

    # handle skipping the flashcard
    if skipped:
        is_correct = False
        feedback_message = f"⚠️ Skipped. The correct answer is '{flashcard_data['correct_answer']}'."
        elapsed_time = 0
    
    # otherwise, check the user's answer
    else:
        user_answer = request.POST.get('selected_answer', '').strip()
        correct_answer = flashcard_data['correct_answer']
        elapsed_time = int(request.POST.get('elapsed_time', 0))
        is_correct = user_answer == correct_answer

        feedback_message = "✅ Correct!" if is_correct else f"❌ Incorrect. The correct answer is '{correct_answer}'."

    evaluate_and_update_flashcard(request, flashcard, flashcard_set, True, is_correct, elapsed_time)

    # updates progress through the game
    request.session['current_index'] += 1
    progress_percentage = (request.session['current_index'] / len(lineup)) * 100

    return JsonResponse({
        'is_correct': is_correct,
        'feedback_message': feedback_message,
        'progress_percentage': progress_percentage,
    })


#------------------------------------------------------------------------------------------------------------
# match mini game functions

# sets up the match game by generating a new lineup of flashcards
@login_required
@email_verified_required
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


# renders the match game page with the terms and definitions to be matched
def match(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    lineup_ids = request.session.get('lineup', [])
    if not lineup_ids:
        return redirect('setup_match', set_id=set_id)

    flashcards = Flashcard.objects.filter(id__in=lineup_ids)
    flashcard_map = {card.id: card for card in flashcards}
    flashcards = [flashcard_map[card_id] for card_id in lineup_ids if card_id in flashcard_map]

    # create a list of items to be matched
    items = []
    for flashcard in flashcards:
        items.append({'id': flashcard.id, 'value': flashcard.term})
        items.append({'id': flashcard.id, 'value': flashcard.definition})

    random.shuffle(items) # shuffle the items to randomise their order

    return render(request, 'cards/match.html', {
        'flashcard_set': flashcard_set,
        'items': items,
    })


# checks the user's answer for the match game and updates the flashcard attributes 
def evaluate_match(request, set_id):
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=request.user.profile)

    flashcard_id = request.GET.get('first_id')
    is_correct = request.GET.get('is_correct') == 'true'
    elapsed_time = int(request.GET.get('time', 0))

    flashcard = get_object_or_404(Flashcard, id=flashcard_id)

    evaluate_and_update_flashcard(request, flashcard, flashcard_set, True, is_correct, elapsed_time)

    return JsonResponse({'success': True, 'message': 'Evaluation complete'})


#------------------------------------------------------------------------------------------------------------
# game feedback functions

# clears the feedback message from the session
def clear_feedback(request):
    request.session.pop('feedback', None)
    return JsonResponse({'success': True})


# renders the end of game page and updates the user's score and rewards
def game_end(request, set_id):
    user_profile = request.user.profile
    league_users = LeagueUser.objects.filter(user=user_profile)
    flashcard_set = get_object_or_404(FlashcardSet, id=set_id, user=user_profile)
    start_time_str = request.session.get('start_time')
    correct = request.session.get('correct', 0)
    incorrect = request.session.get('incorrect', 0)
    skipped = request.session.get('skipped', 0)
    score = 0
    request.session['reward_given'] = False # flag to prevent multiple rewards

    # if a time exists, indicates that the match game was played
    if start_time_str:
        start_time = datetime.fromisoformat(start_time_str)
        total_time = (datetime.now() - start_time).total_seconds()
        score = 50 # flat rate for the match game

        # updates personal best time for the flashcard set
        if flashcard_set.quickest_time is None or total_time < flashcard_set.quickest_time:
            flashcard_set.quickest_time = total_time
            flashcard_set.save()
            score = 100 # bonus points for personal best time

    else:
        total_time = None
        score = correct/(correct+incorrect+skipped)*100

    brainbuck_reward = int(score / 10) if score > 0 else 0 # brainbuck reward based on score

    # update the user's profile with the score and brainbuck reward
    if not request.session.get('reward_given'):
        user_profile.brainbucks += brainbuck_reward

        # updates the user's scores in their leagues
        for league_user in league_users:
            league_user.update_score(score)

        user_profile.save()
        request.session['reward_given'] = True # flags that the reward has been given

    return render(request, 'cards/game_end.html', {
        'flashcard_set': flashcard_set,
        'total_time': total_time,
        'score':score,
        'brainbuck_reward': brainbuck_reward,
        'quickest_time': flashcard_set.quickest_time,
    })


#------------------------------------------------------------------------------------------------------------
# profile settings functions

# updates the user's email address and sends a verification email
@login_required
def change_email(request):
    if request.method == 'POST':
        new_email = request.POST.get('new_email')

        try:
            # check if the new email is already in use
            if User.objects.filter(email=new_email).exists():
                messages.error(request, "This email is already in use.")
            else:
                # update the saved email
                request.user.email = new_email
                request.user.save()

                # generate a new verification token
                profile = request.user.profile
                verification_token = str(uuid.uuid4())
                profile.verification_token = verification_token
                profile.is_verified = False  # mark new email as unverified
                profile.save()

                # generate the verification link and send the email
                verification_link = f"{settings.SITE_URL}/verify-email/{verification_token}/"
                try:
                    send_mail(
                        'BrainSpace: Verify Your Email',
                        f'Click the link to verify your email: {verification_link}',
                        settings.DEFAULT_FROM_EMAIL,
                        [new_email], 
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


# change the username of the user
@login_required
def change_username(request):
    # gets the new username from the form
    if request.method == 'POST':
        new_username = request.POST.get('new_username')

        if User.objects.filter(username=new_username).exists():
            messages.error(request, "This username is already taken.")

        # if username is available, update the username
        else:
            request.user.username = new_username
            request.user.save()
            messages.success(request, "Your username has been updated.")

    return redirect('settings_page')


# change the password of the user
@login_required
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # verify the old password and check if the new passwords match
        if not request.user.check_password(old_password):
            messages.error(request, "Your current password is incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "The new passwords do not match.")
        else:
            try:
                validate_password(new_password) # use custom password validator to check strength
            except ValidationError as e:
                messages.error(request, e.messages[0])
                return redirect('settings_page')

            # update the password and keep the user logged in
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)  # keep the user logged in
            messages.success(request, "Your password has been updated.")

    return redirect('settings_page')

# delete the user's account and all associated data
@login_required
def delete_account(request):
    if request.method == 'POST':
        request.user.delete()
        logout(request)
        return redirect('landing')

    return redirect('settings_page')


#------------------------------------------------------------------------------------------------------------
# password management functions

# handles the password reset request by sending a verification email with a reset link
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')

        # check if the inputted email is associated with a user
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


# confirms the password reset by validating the token and updating the password
def reset_password_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = get_user_model().objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
        user = None

    # check if the token is valid and not expired
    if user is not None and default_token_generator.check_token(user, token):
        
        # take the new password from the form
        if request.method == 'POST':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if new_password != confirm_password:
                messages.error(request, "Passwords do not match.")
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)  # keep the user logged in
                messages.success(request, "Your password has been reset successfully.")
                return redirect('login')
    else:
        messages.error(request, "Invalid or expired password reset link.")
        return redirect('forgot_password')

    return render(request, 'cards/reset_password_confirm.html', {'uidb64': uidb64, 'token': token})
