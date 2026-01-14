"""Authentication configuration for Alpha Locks Reports"""
import hashlib
import os

# Users database (username: hashed_password)
# To add a new user, run: 
#   python -c "import hashlib; print(hashlib.sha256('YOUR_PASSWORD'.encode()).hexdigest())"
#
# Current users:
#   oren / WGuE6IrtC9PB

USERS = {
    "oren": "f6dbf959337af3615cc6b2221378242f512eaa15a42dea2fe58a46ac87f5e8f2",   # password: WGuE6IrtC9PB
}

# Session timeout in seconds (optional, not implemented yet)
SESSION_TIMEOUT = 3600  # 1 hour

def hash_password(password: str) -> str:
    """Hash a password using SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(username: str, password: str) -> bool:
    """Verify username and password."""
    if username not in USERS:
        return False
    return USERS[username] == hash_password(password)

def get_users() -> list:
    """Get list of usernames."""
    return list(USERS.keys())
