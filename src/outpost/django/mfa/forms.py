from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Field,
    Hidden,
    Layout,
    Submit,
)
from django import forms
from django.utils.translation import gettext as _
from outpost.django.base.layout import IconButton


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
            Hidden("image", id="image", value=""),
            IconButton(
                "fa fa-unlock",
                _("Unlock my account"),
                type="submit",
                css_class="btn btn-primary btn-lg btn-block",
            ),
        )
