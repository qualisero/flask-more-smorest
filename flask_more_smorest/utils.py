"""Utility functions for Flask-Smorest CRUD operations.

This module provides common utility functions for password hashing
and string case conversion.
"""

import re

import bcrypt


def generate_password_hash(password: str | bytes) -> bytes:
    """Generate a secure bcrypt hash for a password.

    Args:
        password: The password to hash (string or bytes)

    Returns:
        The hashed password as bytes

    Example:
        >>> hashed = generate_password_hash("my_secure_password")
        >>> isinstance(hashed, bytes)
        True
    """
    if isinstance(password, str):
        password = password.encode("utf-8")
    return bcrypt.hashpw(password, bcrypt.gensalt())


def check_password_hash(password: str | bytes | None, hashed: bytes | str | None) -> bool:
    """Check if a password matches a bcrypt hash.

    Args:
        password: The password to check (string or bytes)
        hashed: The hashed password to compare against (bytes or string)

    Returns:
        True if the password matches the hash, False otherwise

    Example:
        >>> hashed = generate_password_hash("password123")
        >>> check_password_hash("password123", hashed)
        True
        >>> check_password_hash("wrong", hashed)
        False
    """
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


def convert_camel_to_snake(word: str) -> str:
    """Convert CamelCase string to snake_case.

    Args:
        word: CamelCase string to convert

    Returns:
        snake_case version of the input string

    Example:
        >>> convert_camel_to_snake("UserProfile")
        'user_profile'
        >>> convert_camel_to_snake("APIKey")
        'api_key'
    """
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", word)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
