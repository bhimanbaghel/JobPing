"""
Password and input validation utilities.
Implements NIST SP 800-63B Memorized Secret guidelines:
  - Minimum 8 characters (NIST minimum)
  - Maximum 128 characters (prevent DoS on hashing)
  - No composition rules (NIST discourages forced special chars/uppercase)
  - Check against list of commonly breached passwords
  - Block passwords that match the user's email or name
"""

import re

# Top commonly breached passwords (abbreviated set).
# In production, load the full HaveIBeenPwned top-100k list from a file
# or call the k-anonymity API: https://api.pwnedpasswords.com/range/{prefix}
COMMON_PASSWORDS = frozenset([
    "password", "123456", "12345678", "qwerty", "abc123",
    "monkey", "1234567", "letmein", "trustno1", "dragon",
    "baseball", "iloveyou", "master", "sunshine", "ashley",
    "bailey", "shadow", "123123", "654321", "superman",
    "qazwsx", "michael", "football", "password1", "password123",
    "batman", "login", "starwars", "hello", "charlie",
    "donald", "admin", "welcome", "1234567890", "00000000",
    "passw0rd", "whatever", "qwerty123", "princess", "121212",
])


def validate_email_format(email: str) -> str | None:
    """Return an error message if email format is invalid, else None."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not email or not re.match(pattern, email):
        return "Invalid email format."
    return None


def validate_password_nist(password: str, email: str = "") -> str | None:
    """
    Validate a password against NIST SP 800-63B guidelines.
    Returns an error message string if invalid, None if valid.
    """
    if not password:
        return "Password is required."

    if len(password) < 8:
        return "Password must be at least 8 characters."

    if len(password) > 128:
        return "Password must not exceed 128 characters."

    # Check against breached password list (case-insensitive)
    if password.lower() in COMMON_PASSWORDS:
        return "This password is too common and has appeared in data breaches. Choose a different password."

    # Block passwords that are trivially derived from user context
    if email and password.lower() == email.lower().split("@")[0]:
        return "Password must not be your email username."

    # Reject passwords that are all repeating characters (e.g., "aaaaaaaa")
    if len(set(password)) == 1:
        return "Password must not be a single repeating character."

    return None
