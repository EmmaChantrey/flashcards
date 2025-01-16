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
from cards.models import Profile, FlashcardSet, Flashcard
from spaced_repetition import get_lineup, ease_factor_calculation


class SignupViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('signup')
        self.valid_data = {
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'securepassword123',
            'confirm_password': 'securepassword123',
        }

    def test_signup_successful(self):
        response = self.client.post(self.signup_url, self.valid_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='testuser').exists())

    def test_signup_username_already_taken(self):
        User.objects.create_user(username='testuser', email='existing@example.com', password='password')
        response = self.client.post(self.signup_url, self.valid_data)
        self.assertEqual(response.status_code, 302)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Username is already taken.")

    def test_signup_email_already_registered(self):
        User.objects.create_user(username='existinguser', email='testuser@example.com', password='password')
        response = self.client.post(self.signup_url, self.valid_data)
        self.assertEqual(response.status_code, 302)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Email is already registered.")

    def test_signup_passwords_do_not_match(self):
        invalid_data = self.valid_data.copy()
        invalid_data['confirm_password'] = 'differentpassword'
        response = self.client.post(self.signup_url, invalid_data)
        self.assertEqual(response.status_code, 302)

        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Passwords do not match.")

    def test_signup_invalid_method(self):
        response = self.client.get(self.signup_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'cards/signup.html')


