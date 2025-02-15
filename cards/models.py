
# The model defines database tables, behaviours, and supports queries from the database
# This data is sent back to the view.

from datetime import timedelta
from django.contrib.auth.models import User
from django.db import models
from django.utils.timezone import now
from math import ceil


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    points = models.IntegerField(default=0)
    brainbucks = models.IntegerField(default=0)
    friends = models.ManyToManyField('self', through='Friendship', symmetrical=False, related_name='friend_list')

    def __str__(self):
        return f"{self.user.username}'s Profile"
    

    def add_friend(self, profile):
        Friendship.objects.create(sender=self, receiver=profile)

    def remove_friend(self, profile):
        Friendship.objects.filter(
            models.Q(sender=self, receiver=profile) | models.Q(sender=profile, receiver=self)
        ).delete()

    def get_friends(self):
        return Profile.objects.filter(
            models.Q(friendship_requests_sent__receiver=self, friendship_requests_sent__status='accepted') |
            models.Q(friendship_requests_received__sender=self, friendship_requests_received__status='accepted')
        )
    
    def get_requests(self):
        return Profile.objects.filter(friendship_requests_sent__receiver=self, friendship_requests_sent__status='pending')
    
    def get_sent_requests(self):
        return Profile.objects.filter(id__in=Friendship.objects.filter(sender=self, status='pending').values_list('receiver_id', flat=True))
    
    def get_leagues(self):
        return League.objects.filter(models.Q(owner=self) | models.Q(league_users__user=self)).distinct()




class Friendship(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    sender = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='friendship_requests_sent')
    receiver = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='friendship_requests_received')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.user.username} → {self.receiver.user.username} ({self.status})"

    class Meta:
        unique_together = ('sender', 'receiver')

    def accept(self):
        self.status = 'accepted'
        self.save()

    def reject(self):
        self.status = 'rejected'
        self.save()


class FlashcardSet(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='flashcard_sets')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    baseline = models.FloatField(default=0)
    quickest_time = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name
    

class Flashcard(models.Model):
    set = models.ForeignKey(FlashcardSet, on_delete=models.CASCADE, related_name='flashcards')
    term = models.TextField()
    definition = models.TextField()
    interval = models.FloatField(default=86400)
    last_reviewed = models.DateTimeField(null=True, blank=True)
    ease_factor = models.FloatField(default=2.5)
    repetition = models.IntegerField(default=1)

    def __str__(self):
        return self.term
    
    def save(self, *args, **kwargs):
        self.interval = ceil(self.interval / 86400) * 86400
        super().save(*args, **kwargs)
    

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
        return f"{self.user.user.username} - {self.badge.name}"
    

class League(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='owned_leagues')

    def __str__(self):
        return self.name
    

class LeagueUser(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='league_users')
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='league_users')
    score = models.IntegerField(default=0)
    last_reset = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.user.username} in {self.league.name}"
    
    def reset_score(self):
        if now() - self.last_reset >= timedelta(weeks=1):
            self.score = 0
            self.last_reset = now()
            self.save()

