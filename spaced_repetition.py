from datetime import timedelta
import os, django
import random
from django.utils.timezone import now

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flashcards.settings')
django.setup()

# returns a list of overdue flashcards that the user needs to review
def get_overdue_flashcards(flashcards):
    overdue_flashcards = []
    max_interval = 31536000 # 1 year in seconds

    # checks what the next review date is for each flashcard
    for flashcard in flashcards:
        last_reviewed = flashcard.last_reviewed or now()
        interval = min(flashcard.interval, max_interval)
        try:
            next_review_date = last_reviewed + timedelta(seconds=interval)
        except OverflowError:
            print(f"OverflowError: Flashcard ID {flashcard.id} has an invalid interval: {flashcard.interval}")
            continue
        
        # if the next review date is in the past, add it to the overdue list
        if next_review_date <= now():
            overdue_flashcards.append((flashcard, next_review_date))

    overdue_flashcards = sorted(overdue_flashcards, key=lambda x: x[1]) # sort by next review date

    return [flashcard for flashcard, _ in overdue_flashcards]


# creates a lineup of flashcards for the user to review
def get_lineup(flashcards, number):
    lineup = []
    overdue_flashcards = get_overdue_flashcards(flashcards)
    overdue_copy = overdue_flashcards.copy()
    lineup.extend(overdue_flashcards[:number])

    # if the number of overdue flashcards is less than the required number, fill the rest with non-overdue flashcards
    while len(lineup) < number:
        non_overdue_flashcards = [
            card for card in flashcards
            if card not in overdue_flashcards and card not in lineup
        ]

        if non_overdue_flashcards:
            additional_cards_needed = number - len(lineup) # calculate how many more cards are needed
            to_add = random.sample(
                non_overdue_flashcards,
                min(additional_cards_needed, len(non_overdue_flashcards))
            )
            lineup.extend(to_add)
        else:
            break

    # if the number of overdue flashcards is still less than the required number, fill the rest with overdue flashcards
    while len(lineup) < number and overdue_copy:
        additional_cards_needed = number - len(lineup)
        cards_to_add = random.choices(overdue_copy, k=min(additional_cards_needed, len(overdue_copy)))
        lineup.extend(cards_to_add)
        overdue_copy = [card for card in overdue_copy if card not in cards_to_add]

    return lineup

# sm-2 ease factor formula
def ease_factor_calculation(ease_factor, performance_level):
    return max(ease_factor + (0.1 - (4 - performance_level) * (0.08 + (4 - performance_level) * 0.02)), 1.3)
