# need to edit this

# The model defines database tables, behaviours, and supports queries from the database
# This data is sent back to the view.

from django.contrib.auth.models import User
from django.db import models

# # for the leitner method, using boxes 1-5
# NUM_BOXES = 5
# BOXES = range(1, NUM_BOXES + 1)

# class Card(models.Model):
#     question = models.CharField(max_length=100)
#     answer = models.CharField(max_length=100)
#     box = models.IntegerField(
#         choices=zip(BOXES, BOXES),
#         default=BOXES[0],
#     )
#     date_created = models.DateTimeField(auto_now_add=True)

#     def move(self, solved):
#         new_box = self.box + 1 if solved else BOXES[0]

#         if new_box in BOXES:
#             self.box = new_box
#             self.save()

#         return self

#     def __str__(self):
#         return self.question


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    points = models.IntegerField(default=0)
    brainbucks = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class FlashcardSet(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='flashcard_sets')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class Flashcard(models.Model):
    set = models.ForeignKey(FlashcardSet, on_delete=models.CASCADE, related_name='flashcards')
    term = models.TextField()
    definition = models.TextField()
    interval = models.IntegerField(default=1)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    ease_factor = models.FloatField(default=2.5)
    streak = models.IntegerField(default=0)
    baseline = models.FloatField(default=0)

    def __str__(self):
        return self.term
    

class Badge(models.Model):
    name = models.CharField(max_length=255)
    price = models.IntegerField()
    description = models.TextField()
    image = models.ImageField(upload_to='badges/', null=True, blank=True)

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='user_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='user_badges')
    displayed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"
    

class League(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='owned_leagues')

    def __str__(self):
        return self.name
    

class LeagueUser(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='league_users')
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='league_users')
    score = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} in {self.league.name}"
    

