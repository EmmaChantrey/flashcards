import os, django, time
from django.db import models
from django.utils.timezone import now

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flashcards.settings')
django.setup()

from cards.models import Profile, FlashcardSet, Flashcard

def select_flashcard_set(profile):
    flashcard_sets = profile.flashcard_sets.all()
    if not flashcard_sets:
        print("You have no flashcard sets.")
        return None

    print("Select a flashcard set:")
    for idx, flashcard_set in enumerate(flashcard_sets, start=1):
        print(f"{idx}. {flashcard_set.name}")

    choice = int(input("Enter the number of the flashcard set: ")) - 1

    if 0 <= choice < len(flashcard_sets):
        return flashcard_sets[choice]
    else:
        print("Invalid choice.")
        return None

def quiz_user(flashcard_set):
    flashcards = flashcard_set.flashcards.all()

    if not flashcards:
        print("This flashcard set is empty.")
        return
    
    total_time = 0
    num_questions = 0

    print(f"Baseline for the set '{flashcard_set.name}' is: {flashcard_set.baseline:.2f} seconds.")

    for flashcard in flashcards:
        print(f"\nTerm: {flashcard.term} (last reviewed: {flashcard.last_reviewed})")
        start_time = time.time()

        user_definition = input("Enter your definition: ")
        time_taken = time.time() - start_time
        
        total_time += time_taken
        num_questions += 1

        if user_definition.strip().lower() == flashcard.definition.strip().lower():
            print("Correct!")
            if time_taken > 1.25 * flashcard_set.baseline:
                print("Performance level 2: Slow")
            elif time_taken > 0.75*flashcard_set.baseline and time_taken <= 1.25*flashcard_set.baseline:
                print("Performance level 3: Average")
            else:
                print("Performance level 4: Fast")
        else:
            print(f"Incorrect. The correct definition is: {flashcard.definition}")

        flashcard.last_reviewed = now()
        flashcard.save()

    if num_questions > 0:
        average_time = ((total_time / num_questions) + flashcard_set.baseline) / 2
        flashcard_set.baseline = average_time
        flashcard_set.save()
        print(f"New baseline for the set '{flashcard_set.name}' is: {flashcard_set.baseline:.2f} seconds.")

def main():
    username = input("Enter your username: ")
    try:
        profile = Profile.objects.get(user__username=username)
    except Profile.DoesNotExist:
        print("Profile not found.")
        return

    flashcard_set = select_flashcard_set(profile)
    if flashcard_set:
        quiz_user(flashcard_set)

if __name__ == "__main__":
    main()
