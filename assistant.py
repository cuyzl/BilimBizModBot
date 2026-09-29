import asyncio
import re

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import DRIVE_FOLDER_ID
from drive_kb import load_folder
from knowledge_search import (
    split_into_chunks,
    get_source_tier,
    search_knowledge_base,
)


GRADE, TOPIC, TOPIC_MENU, QUESTION = range(4)


# --------------------------------------------------
# КЭШ
# --------------------------------------------------

documents_cache = None
chunks_cache = None


# --------------------------------------------------
# ТЕМЫ
# --------------------------------------------------

TOPICS = {
    "sat": {
        "name": "SAT",
        "path": "Экзамены/SAT",
    },
    "ielts": {
        "name": "IELTS",
        "path": "Экзамены/IELTS",
    },
    "ap": {
        "name": "AP",
        "path": "Экзамены/AP",
    },
    "scholarships": {
        "name": "Стипендии и гранты",
        "path": "Стипендии & Гранты",
    },
    "documents": {
        "name": "Документы",
        "path": "Необходимые & Дополнительные Документы",
    },
    "essay": {
        "name": "Эссе",
        "path": "Эссе",
    },
}


# --------------------------------------------------
# КНОПКИ
# --------------------------------------------------

GRADE_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "7",
                callback_data="grade:7",
            ),
            InlineKeyboardButton(
                "8",
                callback_data="grade:8",
            ),
            InlineKeyboardButton(
                "9",
                callback_data="grade:9",
            ),
        ],
        [
            InlineKeyboardButton(
                "10",
                callback_data="grade:10",
            ),
            InlineKeyboardButton(
                "11",
                callback_data="grade:11",
            ),
            InlineKeyboardButton(
                "12",
                callback_data="grade:12",
            ),
        ],
        [
            InlineKeyboardButton(
                "Не учусь в школе",
                callback_data="grade:other",
            ),
        ],
    ]
)


TOPIC_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(
                "📝 SAT",
                callback_data="topic:sat",
            ),
            InlineKeyboardButton(
                "🌍 IELTS",
                callback_data="topic:ielts",
            ),
        ],
        [
            InlineKeyboardButton(
                "📚 AP",
                callback_data="topic:ap",
            ),
            InlineKeyboardButton(
                "💰 Стипендии",
                callback_data="topic:scholarships",
            ),
        ],
        [
            InlineKeyboardButton(
                "📄 Документы",
                callback_data="topic:documents",
            ),
            InlineKeyboardButton(
                "✍️ Эссе",
                callback_data="topic:essay",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔎 У меня другой вопрос",
                callback_data="topic:other",
            ),
        ],
    ]
)


# --------------------------------------------------
# ЗАГРУЗКА GOOGLE DRIVE
# --------------------------------------------------

def load_assistant_data():
    global documents_cache
    global chunks_cache

    if documents_cache is not None:
        return

    print(
        "📚 Загружаю материалы BilimBiz..."
    )

    documents = load_folder(
        DRIVE_FOLDER_ID
    )

    # Убираем полностью пустые документы
    documents = [
        document
        for document in documents
        if document["text"].strip()
    ]

    # Даём каждому документу внутренний ID
    for index, document in enumerate(
        documents
    ):
        document["assistant_id"] = index

    documents_cache = documents

    # Строим поисковые chunks
    chunks = []

    for document in documents:

        document_chunks = split_into_chunks(
            document["text"]
        )

        for chunk in document_chunks:

            chunks.append(
                {
                    "text": chunk,
                    "name": document["name"],
                    "url": document["url"],
                    "folder_path": document["folder_path"],
                    "tier": get_source_tier(
                        document["name"],
                        document["folder_path"],
                    ),
                    "assistant_id": document[
                        "assistant_id"
                    ],
                }
            )

    chunks_cache = chunks

    print(
        f"✅ Загружено документов: "
        f"{len(documents_cache)}"
    )

    print(
        f"✅ Поисковых фрагментов: "
        f"{len(chunks_cache)}"
    )


