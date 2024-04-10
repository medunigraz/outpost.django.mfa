from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Field,
    Hidden,
    Layout,
    Submit,
)
from django import forms
from django.utils.translation import gettext as _


class EnrollmentUnlockForm(forms.Form):
    # terms_accepted = forms.BooleanField(required=True)
    image = forms.CharField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_action = "."
        self.helper.form_tag = True
        self.helper.form_id = "form"
        self.helper.layout = Layout(
            Field("terms_accepted"),
            Hidden("image", id="image", value=""),
            Submit(
                "unlock",
                _("Unlock my account"),
                css_class="btn btn-primary btn-lg btn-block",
            ),
        )
