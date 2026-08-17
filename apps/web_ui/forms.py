from django import forms

from apps.sample_catalog.models import Stage


class SyncForm(forms.Form):
    """Load a vendor batch into the local mirror."""

    batch_name_from_vendor = forms.CharField(
        label="Batch name from vendor",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "MTX-22068", "class": "form-control"}),
    )


class SubmissionForm(forms.Form):
    """Validate submission options that apply to selected fastq samples."""

    modality = forms.CharField(required=False, max_length=20)
    force = forms.ChoiceField(
        choices=[(Stage.ALIGN.value, Stage.ALIGN.label), (Stage.POST_ALIGN.value, Stage.POST_ALIGN.label)],
        required=False,
    )
    batch_processing = forms.BooleanField(required=False)
    email = forms.EmailField(required=False)


class ConfigUploadForm(forms.Form):
    """Validate the uploaded manifest file and read its UTF-8 text."""

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