async def ensure_data_loaded():
    if documents_cache is None:
        await asyncio.to_thread(
            load_assistant_data
        )


# --------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# --------------------------------------------------

def short_button_name(name, limit=45):
    name = name.strip()

    if len(name) <= limit:
        return name

    return name[:limit - 3] + "..."


def get_document_by_id(document_id):
    if documents_cache is None:
        return None

    for document in documents_cache:

        if (
            document["assistant_id"]
            == document_id
        ):
            return document

    return None


def get_topic_documents(topic):
    if documents_cache is None:
        return []

    topic_info = TOPICS.get(topic)

    if not topic_info:
        return []

    topic_path = topic_info["path"]

    results = []

    for document in documents_cache:

        path = document[
            "folder_path"
        ]

        if (
            path == topic_path
            or path.startswith(
                topic_path + "/"
            )
        ):
            results.append(document)

    return results


def get_document_category(document):
    name = document[
        "name"
    ].lower()

    path = document[
        "folder_path"
    ].lower()

    if (
        "knowledge base" in name
        or "base knowledge" in name
        or "база знаний" in name
        or "основной документ" in name
    ):
        return "knowledge"

    if "гайды" in path:
        return "guides"

    if "чек-листы" in path:
        return "checklists"

    if "шаблоны" in path:
        return "templates"

    if (
        "телеграм" in path
        or "заметки" in path
    ):
        return "other"

    return "other"


def get_category_documents(
    topic,
    category,
):
    documents = get_topic_documents(
        topic
    )

    return [
        document
        for document in documents
        if get_document_category(
            document
        ) == category
    ]


