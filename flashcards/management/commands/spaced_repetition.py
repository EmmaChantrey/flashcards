from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from flashcards.models import FlashcardSet, Flashcard
import random

class Command(BaseCommand):
    help = 'Study flashcards from a selected set'

    def handle(self, *args, **options):
        # Get the user (for simplicity, using the first user - you might want to modify this)
        try:
            user = User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR('No users found in the database.'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error accessing user: {e}'))
            return

        # Get user's flashcard sets
        flashcard_sets = user.profile.flashcard_sets.all()

        if not flashcard_sets:
            self.stdout.write(self.style.ERROR('No flashcard sets found.'))
            return

        # Display available sets
        self.stdout.write(self.style.SUCCESS('Available Flashcard Sets:'))
        for i, flashcard_set in enumerate(flashcard_sets, 1):
            self.stdout.write(f'{i}. {flashcard_set.name}')

        # Prompt for set selection
        while True:
            try:
                set_choice = int(input('Enter the number of the set you want to study: '))
                selected_set = flashcard_sets[set_choice - 1]
                break
            except (ValueError, IndexError):
                self.stdout.write(self.style.ERROR('Invalid selection. Please try again.'))

        # Get flashcards in the selected set
        cards = list(selected_set.flashcards.all())

        if not cards:
            self.stdout.write(self.style.ERROR('No cards in this set.'))
            return

        # Study session
        self.stdout.write(self.style.SUCCESS(f'\nStarting study session for {selected_set.name}'))
        
        # Track score
        correct_count = 0
        total_count = len(cards)

        # Shuffle cards
        random.shuffle(cards)

        for card in cards:
            # Clear screen (simple method)
            print('\n' * 50)

            # Show term
            self.stdout.write(self.style.NOTICE(f'Term: {card.term}'))
            
            # Get user's definition
            user_definition = input('Enter your definition: ').strip()

            # Check definition
            if user_definition.lower() == card.definition.lower():
                self.stdout.write(self.style.SUCCESS('Correct! 🎉'))
                correct_count += 1
            else:
                self.stdout.write(self.style.ERROR(f'Incorrect. The correct definition is: {card.definition}'))

            # Prompt to continue
            input('\nPress Enter to continue...')

        # Show final score
        self.stdout.write(self.style.SUCCESS(f'\nStudy Session Complete!'))
        self.stdout.write(f'Score: {correct_count}/{total_count} ({(correct_count/total_count)*100:.2f}%)')