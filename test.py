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


# class SignupViewTests(TestCase):
#     def setUp(self):
#         self.client = Client()
#         self.signup_url = reverse('signup')
#         self.valid_data = {
#             'username': 'testuser',
#             'email': 'testuser@example.com',
#             'password': 'securepassword123',
#             'confirm_password': 'securepassword123',
#         }

#     def test_signup_successful(self):
#         response = self.client.post(self.signup_url, self.valid_data)
#         self.assertEqual(response.status_code, 302)
#         self.assertTrue(User.objects.filter(username='testuser').exists())
#         print("Test `test_signup_successful` passed.")

#     def test_signup_username_already_taken(self):
#         User.objects.create_user(username='testuser', email='existing@example.com', password='password')
#         response = self.client.post(self.signup_url, self.valid_data)
#         self.assertEqual(response.status_code, 302)

#         messages = list(get_messages(response.wsgi_request))
#         self.assertEqual(len(messages), 1)
#         self.assertEqual(str(messages[0]), "Username is already taken.")
#         print("Test `test_signup_username_already_taken` passed.")

#     def test_signup_email_already_registered(self):
#         User.objects.create_user(username='existinguser', email='testuser@example.com', password='password')
#         response = self.client.post(self.signup_url, self.valid_data)
#         self.assertEqual(response.status_code, 302)

#         messages = list(get_messages(response.wsgi_request))
#         self.assertEqual(len(messages), 1)
#         self.assertEqual(str(messages[0]), "Email is already registered.")
#         print("Test `test_signup_email_already_registered` passed.")

#     def test_signup_passwords_do_not_match(self):
#         invalid_data = self.valid_data.copy()
#         invalid_data['confirm_password'] = 'differentpassword'
#         response = self.client.post(self.signup_url, invalid_data)
#         self.assertEqual(response.status_code, 302)

#         messages = list(get_messages(response.wsgi_request))
#         self.assertEqual(len(messages), 1)
#         self.assertEqual(str(messages[0]), "Passwords do not match.")
#         print("Test `test_signup_passwords_do_not_match` passed.")

#     def test_signup_invalid_method(self):
#         response = self.client.get(self.signup_url)
#         self.assertEqual(response.status_code, 200)
#         self.assertTemplateUsed(response, 'cards/signup.html')
#         print("Test `test_signup_invalid_method` passed.")


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
                user_answer = random.choices([True, False], weights=[i * 10, 1000 - (i * 10)], k=1)[0]
                #user_answer = random.choices([True, False], weights=[0.5, 0.5])[0]
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
            # print(f"Term: {flashcard.term}, Interval: {flashcard.interval / 86400:.1f} days, "
            #     f"Last Reviewed: {flashcard.last_reviewed}, Ease Factor: {flashcard.ease_factor:.2f}, "
            #     f"Next Review Date: {next_review_date}")
            expected_next_review_date = flashcard.last_reviewed + timedelta(seconds=flashcard.interval)
            self.assertEqual(next_review_date, expected_next_review_date, "Next review date calculation is incorrect.")


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