def normalize_question(text):
    """
    Простая нормализация частых вариантов
    и опечаток.
    """

    text = text.lower().strip()

    replacements = {
        "сэт": "sat",
        "сат": "sat",
        "айлтс": "ielts",
        "илтс": "ielts",
        "иелтс": "ielts",
        "commonapp": "common app",
        "коммон апп": "common app",
        "коммон апп": "common app",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    # Убираем лишние пробелы
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


# --------------------------------------------------
# МЕНЮ ТЕМЫ
# --------------------------------------------------

def build_topic_menu(topic):
    documents = get_topic_documents(
        topic
    )

    rows = []

    # Knowledge Base показываем напрямую
    knowledge_docs = [
        document
        for document in documents
        if get_document_category(
            document
        ) == "knowledge"
    ]

    for document in knowledge_docs:

        rows.append(
            [
                InlineKeyboardButton(
                    "📘 "
                    + short_button_name(
                        document["name"]
                    ),
                    callback_data=(
                        f"doc:"
                        f"{document['assistant_id']}"
                    ),
                )
            ]
        )

    guides = get_category_documents(
        topic,
        "guides",
    )

    if guides:
        rows.append(
            [
                InlineKeyboardButton(
                    f"📚 Гайды ({len(guides)})",
                    callback_data=(
                        "category:guides"
                    ),
                )
            ]
        )

    checklists = get_category_documents(
        topic,
        "checklists",
    )

    if checklists:
        rows.append(
            [
                InlineKeyboardButton(
                    f"✅ Чек-листы "
                    f"({len(checklists)})",
                    callback_data=(
                        "category:checklists"
                    ),
                )
            ]
        )

    templates = get_category_documents(
        topic,
        "templates",
    )

    if templates:
        rows.append(
            [
                InlineKeyboardButton(
                    f"🧩 Шаблоны и сравнения "
                    f"({len(templates)})",
                    callback_data=(
                        "category:templates"
                    ),
                )
            ]
        )

    other = get_category_documents(
        topic,
        "other",
    )

    if other:
        rows.append(
            [
                InlineKeyboardButton(
                    f"📎 Другие материалы "
                    f"({len(other)})",
                    callback_data=(
                        "category:other"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "🔎 У меня есть вопрос",
                callback_data="ask_question",
            )
        ]
    )

    rows.append(
        [
            InlineKeyboardButton(
                "⬅️ Назад к темам",
                callback_data="back_topics",
            )
        ]
    )

    return InlineKeyboardMarkup(
        rows
    )


def build_category_keyboard(
    topic,
    category,
):
    documents = get_category_documents(
        topic,
        category,
    )

    rows = []

    for document in documents:

        rows.append(
            [
                InlineKeyboardButton(
                    short_button_name(
                        document["name"]
                    ),
                    callback_data=(
                        f"doc:"
                        f"{document['assistant_id']}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=(
                    "back_topic_menu"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        rows
    )


# --------------------------------------------------
# /START
# --------------------------------------------------

async def start_assistant(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    await update.message.reply_text(
        "👋 Привет! Я BilimBiz Assistant.\n\n"
        "Я помогу найти нужные материалы "
        "в базе BilimBiz.\n\n"
        "Для начала: в каком вы классе?",
        reply_markup=GRADE_KEYBOARD,
    )

    return GRADE


# --------------------------------------------------
# ВЫБОР КЛАССА
# --------------------------------------------------

async def select_grade(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    grade = query.data.split(
        ":",
        1,
    )[1]

    context.user_data[
        "grade"
    ] = grade

    if grade == "other":
        grade_text = (
            "не учусь в школе"
        )
    else:
        grade_text = (
            f"{grade} класс"
        )

    await query.edit_message_text(
        f"Записала: {grade_text}.\n\n"
        "Какая тема вас интересует?",
        reply_markup=TOPIC_KEYBOARD,
    )

    return TOPIC


# --------------------------------------------------
# ВЫБОР ТЕМЫ
# --------------------------------------------------

async def select_topic(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    topic = query.data.split(
        ":",
        1,
    )[1]

    context.user_data[
        "topic"
    ] = topic

    # Другой вопрос:
    # поиск сразу по всей базе
    if topic == "other":

        await query.edit_message_text(
            "Напишите ваш вопрос.\n\n"
            "Я попробую найти подходящие "
            "материалы в базе BilimBiz."
        )

        return QUESTION

    topic_info = TOPICS[
        topic
    ]

    await query.edit_message_text(
        "📚 Загружаю материалы BilimBiz..."
    )

    try:
        await ensure_data_loaded()

    except Exception as error:

        print(
            "❌ Ошибка загрузки Drive:",
            repr(error),
        )

        await query.edit_message_text(
            "Не получилось загрузить "
            "материалы BilimBiz."
        )

        return TOPIC

    documents = get_topic_documents(
        topic
    )

    if not documents:

        await query.edit_message_text(
            f"📚 {topic_info['name']}\n\n"
            "В этом разделе пока нет "
            "заполненных материалов.\n\n"
            "Вы можете задать вопрос, "
            "и я попробую поискать "
            "по всей базе BilimBiz.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔎 Задать вопрос",
                            callback_data=(
                                "ask_question"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "⬅️ Назад",
                            callback_data=(
                                "back_topics"
                            ),
                        )
                    ],
                ]
            ),
        )

        return TOPIC_MENU

    context.user_data[
        "current_category"
    ] = None

    await query.edit_message_text(
        f"📚 {topic_info['name']}\n\n"
        "Что вас интересует?",
        reply_markup=build_topic_menu(
            topic
        ),
    )

    return TOPIC_MENU


# --------------------------------------------------
# КАТЕГОРИИ
# --------------------------------------------------

CATEGORY_NAMES = {
    "guides": "📚 Гайды",
    "checklists": "✅ Чек-листы",
    "templates": "🧩 Шаблоны и сравнения",
    "other": "📎 Другие материалы",
}


async def show_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    category = query.data.split(
        ":",
        1,
    )[1]

    topic = context.user_data.get(
        "topic"
    )

    context.user_data[
        "current_category"
    ] = category

    title = CATEGORY_NAMES.get(
        category,
        "Материалы",
    )

    await query.edit_message_text(
        f"{title}\n\n"
        "Выберите материал:",
        reply_markup=build_category_keyboard(
            topic,
            category,
        ),
    )

    return TOPIC_MENU


# --------------------------------------------------
# ОТКРЫТИЕ ДОКУМЕНТА
# --------------------------------------------------

async def open_document(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    document_id = int(
        query.data.split(
            ":",
            1,
        )[1]
    )

    document = get_document_by_id(
        document_id
    )

    if not document:

        await query.edit_message_text(
            "Не получилось найти этот материал."
        )

        return TOPIC_MENU

    name = document["name"]
    path = document[
        "folder_path"
    ]
    url = document.get(
        "url"
    )

    buttons = []

    if url:
        buttons.append(
            [
                InlineKeyboardButton(
                    "📖 Открыть материал",
                    url=url,
                )
            ]
        )

    current_category = (
        context.user_data.get(
            "current_category"
        )
    )

    if current_category:

        buttons.append(
            [
                InlineKeyboardButton(
                    "⬅️ Назад к списку",
                    callback_data=(
                        f"category:"
                        f"{current_category}"
                    ),
                )
            ]
        )

    else:

        buttons.append(
            [
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data=(
                        "back_topic_menu"
                    ),
                )
            ]
        )

    await query.edit_message_text(
        f"📄 {name}\n\n"
        f"Раздел:\n{path}\n\n"
        "Нажмите кнопку ниже, "
        "чтобы открыть полный материал.",
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )

    return TOPIC_MENU


# --------------------------------------------------
# ВОЗВРАТЫ
# --------------------------------------------------

async def back_to_topic_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    topic = context.user_data.get(
        "topic"
    )

    context.user_data[
        "current_category"
    ] = None

    topic_info = TOPICS.get(
        topic
    )

    if not topic_info:

        await query.edit_message_text(
            "Выберите тему:",
            reply_markup=TOPIC_KEYBOARD,
        )

        return TOPIC

    await query.edit_message_text(
        f"📚 {topic_info['name']}\n\n"
        "Что вас интересует?",
        reply_markup=build_topic_menu(
            topic
        ),
    )

    return TOPIC_MENU


async def back_to_topics(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    context.user_data.pop(
        "topic",
        None,
    )

    context.user_data.pop(
        "current_category",
        None,
    )

    await query.edit_message_text(
        "Какая тема вас интересует?",
        reply_markup=TOPIC_KEYBOARD,
    )

    return TOPIC


# --------------------------------------------------
# СВОБОДНЫЙ ВОПРОС
# --------------------------------------------------

async def ask_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔎 Напишите вопрос своими словами.\n\n"
        "Например:\n"
        "• когда лучше сдавать SAT?\n"
        "• как отправить результаты?\n"
        "• где найти бесплатные ресурсы?\n\n"
        "Я не буду придумывать ответ — "
        "я покажу подходящие материалы BilimBiz."
    )

    return QUESTION


async def handle_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    question = update.message.text.strip()

    if not question:
        return QUESTION

    await update.message.reply_text(
        "🔎 Ищу подходящие материалы..."
    )

    try:
        await ensure_data_loaded()

    except Exception as error:

        print(
            "❌ Ошибка Assistant:",
            repr(error),
        )

        await update.message.reply_text(
            "Не получилось загрузить "
            "базу BilimBiz."
        )

        return QUESTION

    normalized = normalize_question(
        question
    )

    topic = context.user_data.get(
        "topic"
    )

    # Если человек уже выбрал SAT,
    # вопрос "когда лучше сдавать?"
    # будет искаться как SAT-вопрос.
    if (
        topic
        and topic != "other"
        and topic in TOPICS
    ):

        topic_name = TOPICS[
            topic
        ]["name"]

        search_question = (
            f"{topic_name}. "
            f"{normalized}"
        )

    else:

        search_question = normalized

    results = search_knowledge_base(
        search_question,
        chunks_cache,
        top_k=3,
    )

    if not results:

        await update.message.reply_text(
            "Я не нашёл достаточно подходящих "
            "материалов в базе BilimBiz.\n\n"
            "Попробуйте переформулировать вопрос.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ К темам",
                            callback_data=(
                                "back_topics"
                            ),
                        )
                    ]
                ]
            ),
        )

        return QUESTION

    lines = [
        "📚 Похоже, вам подойдут "
        "эти материалы:\n"
    ]

    buttons = []

    seen = set()

    for result in results:

        name = result[
            "name"
        ]

        if name in seen:
            continue

        seen.add(name)

        lines.append(
            f"• {name}"
        )

        url = result.get(
            "url"
        )

        if url:
            buttons.append(
                [
                    InlineKeyboardButton(
                        "📖 "
                        + short_button_name(
                            name
                        ),
                        url=url,
                    )
                ]
            )

    buttons.append(
        [
            InlineKeyboardButton(
                "🔎 Задать другой вопрос",
                callback_data=(
                    "ask_question"
                ),
            )
        ]
    )

    if (
        topic
        and topic != "other"
    ):

        buttons.append(
            [
                InlineKeyboardButton(
                    "⬅️ Назад к разделу",
                    callback_data=(
                        "back_topic_menu"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "🏠 Все темы",
                callback_data=(
                    "back_topics"
                ),
            )
        ]
    )

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
        disable_web_page_preview=True,
    )

    return QUESTION


# --------------------------------------------------
# CANCEL
# --------------------------------------------------

async def cancel_assistant(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    await update.message.reply_text(
        "Диалог завершён.\n"
        "Чтобы начать снова, отправьте /start."
    )

    return ConversationHandler.END


# --------------------------------------------------
# HANDLER
# --------------------------------------------------

async def handle_stale_assistant_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer(
        "Эта кнопка уже не активна. Отправьте /start.",
        show_alert=False,
    )

def get_assistant_handler():

    return ConversationHandler(
        entry_points=[
            CommandHandler(
                "start",
                start_assistant,
                filters=filters.ChatType.PRIVATE,
            ),
        ],

        states={

            GRADE: [
                CallbackQueryHandler(
                    select_grade,
                    pattern=r"^grade:",
                ),
            ],

            TOPIC: [
                CallbackQueryHandler(
                    select_topic,
                    pattern=r"^topic:",
                ),
            ],

            TOPIC_MENU: [
                CallbackQueryHandler(
                    show_category,
                    pattern=r"^category:",
                ),

                CallbackQueryHandler(
                    open_document,
                    pattern=r"^doc:",
                ),

                CallbackQueryHandler(
                    ask_question,
                    pattern=r"^ask_question$",
                ),

                CallbackQueryHandler(
                    back_to_topic_menu,
                    pattern=r"^back_topic_menu$",
                ),

                CallbackQueryHandler(
                    back_to_topics,
                    pattern=r"^back_topics$",
                ),
            ],

            QUESTION: [
                MessageHandler(
                    filters.ChatType.PRIVATE
                    & filters.TEXT
                    & ~filters.COMMAND,
                    handle_question,
                ),

                CallbackQueryHandler(
                    ask_question,
                    pattern=r"^ask_question$",
                ),

                CallbackQueryHandler(
                    back_to_topic_menu,
                    pattern=r"^back_topic_menu$",
                ),

                CallbackQueryHandler(
                    back_to_topics,
                    pattern=r"^back_topics$",
                ),
            ],
        },

        fallbacks=[
            CommandHandler(
                "start",
                start_assistant,
                filters=filters.ChatType.PRIVATE,
            ),

            CommandHandler(
                "cancel",
                cancel_assistant,
                filters=filters.ChatType.PRIVATE,
            ),
        ],

        allow_reentry=True,
    )