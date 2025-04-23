# Brainspace

Brainspace is a flashcard-based learning platform built with Django. It uses spaced repetition and gamification to help users revise more effectively. You can make flashcard sets, play mini games, earn points, and collect badges.

The app is live at [brainspace.pythonanywhere.com](https://brainspace.pythonanywhere.com) until July.

---

## How it works

- Flashcards are grouped into sets you can create and review
- A spaced repetition system determines when you should see a card again
- You earn points and BrainBucks by reviewing cards in the mini games
- BrainBucks can be exchanged for badges and points will boost your position in friend leagues

---

## Project structure

- **Models** are in `cards/models.py`
- **Templates** can all be found in `cards/templates/cards/`
- **Views** are in `cards/views.py`

---

## Running locally

To run Brainspace on your own machine:

1. Install the requirements:

   ```bash
   pip install -r requirements.txt
   ```

2. Start the server on port 8080:

   ```bash
   python manage.py runserver 8080
   ```

3. Open your browser and go to:

   ```
   http://127.0.0.1:8080
   ```

---

## Email verification

If you're using the DCS system, email verification should work automatically via the DCS webmail server.

---

## Live version

You can check out the live version here:  
[https://brainspace.pythonanywhere.com](https://brainspace.pythonanywhere.com)  
This will be active until around July.

---

## Requirements

All dependencies are listed in `requirements.txt`.

