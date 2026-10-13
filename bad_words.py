import os
import re

from better_profanity import profanity


RU_BAD = set()
if os.path.exists("ru_bad_words.txt"):
    with open(
        "ru_bad_words.txt",
        "r",
        encoding="utf-8",
    ) as f:
        RU_BAD = {
            line.strip().lower()
            for line in f
            if line.strip()
        }


KZ_BAD = set()
if os.path.exists("kz_bad_words.txt"):
    with open(
        "kz_bad_words.txt",
        "r",
        encoding="utf-8",
    ) as f:
        KZ_BAD = {
            line.strip().lower()
            for line in f
            if line.strip()
        }


ALL_BAD = RU_BAD | KZ_BAD


def find_bad_word(text: str):
    if not text:
        return None

    text_lower = text.lower()

    for word in ALL_BAD:
        pattern = (
            rf"(?<!\w)"
            rf"{re.escape(word)}"
            rf"(?!\w)"
        )

        if re.search(
            pattern,
            text_lower,
            flags=re.UNICODE,
        ):
            return word

    if profanity.contains_profanity(text):
        return "better_profanity"

    return None


def contains_bad_words(text: str) -> bool:
    return find_bad_word(text) is not None