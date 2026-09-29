import os


BOT_TOKEN = os.getenv("BOT_TOKEN")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv(
    "GOOGLE_CREDENTIALS_JSON"
)


# Локальный запуск на ноутбуке
if not BOT_TOKEN or not DRIVE_FOLDER_ID:
    try:
        from local_config import (
            BOT_TOKEN as LOCAL_BOT_TOKEN,
            DRIVE_FOLDER_ID as LOCAL_DRIVE_FOLDER_ID,
        )

        BOT_TOKEN = (
            BOT_TOKEN
            or LOCAL_BOT_TOKEN
        )

        DRIVE_FOLDER_ID = (
            DRIVE_FOLDER_ID
            or LOCAL_DRIVE_FOLDER_ID
        )

    except ImportError:
        pass


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не найден."
    )


if not DRIVE_FOLDER_ID:
    raise RuntimeError(
        "DRIVE_FOLDER_ID не найден."
    )