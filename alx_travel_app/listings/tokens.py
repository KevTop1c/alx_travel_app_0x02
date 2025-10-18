# tokens.py (create new file)
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomAccessToken(AccessToken):
    @classmethod
    def for_user(cls, user):
        """
        Override this method to use user.pk instead of user.id
        """
        token = cls()

        # Use user.pk instead of user.id
        token[cls.token_type] = str(user.pk)

        # Add other claims
        token["email"] = user.email
        token["username"] = user.username

        return token
