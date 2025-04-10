from datetime import timedelta
import os, django, time
import random
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
    

def get_overdue_flashcards(flashcards):
    overdue_flashcards = []
    max_interval = 31536000

    for flashcard in flashcards:
        last_reviewed = flashcard.last_reviewed or now()
        interval = min(flashcard.interval, max_interval)
        try:
            next_review_date = last_reviewed + timedelta(seconds=interval)
        except OverflowError:
            print(f"OverflowError: Flashcard ID {flashcard.id} has an invalid interval: {flashcard.interval}")
            continue
        
        if next_review_date <= now():
            overdue_flashcards.append((flashcard, next_review_date))

    overdue_flashcards = sorted(overdue_flashcards, key=lambda x: x[1])

    return [flashcard for flashcard, _ in overdue_flashcards]

def get_lineup(flashcards, number):
    lineup = []
    overdue_flashcards = get_overdue_flashcards(flashcards)
    overdue_copy = overdue_flashcards.copy()
    lineup.extend(overdue_flashcards[:number])

    while len(lineup) < number:
        non_overdue_flashcards = [
            card for card in flashcards
            if card not in overdue_flashcards and card not in lineup
        ]

        if non_overdue_flashcards:
            additional_cards_needed = number - len(lineup)
            to_add = random.sample(
                non_overdue_flashcards,
                min(additional_cards_needed, len(non_overdue_flashcards))
            )
            lineup.extend(to_add)
        else:
            break

    while len(lineup) < number and overdue_copy:
        additional_cards_needed = number - len(lineup)
        cards_to_add = random.choices(overdue_copy, k=min(additional_cards_needed, len(overdue_copy)))
        lineup.extend(cards_to_add)
        overdue_copy = [card for card in overdue_copy if card not in cards_to_add]

    return lineup



def quiz_user(flashcard_set):
    flashcards = flashcard_set.flashcards.all()

    if not flashcards:
        print("This flashcard set is empty.")
        return
    
    total_time = 0
    num_questions = 0

    lineup = get_lineup(flashcards)

    print(f"Baseline for the set '{flashcard_set.name}' is: {flashcard_set.baseline:.2f} seconds.")

    for flashcard in lineup:
        print(f"\nTerm: {flashcard.term} (last reviewed: {flashcard.last_reviewed}), ease factor: {flashcard.ease_factor}")
        start_time = time.time()

        user_definition = input("Enter your definition: ")
        time_taken = time.time() - start_time
        
        total_time += time_taken
        num_questions += 1

        if user_definition.strip().lower() == flashcard.definition.strip().lower():
            print("Correct!")
            flashcard.repetition += 1
            if time_taken > 1.25 * flashcard_set.baseline:
                print("Performance level 2: Slow")
                # decrease ease factor
                flashcard.ease_factor =  ease_factor_calculation(flashcard.ease_factor, 2)
            elif time_taken > 0.75 * flashcard_set.baseline and time_taken <= 1.25 * flashcard_set.baseline:
                print("Performance level 3: Average")
                # keep ease factor the same
                flashcard.ease_factor =  ease_factor_calculation(flashcard.ease_factor, 3)
            else:
                print("Performance level 4: Fast")
                # increase ease factor
                flashcard.ease_factor =  ease_factor_calculation(flashcard.ease_factor, 4)
        else:
            print(f"Incorrect. The correct definition is: {flashcard.definition}")
            # assuming incorrect, not skipped
            flashcard.repetition = 1

        print(f"New ease factor for the flashcard '{flashcard.term}' is: {flashcard.ease_factor:.2f}")
        flashcard.last_reviewed = now()

        if flashcard.repetition == 1:
            flashcard.interval = 86400
        elif flashcard.repetition == 2:
            flashcard.interval = 86400 * 6
        else:
            flashcard.interval = max(flashcard.interval * flashcard.ease_factor, 86400)

        flashcard.save()

    if num_questions > 0:
        average_time = ((total_time / num_questions) + flashcard_set.baseline) / 2
        flashcard_set.baseline = average_time
        flashcard_set.save()
        print(f"New baseline for the set '{flashcard_set.name}' is: {flashcard_set.baseline:.2f} seconds.")


def ease_factor_calculation(ease_factor, performance_level):
    return max(ease_factor + (0.1 - (4 - performance_level) * (0.08 + (4 - performance_level) * 0.02)), 1.3)

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
