"""In-memory code->URL store and short-code generation.

This is a real MVP implementation, not a stub: mappings live for the life of
the process. Durable persistence across restarts is an explicitly deferred
follow-up and is intentionally not implemented here.
"""

from __future__ import annotations

import secrets
import string

# URL-safe alphabet: letters + digits only (no +, /, = padding, no ambiguity
# with URL reserved characters), so a code can sit directly in a path segment.
_ALPHABET = string.ascii_letters + string.digits
_CODE_LENGTH = 6


def generate_code(length: int = _CODE_LENGTH) -> str:
    """Return a random URL-safe short code of ``length`` characters."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


class URLStore:
    """Process-local mapping of short code -> original URL."""

    def __init__(self) -> None:
        self._by_code: dict[str, str] = {}

    def add(self, url: str) -> str:
        """Store ``url`` under a freshly generated unique code and return it."""
        code = generate_code()
        # Regenerate on the (astronomically rare) collision so we never clobber
        # an existing mapping.
        while code in self._by_code:
            code = generate_code()
        self._by_code[code] = url
        return code

    def get(self, code: str) -> str | None:
        """Return the original URL for ``code``, or ``None`` if unknown."""
        return self._by_code.get(code)

    def count(self) -> int:
        """Return the number of stored mappings."""
        return len(self._by_code)
