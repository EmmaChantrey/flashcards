# when an HTTP request comes in, it first comes to this file and searches through the 
# configured URL patterns. It stops at the first matching view from views.py

from django.urls import path

from . import views
from django.contrib.auth import views as auth_views
from .views import user_logout

urlpatterns = [
    path('', views.landing_page, name='landing'),

    # path(
    #     "",
    #     views.CardListView.as_view(),
    #     name="card-list"
    # ),

    # path(
    #     "new",
    #     views.CardCreateView.as_view(),
    #     name="card-create"
    # ),

    # path(
    #     "edit/<int:pk>",
    #     views.CardUpdateView.as_view(),
    #     name="card-update"
    # ),

    # path(
    #     "box/<int:box_num>",
    #     views.BoxView.as_view(),
    #     name="box"
    # ),

    path('login/',
        views.login_view, 
        name='login'
    ),

    path('signup/', views.signup, name='signup'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('logout/', user_logout, name='logout'),

    path('create/', views.create, name='create'),
]