import secrets


def new_public_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"

