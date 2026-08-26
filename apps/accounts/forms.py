from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

User = get_user_model()


class LoginForm(AuthenticationForm):
    """Style `AuthenticationForm` and set browser autofill hints.

    Use the form's field-specific validation so inactive accounts and invalid passwords
    produce distinct errors.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "username", "autofocus": True}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "form-control", "autocomplete": "current-password"}
        )


class SignupForm(UserCreationForm):
    """Create accounts through the public registration form.

    Subclassing `UserCreationForm` rather than writing the fields by hand is what keeps
    the password confirmation and every rule in AUTH_PASSWORD_VALIDATORS applying to
    self-registered accounts. A hand-rolled form silently opts out of both.

    The form does not set `is_staff` or `is_superuser`, so a registered account starts with
    no admin access. Grant staff access in the admin.
    """

    email = forms.EmailField(
        required=False,
        help_text="Optional, and only used to reach you about your jobs.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bootstrap styling lives here rather than in the template so the fields can be
        # rendered by looping over the form, which is what surfaces validator messages.
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
