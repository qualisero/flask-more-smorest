"""Utility functions for Flask-Smorest CRUD operations."""

import bcrypt
import re

def generate_password_hash(password):
    if isinstance(password, str):
        password = password.encode("utf-8")
    return bcrypt.hashpw(password, bcrypt.gensalt())


def check_password_hash(password, hashed):
    if password is None or hashed is None:
        return False
    if isinstance(password, str):
        password = password.encode("utf-8")
    if isinstance(hashed, str):
        hashed = hashed.encode("utf-8")
    return bcrypt.checkpw(password, hashed)


def convert_snake_to_camel(word: str) -> str:
    """Convert snake_case string to CamelCase.

    Args:
        word: Snake case string to convert

    Returns:
        CamelCase version of the input string

    Example:
        >>> convert_snake_to_camel("user_profile")
        'UserProfile'
        >>> convert_snake_to_camel("simple")
        'simple'
    """
    if "_" not in word:
        return word
    return "".join(x.capitalize() or "_" for x in word.split("_"))


def convert_camel_to_snake(word):
    """🐪 → 🐍."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", word)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
