import os
from better_profanity import profanity


RU_BAD = set()
if os.path.exists("ru_bad_words.txt"):
    with open("ru_bad_words.txt", "r", encoding="utf-8") as f:
        RU_BAD = {
            line.strip().lower()
            for line in f
            if line.strip()
        }


KZ_BAD = set()
if os.path.exists("kz_bad_words.txt"):
    with open("kz_bad_words.txt", "r", encoding="utf-8") as f:
        KZ_BAD = {
            line.strip().lower()
            for line in f
            if line.strip()
        }


ALL_BAD = RU_BAD | KZ_BAD


def contains_bad_words(text: str) -> bool:
    if not text:
        return False

    text_lower = text.lower()

    for word in ALL_BAD:
        if word in text_lower:
            return True

    if profanity.contains_profanity(text):
        return True

    return False