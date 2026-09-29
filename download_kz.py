# download_kz.py
from datasets import load_dataset

# Загружаем датасет
dataset = load_dataset("Rustem-Kaimolla/kazakh-swear-words")

# Собираем только те строки, где label == 1 (плохие слова)
bad_words = set()
for split in dataset:  # train, test и т.д.
    for row in dataset[split]:
        if row["label"] == 1:  # 1 = плохое слово, 0 = нейтральное
            bad_words.add(row["text"].strip().lower())

# Сохраняем в файл
with open("kz_bad_words.txt", "w", encoding="utf-8") as f:
    for word in sorted(bad_words):
        f.write(word + "\n")

print(f"Готово! Сохранено {len(bad_words)} казахских слов.")