from django import forms

from apps.catalog.models import Stage


class SyncForm(forms.Form):
    """Load a vendor batch from OCS into the local mirror.

    Batch is the only selector offered here: it is how work actually arrives, and it keeps
    this form from re-deriving the either/or rule the API's serializer already owns.
    """

    batch_name_from_vendor = forms.CharField(
        label="Batch name from vendor",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "MTX-22068", "class": "form-control"}),
    )


class SubmissionForm(forms.Form):
    """Store the user's submission choices separately from its fastq samples.

    Every value here is substituted into an `ocs` command, so none of it can be taken from
    the POST as typed. The email in particular is written into the command the worker runs
and stored on the queue entry by `bulk_create`, which skips model validation. This is
    the only place it is checked.
    """

    modality = forms.CharField(required=False, max_length=20)
    force = forms.ChoiceField(
        choices=[(Stage.ALIGN.value, Stage.ALIGN.label), (Stage.POST_ALIGN.value, Stage.POST_ALIGN.label)],
        required=False,
    )
    batch_processing = forms.BooleanField(required=False)
    email = forms.EmailField(required=False)


class ConfigUploadForm(forms.Form):
    """Read an uploaded submission manifest as text.

    The parse and the shape are `workflows.config_loader`'s job; this only settles that
    there is a file, that it is small enough to hold in memory, and that it is text.
    """

    MAX_BYTES = 2 * 1024 * 1024

    file = forms.FileField(label="Config file")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > self.MAX_BYTES:
            raise forms.ValidationError("Config files are under 2 MB.")
        try:
            self.raw = uploaded.read().decode("utf-8")
        except UnicodeDecodeError:
            raise forms.ValidationError("That file is not UTF-8 text.") from None
        return uploaded
