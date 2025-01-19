import matplotlib.pyplot as plt

# Sample data for the flashcards (replace this with your actual data)
flashcards = [
    {"term": "France", "intervals": [1.7, 2.7, 3.8, 5.3, 5.9, 7.1, 6.2, 3.5, 1.0, 1.0, 1.0], "ease_factors": [1.7, 1.56, 1.42, 1.42, 1.42, 1.1, 1.2, 0.88, 0.56, 0.24, 0.0]},
    {"term": "Sweden", "intervals": [17.5, 28.5, 37.5, 37.3, 37.1, 25, 19.4, 12.3, 9, 3.7, 1.0], "ease_factors": [1.95, 1.63, 1.31, 0.99, 0.99, 0.67, 0.77, 0.63, 0.73, 0.41, 0.09]},
    {"term": "The Netherlands", "intervals": [4.5, 7.9, 11.3, 16.1, 24.6, 34.1, 47.3, 50.5, 37.7, 28.2, 12.0], "ease_factors": [1.75, 1.75, 1.43, 1.43, 1.53, 1.39, 1.39, 1.07, 0.75, 0.75, 0.43]},
    {"term": "Austria", "intervals": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], "ease_factors": [1.35, 1.03, 0.71, 0.71, 0.39, 0.25, 0.11, 0.11, 0, 0, 0.1]},
    {"term": "Argentina", "intervals": [1, 1.6, 2, 2, 1.2, 1, 1, 1, 1, 1, 1], "ease_factors": [1.6, 1.6, 1.28, 0.96, 0.64, 0.32, 0.42, 0.1, 0.2, 0.2, 0]},
    {"term": "Belgium", "intervals": [1.8, 2.7, 3.1, 3.2, 3.3, 3, 1.7, 1, 1, 1, 1], "ease_factors": [1.81, 1.49, 1.17, 1.03, 1.03, 0.89, 0.57, 0.57, 0.25, 0.25, 0]},
    {"term": "Norway", "intervals": [4.1, 8, 13.2, 19.7, 23.1, 19.8, 16.9, 16.2, 17.1, 15.6, 15.9], "ease_factors": [1.86, 1.96, 1.64, 1.5, 1.18, 0.86, 0.86, 0.96, 1.06, 0.92, 1.02]},
    {"term": "Greece", "intervals": [10.3, 14, 14.6, 15.1, 17.3, 21.4, 28.6, 34.4, 30.2, 29.6, 29], "ease_factors": [1.68, 1.36, 1.04, 1.04, 1.14, 1.24, 1.34, 1.2, 0.88, 0.98, 0.98]},
    {"term": "Denmark", "intervals": [1, 1.4, 1.5, 1.2, 1, 1, 1, 1, 1, 1, 1], "ease_factors": [1.73, 1.41, 1.09, 0.77, 0.45, 0.13, 0.23, 0.33, 0.19, 0, 0]},
    {"term": "Mexico", "intervals": [6.6, 11.2, 20.1, 29.6, 46.4, 58.3, 54.4, 50.7, 31, 14.6, 8.4], "ease_factors": [1.83, 1.69, 1.79, 1.47, 1.57, 1.25, 0.93, 0.93, 0.61, 0.47, 0.57]},
]

# Create the plot
plt.figure(figsize=(10, 6))

# Plot the intervals and ease factors over time for each flashcard
for card in flashcards:
    # Plot interval vs time
    plt.plot(card["ease_factors"], card["intervals"], marker='o', label=card['term'])

# Add titles and labels
plt.title('Ease Factor vs Interval for Flashcards Over Time')
plt.xlabel('Ease factor')
plt.ylabel('Interval (days)')

# Optionally, add a grid for better readability
plt.grid(True)

# Add a legend to distinguish different flashcards
plt.legend()

# Save the plot as an image file (e.g., PNG)
plt.savefig('flashcard_intervals_vs_ease_factors.png')

# If you don't want to display the plot, remove or comment out the following line
# plt.show()

print("Plot saved as 'flashcard_intervals_vs_ease_factors.png'")
