# decode_ru.py
with open("gross-list.txt", "r", encoding="utf-8") as f:
    encoded_text = f.read()

# Превращаем \uXXXX в реальные буквы
decoded_text = encoded_text.encode().decode("unicode_escape")

with open("ru_bad_words.txt", "w", encoding="utf-8") as f:
    f.write(decoded_text)

print("Готово! Слова сохранены в ru_bad_words.txt")