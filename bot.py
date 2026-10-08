import threading
from datetime import datetime, timedelta, timezone

from assistant import (
    get_assistant_handler,
    load_assistant_data,
    handle_stale_assistant_button,
    auto_refresh_kb
)

from telegram import Update, ChatPermissions

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

from bad_words import contains_bad_words
from config import BOT_TOKEN
from rules_text import RULES_TEXT, WELCOME_TEXT, BOT_ADDED_TEXT
from link_filter import contains_blocked_link


violations = {}


# ---------------------------------------
# Проверяем, является ли человек админом
# ---------------------------------------

async def is_admin(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int
):
    try:
        member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=user_id
        )

        return member.status in (
            "administrator",
            "creator"
        )

    except Exception as e:
        print("Не удалось проверить права админа:", repr(e))
        return False


# ---------------------------------------
# Welcome
# ---------------------------------------

async def welcome_new_members(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat or not message.new_chat_members:
        return

    # Если добавили самого бота
    bot_was_added = any(
        member.id == context.bot.id
        for member in message.new_chat_members
    )

    if bot_was_added:
        await context.bot.send_message(
            chat_id=chat.id,
            text=BOT_ADDED_TEXT
        )

    # Обычные новые участники
    new_members = [
        member
        for member in message.new_chat_members
        if member.id != context.bot.id
    ]

    if not new_members:
        return

    names = ", ".join(
        member.full_name
        for member in new_members
    )

    await context.bot.send_message(
        chat_id=chat.id,
        text=WELCOME_TEXT.format(name=names)
    )


# ---------------------------------------
# /rules
# ---------------------------------------

async def rules_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.effective_message.reply_text(
        RULES_TEXT
    )


# ---------------------------------------
# Модерация
# ---------------------------------------

async def moderate_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not message or not chat:
        return

    # Только группы
    if chat.type not in ("group", "supergroup"):
        return

    text = message.text or message.caption

    if not text:
        return

    print("Получено сообщение:", repr(text))

    # ---------------------------------------
    # Кто отправил сообщение?
    # ---------------------------------------

    anonymous_admin = (
        user is not None
        and user.username == "GroupAnonymousBot"
    )

    # Обычных ботов не модерируем
    if user and user.is_bot and not anonymous_admin:
        return

    user_is_admin = False

    if user and not anonymous_admin:
        user_is_admin = await is_admin(
            context,
            chat.id,
            user.id
        )

    # ---------------------------------------
    # Проверяем нарушения
    # ---------------------------------------

    has_bad_words = contains_bad_words(text)
    has_blocked_link = contains_blocked_link(text)

    # Админы могут отправлять любые ссылки
    if user_is_admin or anonymous_admin:
        has_blocked_link = False

    reasons = []

    if has_bad_words:
        reasons.append("нецензурная лексика")

    if has_blocked_link:
        reasons.append("сторонняя ссылка")

    print("Мат:", has_bad_words)
    print("Запрещённая ссылка:", has_blocked_link)

    # Нарушений нет
    if not reasons:
        return

    reason_text = ", ".join(reasons)

    # ---------------------------------------
    # Удаляем сообщение
    # ---------------------------------------

    try:
        await message.delete()
        print("Сообщение удалено ✅")

    except Exception as e:
        print("Ошибка удаления ❌:", repr(e))
        return

    # ---------------------------------------
    # Анонимный админ
    # ---------------------------------------

    if anonymous_admin:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"Сообщение удалено: {reason_text}.\n"
                "Пожалуйста, соблюдайте правила чата."
            )
        )

        return

    # ---------------------------------------
    # Если Telegram не передал пользователя
    # ---------------------------------------

    if not user:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"Сообщение удалено: {reason_text}."
            )
        )

        return

    # ---------------------------------------
    # Админ
    #
    # Мат удаляем, но warning/mute/ban
    # к администраторам не применяем.
    # ---------------------------------------

    if user_is_admin:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"Сообщение удалено: {reason_text}.\n"
                "Правила чата распространяются и на сообщения администрации."
            )
        )

        return

    # ---------------------------------------
    # Обычный пользователь
    # ---------------------------------------

    key = (chat.id, user.id)

    violations[key] = violations.get(key, 0) + 1
    count = violations[key]

    name = user.full_name

    print(
        f"Нарушение пользователя {name}: "
        f"{count}/3"
    )

    # 1 нарушение -> warning
    if count == 1:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"{name}, сообщение удалено: {reason_text}.\n"
                "Предупреждение 1/3.\n\n"
                "Правила: /rules"
            )
        )

    # 2 нарушение -> mute на 1 час
    elif count == 2:
        mute_until = (
            datetime.now(timezone.utc)
            + timedelta(hours=1)
        )

        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=ChatPermissions(
                    can_send_messages=False
                ),
                until_date=mute_until
            )

            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    f"{name}: второе нарушение "
                    f"({reason_text}).\n"
                    "Доступ к отправке сообщений ограничен на 1 час."
                )
            )

            print("Mute выдан ✅")

        except Exception as e:
            print("Ошибка mute ❌:", repr(e))

    # 3 нарушение -> ban
    elif count >= 3:
        try:
            await context.bot.ban_chat_member(
                chat_id=chat.id,
                user_id=user.id
            )

            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    f"{name} заблокирован за третье "
                    "нарушение правил."
                )
            )

            print("Пользователь заблокирован ✅")

        except Exception as e:
            print("Ошибка ban ❌:", repr(e))


# ---------------------------------------
# Запуск
# ---------------------------------------

def main():
    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Welcome
    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome_new_members
        )
    )

    app.add_handler(
        get_assistant_handler()
    )
    app.add_handler(
     CallbackQueryHandler(
         handle_stale_assistant_button,
            pattern=(
              r"^(grade:|topic:|category:|doc:|"
             r"ask_question$|back_topic_menu$|back_topics$)"
            ),
        )
    )
    app.add_handler(
        CommandHandler(
        "rules",
        rules_command,
    )
)

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & (filters.TEXT | filters.CAPTION)
            & ~filters.COMMAND,
            moderate_message
        )
    )

    print("Загружаю BilimBiz Knowledge Base...")

    load_assistant_data()

    print("Knowledge Base готова.")

    threading.Thread(
    target=auto_refresh_kb,
    daemon=True,
    ).start()

    print("Автоматическое обновление Knowledge Base включено.")
    
    print("BilimBiz Moderator запущен.")

    app.run_polling()


if __name__ == "__main__":
    main()