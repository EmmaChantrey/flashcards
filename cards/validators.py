import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class CustomPasswordValidator:
    def validate(self, password, user=None):

        if len(password) < 8:
            raise ValidationError(_("Password must be at least 8 characters long."))

        if not re.search(r'[A-Z]', password):
            raise ValidationError(_("Password must contain at least one uppercase letter."))

        if not re.search(r'\d', password):
            raise ValidationError(_("Password must contain at least one digit."))

        if not re.search(r'[.,!?\-*&]', password):
            raise ValidationError(_("Password must contain at least one special character (.,!?-*&)"))

    def get_help_text(self):
        return _(
            "Your password must be at least 8 characters long, contain at least one digit, "
            "one uppercase letter, and one special character (.,!?-*&)."
        )
