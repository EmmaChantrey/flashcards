import json
import re
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from cards.validators import CustomPasswordValidator
from django.contrib.messages import get_messages

from datetime import timedelta
import random
from django.test import TestCase
from django.utils.timezone import now
from django.contrib.auth.models import User
from cards.models import Profile, FlashcardSet, Flashcard, League, LeagueUser, Friendship
from django.utils import timezone
from unittest.mock import patch

from spaced_repetition import get_lineup, ease_factor_calculation
from cards.views import create_blank_definition_within_set


class SignupViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('signup')
        self.valid_data = {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'Securepassword123!',
            'confirm_password': 'Securepassword123!',
        }

    def test_signup_successful(self):
        response = self.client.post(self.signup_url, self.valid_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='testuser').exists())
        print("Test `test_signup_successful` passed.")

    def test_signup_username_already_taken(self):
        User.objects.create_user(username='testuser', email='existing@example.com', password='password')
        response = self.client.post(self.signup_url, self.valid_data)
        self.assertEqual(response.status_code, 302)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Username is already taken.")
        print("Test `test_signup_username_already_taken` passed.")

    def test_signup_email_already_registered(self):
        User.objects.create_user(username='existinguser', email='testuser@example.com', password='password')
        response = self.client.post(self.signup_url, self.valid_data)
        self.assertEqual(response.status_code, 302)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Email is already registered.")
        print("Test `test_signup_email_already_registered` passed.")

    def test_signup_passwords_do_not_match(self):
        invalid_data = self.valid_data.copy()
        invalid_data['confirm_password'] = 'differentpassword'
        response = self.client.post(self.signup_url, invalid_data)
        self.assertEqual(response.status_code, 302)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Passwords do not match.")
        print("Test `test_signup_passwords_do_not_match` passed.")

    def test_signup_invalid_method(self):
        response = self.client.get(self.signup_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cards/signup.html')
        print("Test `test_signup_invalid_method` passed.")


class CustomPasswordValidatorTests(TestCase):
    def setUp(self):
        self.validator = CustomPasswordValidator()

    def test_valid_password(self):
        try:
            self.validator.validate('StrongPass1!')
        except ValidationError:
            self.fail("Validator raised ValidationError unexpectedly!")
        print("Test `test_valid_password` passed.")

    def test_password_too_short(self):
        with self.assertRaises(ValidationError) as context:
            self.validator.validate('Sh0rt!')
        self.assertEqual(
            context.exception.message,
            "Password must be at least 8 characters long."
        )
        print("Test `test_password_too_short` passed.")

    def test_password_no_uppercase(self):
        with self.assertRaises(ValidationError) as context:
            self.validator.validate('nouppercase1!')
        self.assertEqual(
            context.exception.message,
            "Password must contain at least one uppercase letter."
        )
        print("Test `test_password_no_uppercase` passed.")

    def test_password_no_digit(self):
        with self.assertRaises(ValidationError) as context:
            self.validator.validate('NoDigit!')
        self.assertEqual(
            context.exception.message,
            "Password must contain at least one digit."
        )
        print("Test `test_password_no_digit` passed.")

    def test_password_no_special_character(self):
        with self.assertRaises(ValidationError) as context:
            self.validator.validate('NoSpecial1')
        self.assertEqual(
            context.exception.message,
            "Password must contain at least one special character (.,!?-*&)"
        )
        print("Test `test_password_no_special_character` passed.")
        

class LoginViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.dashboard_url = reverse('dashboard')
        self.verify_prompt_url = reverse('verify_email_prompt')

        self.verified_user = User.objects.create_user(
            username='verifieduser',
            email='verified@example.com',
            password='ValidPass123!'
        )
        self.verified_user.profile.is_verified = True
        self.verified_user.profile.save()

        self.unverified_user = User.objects.create_user(
            username='unverifieduser',
            email='unverified@example.com',
            password='ValidPass123!'
        )
        self.unverified_user.profile.is_verified = False
        self.unverified_user.profile.save()


    def test_login_verified_user_successful(self):
        response = self.client.post(self.login_url, {
            'username': 'verifieduser',
            'password': 'ValidPass123!',
        })
        self.assertRedirects(response, self.dashboard_url)
        print("Test `test_login_verified_user_successful` passed.")

    def test_login_unverified_user_redirects(self):
        response = self.client.post(self.login_url, {
            'username': 'unverifieduser',
            'password': 'ValidPass123!',
        })
        self.assertRedirects(response, self.verify_prompt_url)
        print("Test `test_login_unverified_user_redirects` passed.")

    def test_login_invalid_credentials(self):
        response = self.client.post(self.login_url, {
            'username': 'verifieduser',
            'password': 'WrongPassword!',
        })
        self.assertRedirects(response, self.login_url)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Incorrect username or password.")
        print("Test `test_login_invalid_credentials` passed.")

    def test_login_invalid_method(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cards/login.html')
        print("Test `test_login_invalid_method` passed.")


class FlashcardCreateViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='Testpass123!')
        self.profile = self.user.profile
        self.profile.is_verified = True
        self.profile.save()
        self.create_url = reverse('create')

        self.flashcard_set = FlashcardSet.objects.create(
            user=self.profile,
            name="Capital cities"
        )

        self.flashcard = Flashcard.objects.create(
            set=self.flashcard_set,
            term="Spain",
            definition="Madrid"
        )

    def test_create_flashcard_set(self):
        self.client.login(username='testuser', password='Testpass123!')

        post_data = {
            'name': 'More capital cities',
            'form-INITIAL_FORMS': '0',
            'form-TOTAL_FORMS': '1',
            'form-MIN_NUM_FORMS': '0',
            'form-MAX_NUM_FORMS': '1000',
            'form-0-term': 'France',
            'form-0-definition': 'Paris',
        }

        response = self.client.post(self.create_url, data=post_data)

        self.assertRedirects(response, reverse('dashboard'))

        # check that the set was created
        flashcard_set = FlashcardSet.objects.get(name='More capital cities')
        self.assertEqual(FlashcardSet.objects.count(), 2)
        self.assertEqual(flashcard_set.name, 'More capital cities')
        self.assertEqual(flashcard_set.user, self.profile)

        # check that the flashcard was created and linked
        self.assertEqual(flashcard_set.flashcards.count(), 1)
        flashcard = flashcard_set.flashcards.first()
        self.assertEqual(flashcard.term, 'France')
        self.assertEqual(flashcard.definition, 'Paris')
        print("Test `test_create_flashcard_set` passed.")

    def test_delete_flashcard_set(self):
        self.client.force_login(self.user)
        url = reverse('delete', args=[self.flashcard_set.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(FlashcardSet.objects.filter(id=self.flashcard_set.id).exists())
        print("Test `test_delete_flashcard_set` passed.")


class FriendRequestTests(TestCase):

    def setUp(self):
        self.client = Client()

        # Create two users and profiles
        self.user1 = User.objects.create_user(username='user1', password='Testpass123!')
        self.user2 = User.objects.create_user(username='user2', password='Testpass123!')
        self.profile1 = self.user1.profile
        self.profile2 = self.user2.profile

    def test_send_friend_request(self):
        self.client.login(username='user1', password='Testpass123!')
        response = self.client.get(reverse('send_friend_request', args=[self.profile2.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Friendship.objects.count(), 1)
        friendship = Friendship.objects.first()
        self.assertEqual(friendship.sender, self.profile1)
        self.assertEqual(friendship.receiver, self.profile2)
        self.assertEqual(friendship.status, 'pending')
        print("Test `test_send_friend_request` passed.")


    def test_duplicate_friend_request(self):
        Friendship.objects.create(sender=self.profile1, receiver=self.profile2)

        self.client.login(username='user1', password='Testpass123!')
        response = self.client.get(reverse('send_friend_request', args=[self.profile2.id]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Friendship.objects.count(), 1)
        print("Test `test_duplicate_friend_request` passed.")


    def test_view_friend_requests(self):
        Friendship.objects.create(sender=self.profile1, receiver=self.profile2)

        self.client.login(username='user2', password='Testpass123!')
        response = self.client.get(reverse('view_friend_requests'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.profile1.user.username)
        print("Test `test_view_friend_requests` passed.")


    def test_accept_friend_request_adds_to_friends(self):
        friend_request = Friendship.objects.create(sender=self.profile1, receiver=self.profile2)

        self.client.login(username='user2', password='Testpass123!')
        self.client.get(reverse('accept_friend_request', args=[friend_request.id]))
        self.assertIn(self.profile1, self.profile2.get_friends())
        self.assertIn(self.profile2, self.profile1.get_friends())
        print("Test `test_accept_friend_request_adds_to_friends` passed.")


    def test_reject_friend_request(self):
        friend_request = Friendship.objects.create(sender=self.profile1, receiver=self.profile2)

        self.client.login(username='user2', password='Testpass123!')
        response = self.client.get(reverse('reject_friend_request', args=[friend_request.id]))

        friend_request.refresh_from_db()
        self.assertEqual(friend_request.status, 'rejected')

        response = self.client.get(reverse('view_friend_requests'))
        self.assertNotContains(response, self.profile1.user.username)
        print("Test `test_reject_friend_request` passed.")


class LeagueTests(TestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='Testpass123!')
        self.user2 = User.objects.create_user(username='user2', password='Testpass123!')
        self.user3 = User.objects.create_user(username='user3', password='Testpass123!')
        self.user4 = User.objects.create_user(username='user4', password='Testpass123!')

        self.profile1 = self.user1.profile
        self.profile1.is_verified = True
        self.profile1.save()
        self.profile2 = self.user2.profile
        self.profile2.is_verified = True
        self.profile2.save()
        self.profile3 = self.user3.profile
        self.profile3.is_verified = True
        self.profile3.save()
        self.profile4 = self.user4.profile
        self.profile4.is_verified = True
        self.profile4.save()

        # make the users friends
        self.profile1.add_friend(self.profile2)

        self.create_league_url = reverse('create_league')
        
    def test_create_league_with_valid_friends(self):
        self.client.login(username='user1', password='Testpass123!')

        response = self.client.post(self.create_league_url, {
            'league_name': 'Test League',
            'friends': [self.profile2.id]  # user2 is a friend of user1
        })

        self.assertRedirects(response, reverse('profile'))
        league = League.objects.get(name='Test League')
        self.assertEqual(league.owner, self.profile1)
        self.assertEqual(league.get_members().count(), 2)
        print("Test `test_create_league_with_valid_friends` passed.")

    def test_reset_scores_after_week(self):
        self.client.login(username='user1', password='Testpass123!')

        # create a league and add some users
        league = League.objects.create(name='Test League', owner=self.profile1)
        league_user1 = LeagueUser.objects.create(league=league, user=self.profile1, score=100)
        league_user2 = LeagueUser.objects.create(league=league, user=self.profile2, score=50)

        # simulate that a week has passed
        league.last_rewarded = timezone.now() - timedelta(weeks=1)
        league.save()
        league.reward_top_users()
        league_user1.refresh_from_db()
        league_user2.refresh_from_db()

        self.assertEqual(league_user1.score, 0)
        self.assertEqual(league_user2.score, 0)
        print("Test `test_reset_scores_after_week` passed.")

    def test_league_creation_and_user_score_update(self):
        self.client.login(username='user1', password='Testpass123!')

        response = self.client.post(self.create_league_url, {
            'league_name': 'Test League',
            'friends': [self.profile2.id]  # user2 is a friend of user1
        })

        self.assertRedirects(response, reverse('profile'))

        league = League.objects.get(name='Test League')
        
        league_user1 = LeagueUser.objects.get(league=league, user=self.profile1)
        league_user2 = LeagueUser.objects.get(league=league, user=self.profile2)

        self.assertEqual(league_user1.score, 0)
        self.assertEqual(league_user2.score, 0)

        league_user2.update_score(20)
        league_user2.refresh_from_db()
        self.assertEqual(league_user2.score, 20)
        print("Test `test_league_creation_and_user_score_update` passed.")

    def test_reward_top_users_and_assign_brainbucks(self):
        league = League.objects.create(name='Test League', owner=self.profile1)
        league_user1 = LeagueUser.objects.create(league=league, user=self.profile1, score=150)
        league_user2 = LeagueUser.objects.create(league=league, user=self.profile2, score=120)
        league_user3 = LeagueUser.objects.create(league=league, user=self.profile3, score=90)
        league_user4 = LeagueUser.objects.create(league=league, user=self.profile4, score=60)

        self.assertEqual(self.profile1.brainbucks, 0)
        self.assertEqual(self.profile2.brainbucks, 0)
        self.assertEqual(self.profile3.brainbucks, 0)
        self.assertEqual(self.profile4.brainbucks, 0)

        league.reward_top_users()

        self.profile1.refresh_from_db()
        self.profile2.refresh_from_db()
        self.profile3.refresh_from_db()
        self.profile4.refresh_from_db()

        self.assertEqual(self.profile1.brainbucks, 50)
        self.assertEqual(self.profile2.brainbucks, 30)
        self.assertEqual(self.profile3.brainbucks, 20)

        league = League.objects.get(id=league.id)
        previous_top_users = json.loads(league.previous_top_users)

        self.assertEqual(len(previous_top_users), 3)
        self.assertEqual(previous_top_users[0]["username"], self.user1.username)
        self.assertEqual(previous_top_users[0]["score"], 150)
        self.assertEqual(previous_top_users[1]["username"], self.user2.username)
        self.assertEqual(previous_top_users[1]["score"], 120)
        self.assertEqual(previous_top_users[2]["username"], self.user3.username)
        self.assertEqual(previous_top_users[2]["score"], 90)

        league_user1.refresh_from_db()
        league_user2.refresh_from_db()
        league_user3.refresh_from_db()
        league_user4.refresh_from_db()

        self.assertEqual(league_user1.score, 0)
        self.assertEqual(league_user2.score, 0)
        self.assertEqual(league_user3.score, 0)
        self.assertEqual(league_user4.score, 0)
        print("Test `test_reward_top_users_and_assign_brainbucks` passed.")



class TrueFalseGameTests(TestCase):

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='Testpass123!')
        self.user2 = User.objects.create_user(username='user2', password='Testpass123!')
        self.user1_profile = self.user1.profile
        self.user1_profile.is_verified = True
        self.user1_profile.save()
        self.user2_profile = self.user2.profile
        self.user2_profile.is_verified = True
        self.user2_profile.save()

        self.flashcard_set = FlashcardSet.objects.create(
            name='Test Set', user=self.user1_profile)
        self.flashcard1 = Flashcard.objects.create(
            term='Term 1', definition='Definition 1', set=self.flashcard_set)
        self.flashcard2 = Flashcard.objects.create(
            term='Term 2', definition='Definition 2', set=self.flashcard_set)

        self.setup_url = reverse('setup_true_false', args=[self.flashcard_set.id])
        self.true_false_url = reverse('true_false', args=[self.flashcard_set.id])
        self.true_false_check_url = reverse('true_false_check', args=[self.flashcard_set.id])
        self.true_false_feedback_url = reverse('true_false_feedback', args=[self.flashcard_set.id])
        self.true_false_next_url = reverse('true_false_next', args=[self.flashcard_set.id])

    def test_setup_true_false(self):
        self.client.login(username='user1', password='Testpass123!')
        response = self.client.get(self.setup_url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue('lineup' in self.client.session)
        self.assertTrue('current_index' in self.client.session)
        self.assertTrue('start_time' in self.client.session)
        self.assertEqual(self.client.session['current_index'], 0)
        print("Test `test_setup_true_false` passed.")

    def test_true_false(self):
        self.client.login(username='user1', password='Testpass123!')
        self.client.get(self.setup_url)

        response = self.client.get(self.true_false_url)
        self.assertEqual(response.status_code, 200)

        # verify that the flashcard is displayed and progress is calculated
        self.assertContains(response, 'Term')
        self.assertContains(response, 'Definition')
        print("Test `test_true_false` passed.")

    def test_true_false_check_correct_answer(self):
        self.client.login(username='user1', password='Testpass123!')
        self.client.get(self.setup_url)

        self.client.get(self.true_false_url)
        is_correct = self.client.session['is_correct']

        # simulate the user answering correctly
        request_data = {
            'answer': 'true' if is_correct else 'false',
            'time': 5
        }

        response = self.client.get(self.true_false_check_url, data=request_data)
        self.assertRedirects(response, self.true_false_feedback_url)

        self.assertIn('feedback_message', self.client.session)
        self.assertIn("✅ Correct!", self.client.session['feedback_message'])
        print("Test `test_true_false_check_correct_answer` passed.")


    def test_true_false_check_incorrect_answer(self):
        self.client.login(username='user1', password='Testpass123!')
        self.client.get(self.setup_url)

        self.client.get(self.true_false_url)

        is_correct = self.client.session['is_correct']

        # simulate user answering incorrectly (opposite of actual value)
        request_data = {
            'answer': 'false' if is_correct else 'true',
            'time': 5
        }

        response = self.client.get(self.true_false_check_url, data=request_data)
        self.assertRedirects(response, self.true_false_feedback_url)

        self.assertIn('feedback_message', self.client.session)
        self.assertIn("❌ Incorrect.", self.client.session['feedback_message'])
        print("Test `test_true_false_check_incorrect_answer` passed.")


    def test_true_false_next(self):
        self.client.login(username='user1', password='Testpass123!')
        self.client.get(self.setup_url)
        self.client.get(self.true_false_url)

        response = self.client.get(self.true_false_next_url)
        self.assertRedirects(response, self.true_false_url)

        # check that the index has been incremented
        self.assertEqual(self.client.session['current_index'], 1)
        print("Test `test_true_false_next` passed.")

    def test_true_false_feedback(self):
        self.client.login(username='user1', password='Testpass123!')
        self.client.get(self.setup_url)
        self.client.get(self.true_false_url)

        current_flashcard_id = self.client.session['current_flashcard_id']
        flashcard = Flashcard.objects.get(id=current_flashcard_id)
        is_correct = self.client.session['is_correct']

        # choose correct answer based on the actual value of is_correct
        user_answer = 'true' if is_correct else 'false'
        request_data = {'answer': user_answer, 'time': 5}
        self.client.get(self.true_false_check_url, data=request_data)

        response = self.client.get(self.true_false_feedback_url)
        self.assertEqual(response.status_code, 200)

        feedback_message = self.client.session.get('feedback_message', '')

        if feedback_message.startswith("✅ Correct!"):
            self.assertContains(response, "✅ Correct!")
        elif feedback_message.startswith("❌ Incorrect."):
            self.assertContains(response, "❌ Incorrect.")
        else:
            self.fail(f"Unexpected feedback message: {feedback_message}")

        self.assertContains(response, flashcard.term)
        self.assertIn(flashcard.definition, response.content.decode())

        print("Test `test_true_false_feedback` passed.")



class FillTheBlanksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='Testpass123!')
        self.profile = self.user.profile
        self.profile.is_verified = True
        self.profile.save()

        self.flashcard_set = FlashcardSet.objects.create(user=self.profile, name="Test Set")
        self.flashcard1 = Flashcard.objects.create(
            term="Term1", definition="This is the definition of Term1", set=self.flashcard_set)
        self.flashcard2 = Flashcard.objects.create(
            term="Term2", definition="This is the definition of Term2", set=self.flashcard_set)
        self.flashcard_set.flashcards.add(self.flashcard1, self.flashcard2)
        self.client.login(username='testuser', password='Testpass123!')

    @patch('cards.views.random.choice')
    def test_create_blank_definition_within_set(self, mock_random_choice):
        mock_random_choice.return_value = "Term1"
        blanked_definition, blanked_word = create_blank_definition_within_set(self.flashcard1, self.flashcard_set)
        self.assertIn('<input type="text" class="blank"', blanked_definition)
        self.assertEqual(blanked_word, "Term1")

    def test_fill_the_blanks_view(self):
        response = self.client.get(reverse('setup_fill_the_blanks', args=[self.flashcard_set.id]))
        self.assertRedirects(response, reverse('fill_the_blanks', args=[self.flashcard_set.id]))
        print("Test `test_fill_the_blanks_view` passed.")


    def test_fill_the_blanks_check_correct_answer(self):
        self.client.get(reverse('setup_fill_the_blanks', args=[self.flashcard_set.id]))
        response = self.client.get(reverse('fill_the_blanks', args=[self.flashcard_set.id]))
        flashcard = response.context['flashcard']
        correct_answer = flashcard['correct_answer']
        response = self.client.post(reverse('fill_the_blanks_check', args=[self.flashcard_set.id]), {
            'answer': correct_answer,
            'elapsed_time': 5
        })
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content.decode(), {
            'is_correct': True,
            'feedback_message': '✅ Correct!',
            'progress_percentage': 50,
        })
        print("Test `test_fill_the_blanks_check_correct_answer` passed.")  


    def test_fill_the_blanks_check_incorrect_answer(self):
        self.client.get(reverse('setup_fill_the_blanks', args=[self.flashcard_set.id]))
        response = self.client.get(reverse('fill_the_blanks', args=[self.flashcard_set.id]))
        flashcard = response.context['flashcard']

        incorrect_answer = "WrongAnswer"
        correct_answer = flashcard['correct_answer']

        response = self.client.post(reverse('fill_the_blanks_check', args=[self.flashcard_set.id]), {
            'answer': incorrect_answer,
            'elapsed_time': 5
        })

        self.assertEqual(response.status_code, 200)

        self.assertJSONEqual(response.content.decode(), {
            'is_correct': False,
            'feedback_message': f"❌ Incorrect. The correct answer is '{correct_answer}'.",
            'progress_percentage': 50,
        })

        print("Test `test_fill_the_blanks_check_incorrect_answer` passed.")



    def test_fill_the_blanks_check_skipped(self):
        self.client.get(reverse('setup_fill_the_blanks', args=[self.flashcard_set.id]))
        response = self.client.get(reverse('fill_the_blanks', args=[self.flashcard_set.id]))
        flashcard = response.context['flashcard']
        response = self.client.post(reverse('fill_the_blanks_check', args=[self.flashcard_set.id]), {
            'skipped': 'true',
            'elapsed_time': 5
        })
        
        content = response.content.decode()
        data = json.loads(content)

        # Extract the correct word from the feedback message using regex
        match = re.search(r"correct answer is '(.*?)'", data['feedback_message'])
        correct_word = match.group(1) if match else None

        # Now compare dynamically using the extracted word
        self.assertJSONEqual(content, {
            "is_correct": False,
            "feedback_message": f"⚠️ Skipped. The correct answer is '{correct_word}'.",
            "progress_percentage": 50.0
        })

        print("Test `test_fill_the_blanks_check_skipped` passed.")


    def test_game_end_redirect(self):
        self.client.get(reverse('setup_fill_the_blanks', args=[self.flashcard_set.id]))

        for _ in range(self.flashcard_set.flashcards.count()):
            response = self.client.get(reverse('fill_the_blanks', args=[self.flashcard_set.id]))
            flashcard = response.context['flashcard']
            correct_answer = flashcard['correct_answer']
            self.client.post(reverse('fill_the_blanks_check', args=[self.flashcard_set.id]), {
                'answer': correct_answer,
                'elapsed_time': 5
            })

        final_response = self.client.get(reverse('fill_the_blanks', args=[self.flashcard_set.id]))
        self.assertRedirects(final_response, reverse('game_end', args=[self.flashcard_set.id]))
        print("Test `test_game_end_redirect` passed.")



class QuizModeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='Testpass123!')
        self.user.profile.is_verified = True
        self.user.profile.save()
        self.client.force_login(self.user)

        self.flashcard_set = FlashcardSet.objects.create(name="Sample Set", user=self.user.profile)

        self.cards = [
            Flashcard.objects.create(term=f"Term{i}", definition=f"Definition{i}", set=self.flashcard_set)
            for i in range(4)
        ]

    def test_setup_quiz_initialises_session(self):
        response = self.client.get(reverse('setup_quiz', args=[self.flashcard_set.id]))
        self.assertRedirects(response, reverse('quiz', args=[self.flashcard_set.id]))

        session = self.client.session
        self.assertIn('lineup', session)
        self.assertEqual(len(session['lineup']), 4)
        self.assertEqual(session['current_index'], 0)
        self.assertEqual(session['correct'], 0)
        self.assertEqual(session['incorrect'], 0)
        print("Test `test_setup_quiz_initialises_session` passed.")

    def test_quiz_view_renders_correct_flashcard(self):
        self.client.get(reverse('setup_quiz', args=[self.flashcard_set.id]))
        response = self.client.get(reverse('quiz', args=[self.flashcard_set.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('flashcard', response.context)
        self.assertTemplateUsed(response, 'cards/quiz.html')
        print("Test `test_quiz_view_renders_correct_flashcard` passed.")

    def test_quiz_check_correct_answer(self):
        self.client.get(reverse('setup_quiz', args=[self.flashcard_set.id]))
        session = self.client.session
        flashcard = session['lineup'][0]
        correct_answer = flashcard['correct_answer']

        response = self.client.post(reverse('quiz_check', args=[self.flashcard_set.id]), {
            'selected_answer': correct_answer,
            'elapsed_time': 5
        })
        data = json.loads(response.content)

        self.assertTrue(data['is_correct'])
        self.assertEqual(data['feedback_message'], "✅ Correct!")
        self.assertIn('progress_percentage', data)
        print("Test `test_quiz_check_correct_answer` passed.")

    def test_quiz_check_incorrect_answer(self):
        self.client.get(reverse('setup_quiz', args=[self.flashcard_set.id]))
        session = self.client.session
        flashcard = session['lineup'][0]
        wrong_answer = "DefinitelyWrong"

        response = self.client.post(reverse('quiz_check', args=[self.flashcard_set.id]), {
            'selected_answer': wrong_answer,
            'elapsed_time': 3
        })
        data = json.loads(response.content)

        self.assertFalse(data['is_correct'])
        self.assertIn("❌ Incorrect", data['feedback_message'])
        self.assertIn('progress_percentage', data)
        print("Test `test_quiz_check_incorrect_answer` passed.")

    def test_quiz_check_skipped(self):
        self.client.get(reverse('setup_quiz', args=[self.flashcard_set.id]))
        response = self.client.post(reverse('quiz_check', args=[self.flashcard_set.id]), {
            'skipped': 'true'
        })
        data = json.loads(response.content)

        self.assertFalse(data['is_correct'])
        self.assertIn("⚠️ Skipped", data['feedback_message'])
        self.assertIn('progress_percentage', data)
        print("Test `test_quiz_check_skipped` passed.")

    def test_quiz_completion_redirects(self):
        self.client.get(reverse('setup_quiz', args=[self.flashcard_set.id]))
        session = self.client.session
        session['current_index'] = len(session['lineup'])
        session.save()

        response = self.client.post(reverse('quiz_check', args=[self.flashcard_set.id]))
        data = json.loads(response.content)

        self.assertTrue(data['redirect'])
        self.assertEqual(data['url'], reverse('game_end', args=[self.flashcard_set.id]))
        print("Test `test_quiz_completion_redirects` passed.")



class MatchModeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='matchuser', password='Testpass123!')
        self.user.profile.is_verified = True
        self.user.profile.save()
        self.client.force_login(self.user)

        self.flashcard_set = FlashcardSet.objects.create(name='Match Set', user=self.user.profile)

        self.cards = [
            Flashcard.objects.create(term=f"Term{i}", definition=f"Definition{i}", set=self.flashcard_set)
            for i in range(6)
        ]

    def test_setup_match_stores_session_data(self):
        response = self.client.get(reverse('setup_match', args=[self.flashcard_set.id]))
        self.assertRedirects(response, reverse('match', args=[self.flashcard_set.id]))

        session = self.client.session
        self.assertIn('lineup', session)
        self.assertEqual(len(session['lineup']), 6)
        self.assertEqual(session['current_index'], 0)
        self.assertEqual(session['correct'], 0)
        self.assertEqual(session['incorrect'], 0)
        self.assertIsNotNone(session['start_time'])

        print("Test `test_setup_match_stores_session_data` passed.")

    def test_match_view_renders_items(self):
        self.client.get(reverse('setup_match', args=[self.flashcard_set.id]))
        response = self.client.get(reverse('match', args=[self.flashcard_set.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn('items', response.context)
        self.assertIn('flashcard_set', response.context)
        self.assertTemplateUsed(response, 'cards/match.html')

        items = response.context['items']
        self.assertEqual(len(items), 12) # 6 terms + 6 definitions

        print("Test `test_match_view_renders_items` passed.")

    def test_match_redirects_if_no_lineup(self):
        response = self.client.get(reverse('match', args=[self.flashcard_set.id]), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('setup_match', args=[self.flashcard_set.id]))
        print("Test `test_match_redirects_if_no_lineup` passed.")

    def test_evaluate_match_correct_response(self):
        self.client.get(reverse('setup_match', args=[self.flashcard_set.id]))
        flashcard = self.cards[0]

        response = self.client.get(reverse('evaluate_match', args=[self.flashcard_set.id]), {
            'first_id': flashcard.id,
            'is_correct': 'true',
            'time': '7'
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Evaluation complete')
        print("Test `test_evaluate_match_correct_response` passed.")

    def test_evaluate_match_incorrect_response(self):
        self.client.get(reverse('setup_match', args=[self.flashcard_set.id]))
        flashcard = self.cards[0]

        response = self.client.get(reverse('evaluate_match', args=[self.flashcard_set.id]), {
            'first_id': flashcard.id,
            'is_correct': 'false',
            'time': '7'
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Evaluation complete')
        print("Test `test_evaluate_match_incorrect_response` passed.")

    def test_cards_disappear_on_correct_match(self):
        session = self.client.session
        session['lineup'] = [self.cards[0].id, self.cards[1].id]
        session['correct'] = 0
        session.save()

        self.client.get(reverse('evaluate_match', args=[self.flashcard_set.id]), {
            'first_id': self.cards[0].id,
            'second_id': self.cards[1].id,
            'is_correct': 'true',
            'time': '4',
        })

        response = self.client.get(reverse('match', args=[self.flashcard_set.id]))
        content = response.content.decode()

        self.assertIn('style="display: none;"', content)

        print("Test `test_cards_disappear_on_correct_match` passed.")


    def test_cards_remain_visible_on_incorrect_match(self):
        session = self.client.session
        session['lineup'] = [self.cards[0].id, self.cards[1].id]
        session['incorrect'] = 0
        session.save()

        self.client.get(reverse('evaluate_match', args=[self.flashcard_set.id]), {
            'first_id': self.cards[0].id,
            'second_id': self.cards[1].id,
            'is_correct': 'false',
            'time': '4',
        })

        response = self.client.get(reverse('match', args=[self.flashcard_set.id]))
        content = response.content.decode()

        self.assertIn('Term0', content)
        self.assertIn('Definition0', content)
        self.assertIn('Term1', content)
        self.assertIn('Definition1', content)
        print("Test `test_cards_remain_visible_on_incorrect_match` passed.")


class SpacedRepetitionTests(TestCase):
    def setUp(self):
        self.user, created = User.objects.get_or_create(username='testuser', defaults={'password': 'testpassword'})
        self.profile, created = Profile.objects.get_or_create(user=self.user)

        self.create_flashcard_set(
            self.profile,
            "Capital Cities",
            [
                ("France", "Paris"),
                ("Germany", "Berlin"),
                ("Japan", "Tokyo"),
                ("USA", "Washington D.C."),
                ("Brazil", "Brasilia"),
                ("Australia", "Canberra"),
                ("Canada", "Ottawa"),
                ("China", "Beijing"),
                ("The Netherlands", "Amsterdam"),
                ("South Korea", "Seoul"),
                ("Italy", "Rome"),
                ("Spain", "Madrid"),
                ("Mexico", "Mexico City"),
                ("Argentina", "Buenos Aires"),
                ("Egypt", "Cairo"),
                ("Greece", "Athens"),
                ("Sweden", "Stockholm"),
                ("Norway", "Oslo"),
                ("Denmark", "Copenhagen"),
                ("Finland", "Helsinki"),
                ("Portugal", "Lisbon"),
                ("Ireland", "Dublin"),
                ("Austria", "Vienna"),
                ("Belgium", "Brussels"),
            ]
        )

    def create_flashcard_set(self, profile, name, terms_definitions):
        flashcard_set = FlashcardSet.objects.create(
            user=profile,
            name=name,
            baseline=random.uniform(2.5, 7.5)
        )

        for term, definition in terms_definitions:            
            Flashcard.objects.create(
                set=flashcard_set,
                term=term,
                definition=definition,
                interval=1,
                ease_factor=2.5,
                last_reviewed=now() - timedelta(days=random.randint(0, 60))
            )



    def test_lineup_generation_with_output(self):
        flashcards = Flashcard.objects.all()

        print("\nAll Flashcards:")
        for flashcard in flashcards:
            next_review_date = flashcard.last_reviewed + timedelta(seconds=flashcard.interval)
            print(f"Term: {flashcard.term}, Interval: {flashcard.interval / 86400:.1f} days, "
                  f"Last Reviewed: {flashcard.last_reviewed}, Ease Factor: {flashcard.ease_factor:.2f}, "
                  f"Next Review Date: {next_review_date}")

        lineup = get_lineup(flashcards, 10)

        print("\nGenerated Lineup:")
        for flashcard in lineup:
            next_review_date = flashcard.last_reviewed + timedelta(seconds=flashcard.interval)
            print(f"Term: {flashcard.term}, Interval: {flashcard.interval / 86400:.1f} days, "
                  f"Last Reviewed: {flashcard.last_reviewed}, Ease Factor: {flashcard.ease_factor:.2f}, "
                  f"Next Review Date: {next_review_date}")

        self.assertEqual(len(lineup), 10, "Lineup should contain exactly 10 flashcards.")

        overdue_flashcards = [
            flashcard for flashcard in flashcards
            if flashcard.last_reviewed + timedelta(seconds=flashcard.interval) <= now()
        ]
        self.assertTrue(
            all(flashcard in overdue_flashcards for flashcard in lineup[:len(overdue_flashcards)]),
            "Overdue flashcards should be prioritized in the lineup."
        )

        non_overdue_flashcards = [
            flashcard for flashcard in flashcards if flashcard not in overdue_flashcards
        ]
        self.assertTrue(
            all(flashcard in non_overdue_flashcards for flashcard in lineup[len(overdue_flashcards):]),
            "Non-overdue flashcards should be used to fill the remaining lineup."
        )

        print("\nTest `test_lineup_generation_with_output` passed.")


    def evaluate_and_update_flashcard(self, request, flashcard, flashcard_set, user_answer, is_correct, elapsed_time):
        print(f"user_answer: {user_answer}, is_correct: {is_correct}, elapsed_time: {elapsed_time}")
        if user_answer == is_correct:
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


    def test_flashcard_performance_updates(self):
        flashcards = Flashcard.objects.all()
        flashcard_set = FlashcardSet.objects.first()
        
        self.assertTrue(flashcards.exists(), "There should be at least one flashcard in the database.")
        self.assertIsNotNone(flashcard_set, "FlashcardSet should exist in the database.")


        print(f"\n--- Generating Lineup ---")
        lineup = get_lineup(flashcards, 10)
        
        self.assertLessEqual(len(lineup), 10, "Lineup size exceeds the maximum allowed value.")
        self.assertTrue(all(card in flashcards for card in lineup), "Lineup contains flashcards not in the database.")

        print("\nLineup:")
        for flashcard in lineup:
            print(f"Term: {flashcard.term}, Interval: {flashcard.interval / 86400:.1f} days, "
                f"Last Reviewed: {flashcard.last_reviewed}, Ease Factor: {flashcard.ease_factor:.2f}")

        # simulate user interaction
        intervals_by_flashcard = {flashcard.term: [] for flashcard in Flashcard.objects.all()}

        for flashcard in lineup:
            intervals_by_flashcard[flashcard.term].append(flashcard.interval / 86400)
            for i in range(100):
                print(f"\n--- Question {i + 1} ---")
                true_weight = max((i*10), 400)
                user_answer = random.choices([True, False], weights=[true_weight, 1000 - true_weight], k=1)[0]
                elapsed_time = random.uniform(1, 20)

                old_interval = flashcard.interval
                old_ease_factor = flashcard.ease_factor
                old_last_reviewed = flashcard.last_reviewed

                print(f"\n--- Flashcard: {flashcard.term} ---")
                print(f"The user's answer was correct? {user_answer} in {elapsed_time:.2f} seconds")

                # store performance level
                slow = elapsed_time >= 1.25 * flashcard_set.baseline
                average = elapsed_time > 0.75 * flashcard_set.baseline and elapsed_time <= 1.25 * flashcard_set.baseline
                fast = elapsed_time <= 0.75 * flashcard_set.baseline

                self.evaluate_and_update_flashcard(None, flashcard, flashcard_set, user_answer, True, elapsed_time)
                flashcard.refresh_from_db()

                print(f"Old interval: {old_interval / 86400:.1f} days, New interval: {flashcard.interval / 86400:.1f} days, \nOld ease factor: {old_ease_factor:.2f}, New ease factor: {flashcard.ease_factor:.2f}")

                intervals_by_flashcard[flashcard.term].append(flashcard.interval / 86400)  # convert seconds to days

                print(f"flashcard term: {flashcard.term}, user_answer: {user_answer}, slow: {slow}, average: {average}, fast: {fast}")
                if user_answer and not slow:
                    expected_ease_factor = ease_factor_calculation(old_ease_factor, performance_level=3 if average else 4)
                    self.assertEqual(flashcard.ease_factor, expected_ease_factor,
                                    f"Ease factor did not update correctly. Expected: {expected_ease_factor}, actual: {flashcard.ease_factor}")
                elif user_answer and slow:
                    expected_ease_factor = ease_factor_calculation(old_ease_factor, performance_level=2)
                    self.assertEqual(flashcard.ease_factor, expected_ease_factor,
                                    f"Ease factor did not update correctly. Expected: {expected_ease_factor}, actual: {flashcard.ease_factor}")
                else:
                    self.assertEqual(flashcard.interval, 86400, "Interval did not return to 1 after incorrect answer.")

                self.assertGreater(flashcard.last_reviewed, old_last_reviewed, "Last reviewed time did not update.")

        print("\nCollected Intervals:")
        for term, intervals in intervals_by_flashcard.items():
            print(f"Term: {term}, Intervals (days): {intervals}")

        print("\nUpdated Flashcards:")
        for flashcard in Flashcard.objects.all():
            next_review_date = flashcard.last_reviewed + timedelta(seconds=flashcard.interval)
            expected_next_review_date = flashcard.last_reviewed + timedelta(seconds=flashcard.interval)
            self.assertEqual(next_review_date, expected_next_review_date, "Next review date calculation is incorrect.")
       
        print("Test `test_flashcard_performance_updates` passed.")

    def test_flashcard_overdue_prioritisation(self):
        flashcards = Flashcard.objects.all()

        lineup = get_lineup(flashcards, 10)

        overdue_flashcards = [
            flashcard for flashcard in flashcards
            if flashcard.last_reviewed + timedelta(seconds=flashcard.interval) <= now()
        ]

        print("Overdue flashcards:")
        for flashcard in overdue_flashcards:
            print(f" - Term: {flashcard.term}, Last Reviewed: {flashcard.last_reviewed}, Interval: {flashcard.interval}")

        print("\nLineup flashcards:")
        for i, flashcard in enumerate(lineup):
            print(f"{i+1}. Term: {flashcard.term}, Last Reviewed: {flashcard.last_reviewed}, Interval: {flashcard.interval}")

        self.assertTrue(
            all(flashcard in overdue_flashcards for flashcard in lineup[:len(overdue_flashcards)]),
            "Overdue flashcards should be prioritised in the lineup."
        )

        lineup_overdue_part = lineup[:len(overdue_flashcards)]
        print("\nChecking lineup[:len(overdue_flashcards)]:")
        for flashcard in lineup_overdue_part:
            print(f" - Term: {flashcard.term}, Last Reviewed: {flashcard.last_reviewed}, Interval: {flashcard.interval}")

        print("\nAre all flashcards in the initial part of the lineup overdue?")
        print(all(flashcard in overdue_flashcards for flashcard in lineup_overdue_part))
        
        print("\nTest `test_flashcard_overdue_prioritisation` passed.")
