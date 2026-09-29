import json
import os
import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader

from config import (
    DRIVE_FOLDER_ID,
    GOOGLE_CREDENTIALS_JSON,
)


CREDENTIALS_FILE = "google_credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly"
]


if GOOGLE_CREDENTIALS_JSON:
    credentials_info = json.loads(
        GOOGLE_CREDENTIALS_JSON
    )

    credentials = (
        service_account.Credentials
        .from_service_account_info(
            credentials_info,
            scopes=SCOPES,
        )
    )

else:
    credentials = (
        service_account.Credentials
        .from_service_account_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
        )
    )

drive_service = build(
    "drive",
    "v3",
    credentials=credentials,
)


def list_files_in_folder(folder_id):
    files = []
    page_token = None

    while True:
        result = drive_service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields=(
                "nextPageToken, "
                "files(id, name, mimeType, webViewLink)"
            ),
            pageToken=page_token,
        ).execute()

        files.extend(result.get("files", []))

        page_token = result.get("nextPageToken")

        if not page_token:
            break

    return files


def read_google_doc(file_id):
    content = drive_service.files().export(
        fileId=file_id,
        mimeType="text/plain",
    ).execute()

    return (
        content
        .decode("utf-8")
        .lstrip("\ufeff")
        .strip()
    )


def read_pdf(file_id):
    request = drive_service.files().get_media(
        fileId=file_id
    )

    buffer = io.BytesIO()

    downloader = MediaIoBaseDownload(
        buffer,
        request,
    )

    done = False

    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)

    reader = PdfReader(buffer)

    pages = []

    for page in reader.pages:
        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n".join(pages).strip()


def load_folder(folder_id, folder_path=""):
    documents = []

    files = list_files_in_folder(folder_id)

    for file in files:
        name = file["name"]
        file_id = file["id"]
        mime_type = file["mimeType"]

        # Если это подпапка
        if mime_type == "application/vnd.google-apps.folder":

            if folder_path:
                new_path = f"{folder_path}/{name}"
            else:
                new_path = name

            print(f"📁 Папка: {new_path}")

            documents.extend(
                load_folder(
                    file_id,
                    new_path,
                )
            )

            continue

        try:
            # Google Docs
            if mime_type == "application/vnd.google-apps.document":
                text = read_google_doc(file_id)

            # PDF
            elif mime_type == "application/pdf":
                text = read_pdf(file_id)

            else:
                print(f"⏭️ Пропущен файл: {name}")
                continue

            documents.append(
                {
                    "id": file_id,
                    "name": name,
                    "url": file.get("webViewLink"),
                    "text": text,
                    "folder_path": folder_path,
                }
            )

            if folder_path:
                print(
                    f"✅ Загружен: "
                    f"{folder_path}/{name}"
                )
            else:
                print(
                    f"✅ Загружен: {name}"
                )

        except Exception as e:
            print(
                f"❌ Ошибка при чтении {name}:",
                repr(e),
            )

    return documents


if __name__ == "__main__":
    print("Подключаюсь к Google Drive...\n")

    documents = load_folder(
        DRIVE_FOLDER_ID
    )

    print("\n-----------------------")
    print(
        f"Найдено документов: "
        f"{len(documents)}"
    )

    for document in documents:

        path = document["folder_path"]

        if path:
            location = (
                f"{path}/{document['name']}"
            )
        else:
            location = document["name"]

        print(
            f"• {location} "
            f"({len(document['text'])} символов)"
        )