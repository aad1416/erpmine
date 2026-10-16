"""Conservative, deterministic token estimates for admission control.

Provider tokenizers may need network-fetched vocabularies. Upload validation must
remain available offline, so product limits use a conservative local estimate instead.
Actual request usage is still reported by the model provider.
"""

from __future__ import annotations

import math


def count_tokens(text: str) -> int:
    ascii_characters = sum(1 for character in text if ord(character) < 128)
    non_ascii_characters = len(text) - ascii_characters
    # Three ASCII characters per token intentionally over-counts typical English.
    # Count every non-ASCII code point as a token to stay conservative for languages
    # whose scripts tokenize more densely.
    return math.ceil(ascii_characters / 3) + non_ascii_characters
