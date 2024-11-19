from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Profile, FlashcardSet, Flashcard, Badge, UserBadge, League, LeagueUser

admin.site.register(Profile)
admin.site.register(FlashcardSet)
admin.site.register(Flashcard)
admin.site.register(Badge)
admin.site.register(UserBadge)
admin.site.register(League)
admin.site.register(LeagueUser)