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

    path('logout/', user_logout, name='logout'),

    path('create/', views.create, name='create'),

    path('study/<int:set_id>/', views.study_set, name='study'),

    path('true_false/<int:set_id>/', views.true_false, name='true_false'),

    path('edit/<int:set_id>/', views.edit_set, name='edit'),

    path('delete/<int:set_id>/', views.delete_set, name='delete'),
]