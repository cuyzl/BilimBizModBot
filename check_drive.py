from drive_kb import load_folder
from config import DRIVE_FOLDER_ID


docs = load_folder(DRIVE_FOLDER_ID)

print("\n\n=== КОРОТКИЕ ДОКУМЕНТЫ ===")

for doc in docs:
    if len(doc["text"].strip()) < 300:
        print("\n---", doc["name"], "---")
        print(repr(doc["text"][:300]))