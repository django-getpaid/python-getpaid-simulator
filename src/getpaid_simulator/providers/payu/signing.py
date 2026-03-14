"""PayU signature signing module.

Implements the exact signature algorithm used by PayU for callback verification.
Reference: getpaid-payu/src/getpaid_payu/processor.py:184
"""

from hashlib import sha256


def compute_signature(body: bytes, second_key: str) -> str:
    """
    Compute PayU signature.

    Algorithm (from processor.py:184): hex(SHA256(body + second_key))

    Args:
        body: Raw HTTP body bytes
        second_key: PayU second_key from config

    Returns:
        Hexadecimal signature string
    """
    return sha256(body + second_key.encode()).hexdigest()


def sign_payload(body: bytes, second_key: str) -> str:
    """
    Create full PayU signature header value.

    Args:
        body: Raw HTTP body bytes
        second_key: PayU second_key from config

    Returns:
        Full header value: "signature=<hex>;algorithm=SHA-256;sender=checkout"
    """
    sig = compute_signature(body, second_key)
    return f"signature={sig};algorithm=SHA-256;sender=checkout"
