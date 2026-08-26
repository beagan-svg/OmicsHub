from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.forms import SignupForm


@require_http_methods(["GET", "POST"])
def signup(request):
    """Create an account and sign the user in.

    Already-authenticated users are redirected away, as `LoginView` does with
    `redirect_authenticated_user`: submitting this form while signed in would otherwise
    silently swap the session to the new account.
    """
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to OmicsHub, {user.get_username()}.")
            return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})


@require_http_methods(["POST"])
def logout_view(request):
    """Sign the user out and say so.

    Display a confirmation because the sign-in page is otherwise identical after logout.
    """
    logout(request)
    messages.info(request, "You've been signed out.")
    return redirect(settings.LOGOUT_REDIRECT_URL)