class CustomPasswordValidatorTests(TestCase):
    def setUp(self):
        self.validator = CustomPasswordValidator()

    def test_valid_password(self):
        try:
            self.validator.validate('StrongPass1!')
        except ValidationError:
            self.fail("Validator raised ValidationError unexpectedly!")

    def test_password_too_short(self):
        with self.assertRaises(ValidationError) as context:
            self.validator.validate('Sh0rt!')
        self.assertEqual(
            context.exception.message,
            "Password must be at least 8 characters long."
        )

    def test_password_no_uppercase(self):
        with self.assertRaises(ValidationError) as context:
            self.validator.validate('nouppercase1!')
        self.assertEqual(
            context.exception.message,
            "Password must contain at least one uppercase letter."
        )

    def test_password_no_digit(self):
        with self.assertRaises(ValidationError) as context:
            self.validator.validate('NoDigit!')
        self.assertEqual(
            context.exception.message,
            "Password must contain at least one digit."
        )

    def test_password_no_special_character(self):
        with self.assertRaises(ValidationError) as context:
            self.validator.validate('NoSpecial1')
        self.assertEqual(
            context.exception.message,
            "Password must contain at least one special character (.,!?-*&)"
        )


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
                ("Russia", "Moscow"),
                ("India", "New Delhi"),
                ("The Netherlands", "Amsterdam"),
                ("South Africa", "Pretoria"),
                ("South Korea", "Seoul"),
                ("Italy", "Rome"),
                ("Spain", "Madrid"),
                ("Mexico", "Mexico City"),
                ("Argentina", "Buenos Aires"),
                ("Egypt", "Cairo"),
                ("Turkey", "Ankara"),
                ("United Kingdom", "London"),
                ("Greece", "Athens"),
                ("Sweden", "Stockholm"),
                ("Norway", "Oslo"),
                ("Denmark", "Copenhagen"),
                ("Finland", "Helsinki"),
                ("Switzerland", "Bern"),
                ("Portugal", "Lisbon"),
                ("Ireland", "Dublin"),
                ("Austria", "Vienna"),
                ("Belgium", "Brussels"),
                ("Poland", "Warsaw"),
                ("Czech Republic", "Prague"),
                ("Hungary", "Budapest"),
                ("Romania", "Bucharest"),
                ("Bulgaria", "Sofia"),
                ("Croatia", "Zagreb"),
                ("Slovenia", "Ljubljana"),
                ("Slovakia", "Bratislava"),
                ("Ukraine", "Kyiv"),
                ("Serbia", "Belgrade"),
            ]
        )

    def create_flashcard_set(self, profile, name, terms_definitions):
        flashcard_set = FlashcardSet.objects.create(
            user=profile,
            name=name,
            baseline=random.uniform(30, 60)
        )

        base_interval = 1 * 86400
        max_reviews = 5

        for term, definition in terms_definitions:
            previous_interval = base_interval
            ease_factor = random.uniform(1.3, 2.5)
            
            for _ in range(random.randint(0, max_reviews)):
                ease_factor = random.uniform(1.3, 2.5)
                previous_interval = previous_interval * ease_factor
            
            Flashcard.objects.create(
                set=flashcard_set,
                term=term,
                definition=definition,
                interval=previous_interval,
                ease_factor=ease_factor,
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

    def evaluate_and_update_flashcard(self, request, flashcard, flashcard_set, user_answer, is_correct, elapsed_time):
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

        # update flashcard's ease factor, interval, and last reviewed date
        flashcard.ease_factor = ease_factor_calculation(flashcard.ease_factor, performance_level)
        print(f"New ease factor for the flashcard '{flashcard.term}' is: {flashcard.ease_factor:.2f}")
        flashcard.interval = max(flashcard.interval * flashcard.ease_factor, 86400)  # Ensure at least one day
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

        for i in range(3):
            print(f"\n--- Generating Lineup {i + 1} ---")
            lineup = get_lineup(flashcards, 10)

            print("\nLineup:")
            for flashcard in lineup:
                print(f"Term: {flashcard.term}, Interval: {flashcard.interval / 86400:.1f} days, "
                      f"Last Reviewed: {flashcard.last_reviewed}, Ease Factor: {flashcard.ease_factor:.2f}")

            # Simulate user interaction with each flashcard in the lineup
            for flashcard in lineup:
                user_answer = random.choice([True, False])
                elapsed_time = random.uniform(0.5, 2.0) * flashcard_set.baseline

                self.evaluate_and_update_flashcard(None, flashcard, flashcard_set, user_answer, True, elapsed_time)

            # Validate updated flashcards
            print("\nUpdated Flashcards:")
            for flashcard in Flashcard.objects.all():
                next_review_date = flashcard.last_reviewed + timedelta(seconds=flashcard.interval)
                print(f"Term: {flashcard.term}, Interval: {flashcard.interval / 86400:.1f} days, "
                    f"Last Reviewed: {flashcard.last_reviewed}, Ease Factor: {flashcard.ease_factor:.2f}, "
                    f"Next Review Date: {next_review_date}")


    def test_flashcard_overdue_prioritisation(self):
        flashcards = Flashcard.objects.all()

        lineup = get_lineup(flashcards, 10)

        # Identify overdue flashcards
        overdue_flashcards = [
            flashcard for flashcard in flashcards
            if flashcard.last_reviewed + timedelta(seconds=flashcard.interval) <= now()
        ]

        # Debug print for overdue flashcards
        print("Overdue flashcards:")
        for flashcard in overdue_flashcards:
            print(f" - Term: {flashcard.term}, Last Reviewed: {flashcard.last_reviewed}, Interval: {flashcard.interval}")

        # Debug print for lineup
        print("\nLineup flashcards:")
        for i, flashcard in enumerate(lineup):
            print(f"{i+1}. Term: {flashcard.term}, Last Reviewed: {flashcard.last_reviewed}, Interval: {flashcard.interval}")

        # Assertion check
        self.assertTrue(
            all(flashcard in overdue_flashcards for flashcard in lineup[:len(overdue_flashcards)]),
            "Overdue flashcards should be prioritised in the lineup."
        )

        # Additional debugging for the assertion logic
        lineup_overdue_part = lineup[:len(overdue_flashcards)]
        print("\nChecking lineup[:len(overdue_flashcards)]:")
        for flashcard in lineup_overdue_part:
            print(f" - Term: {flashcard.term}, Last Reviewed: {flashcard.last_reviewed}, Interval: {flashcard.interval}")

        print("\nAre all flashcards in the initial part of the lineup overdue?")
        print(all(flashcard in overdue_flashcards for flashcard in lineup_overdue_part))

