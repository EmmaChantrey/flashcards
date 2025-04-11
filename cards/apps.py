from django.apps import AppConfig


class CardsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cards'

    def ready(self):
        import cards.signals
        if not hasattr(self, '_nltk_initialized'):
            from .nltk_setup import initialize_nltk
            initialize_nltk()
            self._nltk_initialized = True
