from __future__ import annotations

from django import forms

from apps.accounts.models import User


class LinkUserForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(employee__isnull=True).order_by("email"),
        label="User account",
        help_text="Only accounts not already linked to another employee are listed.",
    )


class UnlinkUserConfirmForm(forms.Form):
    """No fields — the confirm page is a plain "are you sure", but a real
    FormView still needs a form to POST/validate against."""
