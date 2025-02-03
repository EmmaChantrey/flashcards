# when an HTTP request comes in, it first comes to this file and searches through the 
# configured URL patterns. It stops at the first matching view from views.py

from django.urls import path

from . import views
from django.contrib.auth import views as auth_views
from .views import user_logout

urlpatterns = [
    path('', views.landing_page, name='landing'),

    path('login/', views.login_view, name='login'),

    path('signup/', views.signup, name='signup'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('flashcard_sidebar/', views.flashcard_sidebar, name='flashcard_sidebar'),
    
    path('badge_shop/', views.badge_shop, name='badge_shop'),

    path('purchase-badge/<int:badge_id>/', views.purchase_badge, name='purchase_badge'),

    path('logout/', user_logout, name='logout'),

    path('create/', views.create, name='create'),

    path('about/', views.about, name='about'),

    path('profile/', views.profile, name='profile'),

    path('search-users/', views.search_users, name='search_users'),

    path('send-friend-request/<int:user_id>/', views.send_friend_request, name='send_friend_request'),

    path('study/<int:set_id>/', views.study_set, name='study'),

    path('true_false/<int:set_id>/setup/', views.setup_true_false, name='setup_true_false'),

    path('true_false/<int:set_id>/', views.true_false, name='true_false'),

    path('true_false/<int:set_id>/check/', views.true_false_check, name='true_false_check'),

    path('fill_the_blanks/<int:set_id>/setup/', views.setup_fill_the_blanks, name='setup_fill_the_blanks'),

    path('fill_the_blanks/<int:set_id>/', views.fill_the_blanks, name='fill_the_blanks'),

    path('fill_the_blanks/<int:set_id>/check/', views.fill_the_blanks_check, name='fill_the_blanks_check'),

    path('quiz/<int:set_id>/setup/', views.setup_quiz, name='setup_quiz'),

    path('quiz/<int:set_id>/', views.quiz, name='quiz'),

    path('quiz/<int:set_id>/check/', views.quiz_check, name='quiz_check'),

    path('match/<int:set_id>/setup/', views.setup_match, name='setup_match'),

    path('match/<int:set_id>/', views.match, name='match'),

    path('evaluate_match/<int:set_id>/', views.evaluate_match, name='evaluate_match'),

    path('clear_feedback/', views.clear_feedback, name='clear_feedback'),

    path('edit/<int:set_id>/', views.edit_set, name='edit'),

    path('delete/<int:set_id>/', views.delete_set, name='delete'),

    path('game_end/<int:set_id>/', views.game_end, name='game_end'),

]