# need to edit

# The view will assemble requested data and style it before generating a HTTP response

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .forms import SignUpForm
from django.contrib import messages

from django.views.generic import (
    ListView,
    CreateView,
    UpdateView
)


import random

def landing_page(request):
    return render(request, 'cards/landing.html')

def signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('signup')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return redirect('signup')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return redirect('signup')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()  # This triggers the profile creation via signals
        login(request, user)  # Log the user in after signup

        messages.success(request, "Account created successfully!")
        return redirect('dashboard')

    return render(request, 'cards/signup.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        # Authenticate the user
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # If the user is authenticated, log them in
            login(request, user)
            messages.success(request, "You have successfully logged in.")
            return redirect('dashboard')
        else:
            # If authentication fails, show an error message
            messages.error(request, "Invalid username or password.")
            return redirect('login')  # Redirect to the login page for retry
    
    return render(request, 'cards/login.html')  # Render the login template



@login_required
def dashboard(request):
    return render(request, 'cards/dashboard.html', {
        'username': request.user.username,
    })

def user_logout(request):
    logout(request)  # Log out the user
    return redirect('login')  # Redirect to the login page or home page after logout

def create(request):
    return render(request, 'cards/create.html')

# #orders cards by box (ascending) and date created (descending)
# class CardListView(ListView):
#     model = Card
#     queryset = Card.objects.all().order_by("box", "-date_created")

# class CardCreateView(CreateView):
#     model = Card
#     fields = ["question", "answer", "box"]
#     success_url = reverse_lazy("card-create")

# class CardUpdateView(CardCreateView, UpdateView):
#     success_url = reverse_lazy("card-list")

# class BoxView(CardListView):
#     template_name = "cards/box.html"
#     form_class = CardCheckForm

#     def get_queryset(self):
#         return Card.objects.filter(box=self.kwargs["box_num"])

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context["box_number"] = self.kwargs["box_num"]

#         # if there's a card in the box, select a random one to present
#         if self.object_list:
#             context["check_card"] = random.choice(self.object_list)
#         return context
    
#     def post(self, request, *args, **kwargs):
#         form = self.form_class(request.POST)
#         if form.is_valid():
#             card = get_object_or_404(Card, id=form.cleaned_data["card_id"])
#             card.move(form.cleaned_data["solved"])

#         return redirect(request.META.get("HTTP_REFERER"))