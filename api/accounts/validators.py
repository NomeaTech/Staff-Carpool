from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CharacterMixValidator:
    """
    Passwords must contain a number, a lower case letter and an upper case
    letter. The password fields check the same in the browser, with the
    pattern PASSWORD_PATTERN (accounts/forms.py).
    """

    def validate(self, password, user=None):
        missing = []
        if not any(c.isdigit() for c in password):
            missing.append(_("a number"))
        if not any(c.islower() for c in password):
            missing.append(_("a lower case letter"))
        if not any(c.isupper() for c in password):
            missing.append(_("an upper case letter"))
        if missing:
            listed = missing[0] if len(missing) == 1 else _("%(first)s and %(last)s") % {
                "first": ", ".join(missing[:-1]), "last": missing[-1],
            }
            raise ValidationError(
                _("Your password must also contain %(missing)s.") % {"missing": listed},
                code="password_character_mix",
            )

    def get_help_text(self):
        return _("Your password must contain a number, a lower case letter and an upper case letter.")
