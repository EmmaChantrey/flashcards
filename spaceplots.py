import matplotlib.pyplot as plt

flashcards = [
    {"term": "Card 1", "intervals": [1, 1, 1, 1, 6, 1, 6, 16, 43, 115, 306], "ease_factors": [2.5, 2.36, 2.36, 2.36, 2.22, 2.22, 2.22, 2.08, 2.08, 2.08, 1.94]},
    {"term": "Card 2", "intervals": [1, 1, 1, 1, 1, 1, 6, 15, 39, 95, 217], "ease_factors": [2.5, 2.5, 2.6, 2.46, 2.32, 2.18, 2.18, 2.28, 2.14, 2, 2]},
    {"term": "Card 3", "intervals": [1, 1, 1, 1, 1, 1, 6, 1, 1, 6, 16], "ease_factors": [2.5, 2.5, 2.6, 2.46, 2.46, 2.32, 2.32, 2.18, 2.18, 2.18, 2.18]},
    {"term": "Card 4", "intervals": [1, 1, 1, 1, 6, 1, 6, 17, 46, 123, 340], "ease_factors": [2.5, 2.36, 2.22, 2.22, 2.22, 2.22, 2.32, 2.32, 2.42, 2.52, 2.62]},
]

plt.figure(figsize=(10, 6))

for card in flashcards:
    plt.plot(range(1, len(card["intervals"]) + 1), card["intervals"], marker='o', label=card['term'])

plt.title('Interval vs Repetition of Flashcards (Dynamic success rate)')
plt.xlabel('Repetition Number')
plt.ylabel('Interval (days)')
plt.grid(True)
plt.legend()

plt.savefig('flashcard_intervals.png')
