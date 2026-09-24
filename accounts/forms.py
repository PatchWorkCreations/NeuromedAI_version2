from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm

User = get_user_model()


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email address",
        widget=forms.EmailInput(attrs={
            "class": "field-input",
            "placeholder": "you@email.com",
            "autocomplete": "email",
        }),
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": "field-input",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        }),
    )

    error_messages = {
        "invalid_login": "That email and password didn’t match. Try again.",
        "inactive": "This account is inactive.",
    }

    def clean(self):
        email = (self.cleaned_data.get("username") or "").strip()
        password = self.cleaned_data.get("password")
        if not email or not password:
            return self.cleaned_data
        user = (
            User.objects.filter(email__iexact=email).first()
            or User.objects.filter(username__iexact=email).first()
        )
        if user is None or not user.check_password(password):
            raise forms.ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
            )
        if not user.is_active:
            raise forms.ValidationError(self.error_messages["inactive"], code="inactive")
        self.user_cache = user
        return self.cleaned_data


class SignupForm(forms.Form):
    first_name = forms.CharField(
        label="First name",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "field-input", "placeholder": "Maria", "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Last name",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "field-input", "placeholder": "Santos", "autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={
            "class": "field-input",
            "placeholder": "maria@example.com",
            "autocomplete": "email",
        }),
    )
    profession = forms.CharField(
        label="Profession",
        required=False,
        max_length=120,
        widget=forms.TextInput(attrs={
            "class": "field-input",
            "placeholder": "Nurse, caregiver, family",
        }),
    )
    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "field-input",
            "placeholder": "marie_g",
            "autocomplete": "username",
        }),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            "class": "field-input",
            "placeholder": "••••••••",
            "autocomplete": "new-password",
        }),
        help_text="8+ chars, letters, numbers & symbols.",
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={
            "class": "field-input",
            "placeholder": "••••••••",
            "autocomplete": "new-password",
        }),
    )
    terms = forms.BooleanField(
        error_messages={"required": "Please agree to the Terms and Privacy Policy."},
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is taken.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords didn’t match.")
        if p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
        )
        profile = user.profile
        profile.profession = self.cleaned_data.get("profession") or ""
        profile.save(update_fields=["profession"])
        return user


class StyledPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "field-input", "placeholder": "you@email.com"}),
    )


class StyledSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="New password",
        widget=forms.PasswordInput(attrs={"class": "field-input", "placeholder": "••••••••"}),
    )
    new_password2 = forms.CharField(
        label="Confirm new password",
        widget=forms.PasswordInput(attrs={"class": "field-input", "placeholder": "••••••••"}),
    )
