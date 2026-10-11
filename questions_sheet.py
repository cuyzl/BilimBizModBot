import json
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import (
    GOOGLE_CREDENTIALS_JSON,
    QUESTIONS_SHEET_ID,
)


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets"
]

CREDENTIALS_FILE = "google_credentials.json"

SHEET_NAME = "Questions"


def get_sheets_service():
    if GOOGLE_CREDENTIALS_JSON:
        credentials_info = json.loads(
            GOOGLE_CREDENTIALS_JSON
        )

        credentials = (
            service_account
            .Credentials
            .from_service_account_info(
                credentials_info,
                scopes=SCOPES,
            )
        )

    else:
        credentials = (
            service_account
            .Credentials
            .from_service_account_file(
                CREDENTIALS_FILE,
                scopes=SCOPES,
            )
        )

    return build(
        "sheets",
        "v4",
        credentials=credentials,
    )


def find_header_row(service):
    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=QUESTIONS_SHEET_ID,
            range=f"{SHEET_NAME}!B:I",
        )
        .execute()
    )

    rows = result.get(
        "values",
        []
    )

    for index, row in enumerate(
        rows,
        start=1,
    ):
        if (
            len(row) >= 6
            and row[0].strip().lower() == "date"
            and row[1].strip().lower()
            == "telegram user id"
            and row[5].strip().lower()
            == "question"
        ):
            return index

    raise RuntimeError(
        "Не удалось найти строку "
        "заголовков в Google Sheet."
    )


def save_question(
    telegram_user_id,
    username,
    grade,
    topic,
    question,
):
    service = get_sheets_service()

    header_row = find_header_row(
        service
    )

    result = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=QUESTIONS_SHEET_ID,
            range=(
                f"{SHEET_NAME}!"
                f"A{header_row + 1}:I"
            ),
        )
        .execute()
    )

    existing_rows = result.get(
        "values",
        []
    )

    next_row = (
        header_row
        + len(existing_rows)
        + 1
    )

    date = datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )

    username_text = (
        f"@{username}"
        if username
        else ""
    )

    values = [[
        date,
        str(telegram_user_id),
        username_text,
        grade,
        topic,
        question,
        "New",
        "",
    ]]

    (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=QUESTIONS_SHEET_ID,
            range=(
                f"{SHEET_NAME}!"
                f"B{next_row}:I{next_row}"
            ),
            valueInputOption="USER_ENTERED",
            body={
                "values": values
            },
        )
        .execute()
    )

    return next_row