"""
Q&A Бот (Max messenger) — чистый aiohttp
/q <вопрос>  — пользователь задаёт вопрос
/a <номер> <ответ> — модератор отвечает в группе
/list — список ожидающих вопросов (в группе)
"""

import asyncio
import json
import os

import aiohttp
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "0"))
API_BASE = "https://platform-api.max.ru"

questions = {}
question_counter = 0


# === API ХЕЛПЕРЫ ===

async def api_get(endpoint, session=None, params=None):
    headers = {"Authorization": BOT_TOKEN}
    sess = session or aiohttp.ClientSession()
    try:
        async with sess.get(f"{API_BASE}{endpoint}", headers=headers, params=params) as resp:
            return await resp.json()
    finally:
        if session is None:
            await sess.close()


async def send_message(text="", chat_id=None, user_id=None, attachments=None, session=None):
    """
    Отправка сообщения.
    user_id — для личных диалогов (приоритет).
    chat_id — для групп.
    Это QUERY-параметры URL, не тело!
    """
    params = {}
    if user_id is not None:
        params["user_id"] = user_id
    elif chat_id is not None:
        params["chat_id"] = chat_id

    body = {"text": text, "format": "markdown"}
    if attachments:
        body["attachments"] = attachments

    headers = {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}
    sess = session or aiohttp.ClientSession()
    try:
        async with sess.post(f"{API_BASE}/messages", headers=headers, params=params, json=body) as resp:
            result = await resp.json()
            print(f"📤 SEND user_id={user_id} chat_id={chat_id}: {resp.status} → {result}")
            return result
    finally:
        if session is None:
            await sess.close()


async def answer_callback(callback_id, text="", session=None):
    headers = {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}
    params = {"callback_id": callback_id}
    body = {"message": {"text": text, "format": "markdown"}} if text else {}
    sess = session or aiohttp.ClientSession()
    try:
        async with sess.post(f"{API_BASE}/answers", headers=headers, params=params, json=body) as resp:
            return await resp.json()
    finally:
        if session is None:
            await sess.close()


def build_inline_keyboard(buttons):
    """buttons: list of {text, callback} → attachments"""
    rows = []
    for btn in buttons:
        rows.append([{
            "type": "callback",
            "text": btn["text"],
            "payload": btn["callback"]
        }])
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


# === ПАРСИНГ ОБНОВЛЕНИЙ ===

def get_text(update):
    msg = update.get("message", {})
    body = msg.get("body", {})
    if isinstance(body, dict):
        return body.get("text", "")
    return str(body) if body else ""


def get_sender(update):
    msg = update.get("message", {})
    sender = msg.get("sender", {})
    return {"user_id": sender.get("user_id"), "name": sender.get("name", "Пользователь")}


def get_chat_id(update):
    msg = update.get("message", {})
    recipient = msg.get("recipient", {})
    return recipient.get("chat_id")


def is_callback(update):
    return update.get("callback", None) is not None


def get_callback_data(update):
    return update.get("callback", {}).get("payload", "")


def get_callback_id(update):
    return update.get("callback", {}).get("callback_id", "")


def get_callback_user_id(update):
    return update.get("callback", {}).get("user", {}).get("user_id")


# === ОБРАБОТЧИКИ ===

async def handle_start(user_id, session):
    kb = build_inline_keyboard([{"text": "💬 Задать вопрос", "callback": "ask"}])
    await send_message(user_id=user_id, text="👋 Привет! Нажмите кнопку ниже чтобы задать вопрос.",
                       attachments=kb, session=session)


async def handle_question(update, session):
    global question_counter
    text = get_text(update)
    sender = get_sender(update)
    user_id = sender['user_id']

    if text.startswith('/q '):
        question_text = text[3:].strip()
    elif text.startswith('/q'):
        question_text = text[2:].strip()
    else:
        question_text = text.strip()

    if len(question_text) < 2:
        kb = build_inline_keyboard([{"text": "🏠 В меню", "callback": "menu"}])
        await send_message(user_id=user_id,
                           text="❌ Напишите вопрос после команды.\nПример: `/q Как поступить?`",
                           attachments=kb, session=session)
        return

    question_counter += 1
    q_num = question_counter

    questions[q_num] = {
        'user_id': user_id,
        'user_name': sender['name'],
        'question': question_text
    }

    group_msg = (
        f"❓ **Вопрос #{q_num}**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 {sender['name']}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{question_text}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💬 `/a {q_num} <ваш ответ>`"
    )

    try:
        await send_message(chat_id=GROUP_ID, text=group_msg, session=session)
        print(f"✅ Вопрос #{q_num} от {sender['name']} (user_id={user_id})")
        kb = build_inline_keyboard([{"text": "🏠 В меню", "callback": "menu"}])
        await send_message(user_id=user_id, text="✅ Вопрос отправлен! Ожидайте ответа.",
                           attachments=kb, session=session)
    except Exception as e:
        print(f"❌ Ошибка отправки в группу: {e}")
        await send_message(user_id=user_id, text=f"❌ Ошибка: {e}", session=session)


async def handle_answer(update, session):
    text = get_text(update)
    chat_id = get_chat_id(update)

    if chat_id != GROUP_ID:
        await send_message(chat_id=chat_id, text="❌ Эта команда только для группы модераторов.", session=session)
        return

    if text.startswith('/a '):
        parts = text[3:].strip().split(' ', 1)
    else:
        parts = text.strip().split(' ', 1)

    if len(parts) < 2:
        await send_message(chat_id=chat_id, text="❌ Формат: `/a <номер> <ответ>`", session=session)
        return

    try:
        q_num = int(parts[0])
    except ValueError:
        await send_message(chat_id=chat_id, text="❌ Номер вопроса — число.", session=session)
        return

    answer_text = parts[1].strip()
    if not answer_text:
        await send_message(chat_id=chat_id, text="❌ Напишите ответ.", session=session)
        return

    if q_num not in questions:
        await send_message(chat_id=chat_id, text=f"❌ Вопрос #{q_num} не найден или уже отвечен.", session=session)
        return

    info = questions[q_num]
    target_user_id = info['user_id']
    user_name = info['user_name']
    question_text = info['question']

    answer_msg = (
        f"📬 **Ответ на ваш вопрос #{q_num}!**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"❓ Ваш вопрос: {question_text}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💬 **Ответ:**\n"
        f"{answer_text}"
    )

    try:
        await send_message(user_id=target_user_id, text=answer_msg, session=session)
        print(f"✅ Ответ на #{q_num} отправлен (user_id={target_user_id})")
        await send_message(chat_id=GROUP_ID, text=f"✅ Ответ на вопрос #{q_num} отправлен {user_name}", session=session)
        del questions[q_num]
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        await send_message(chat_id=GROUP_ID, text=f"❌ Не удалось отправить ответ: {e}", session=session)


async def handle_list(update, session):
    chat_id = get_chat_id(update)
    if chat_id != GROUP_ID:
        return

    if not questions:
        await send_message(chat_id=GROUP_ID, text="📋 Нет ожидающих вопросов.", session=session)
        return

    text = "📋 **Ожидающие вопросы:**\n\n"
    for num, info in sorted(questions.items()):
        q_preview = info['question'][:50] + ('...' if len(info['question']) > 50 else '')
        text += f"#{num} — {info['user_name']}: {q_preview}\n"
    text += f"\n💬 `/a <номер> <ответ>`"

    await send_message(chat_id=GROUP_ID, text=text, session=session)


async def handle_callback(update, session):
    data = get_callback_data(update)
    callback_id = get_callback_id(update)
    user_id = get_callback_user_id(update)

    print(f"🔔 CALLBACK: payload={data} user_id={user_id}")

    if not user_id:
        print("⚠️ Нет user_id в callback, пропускаю")
        return

    if data == "ask":
        kb = build_inline_keyboard([{"text": "🏠 В меню", "callback": "menu"}])
        await send_message(user_id=user_id,
                           text="💬 Напишите ваш вопрос:\n"
                                "Используйте `/q` перед вопросом\n"
                                "Например: `/q Как поступить на бюджет?`",
                           attachments=kb, session=session)
    elif data == "menu":
        kb = build_inline_keyboard([{"text": "💬 Задать вопрос", "callback": "ask"}])
        await send_message(user_id=user_id, text="👋 Главное меню:", attachments=kb, session=session)

    if callback_id:
        try:
            await answer_callback(callback_id, session=session)
        except:
            pass


# === LONG POLLING ===

async def run_bot():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан! Укажите в .env")
        return

    headers = {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}

    async with aiohttp.ClientSession(headers=headers) as session:
        me = await api_get("/me", session=session)
        print(f"🤖 Бот: {me.get('name', '?')} @{me.get('username', '?')}")

        if "user_id" not in me:
            print(f"❌ Ошибка авторизации: {me}")
            return

        print(f"📢 Группа: {GROUP_ID}")
        print("📝 Команды: /q <вопрос> | /a <номер> <ответ> | /list")
        print("⏳ Ожидание сообщений...\n")

        marker = None

        while True:
            try:
                params = {"limit": 100}
                if marker:
                    params["marker"] = marker

                result = await api_get("/updates", session=session, params=params)

                if not result:
                    await asyncio.sleep(1)
                    continue

                updates = result.get("updates", [])
                new_marker = result.get("marker", marker)

                if updates:
                    print(f"📥 Получено обновлений: {len(updates)}")

                for update in updates:
                    try:
                        await process_update(update, session)
                    except Exception as e:
                        print(f"❌ Ошибка обработки: {e}")
                        import traceback
                        traceback.print_exc()

                if new_marker:
                    marker = new_marker

                await asyncio.sleep(0.3)

            except Exception as e:
                print(f"❌ Ошибка polling: {e}")
                await asyncio.sleep(3)


async def process_update(update, session):
    if is_callback(update):
        await handle_callback(update, session)
        return

    text = get_text(update)
    sender = get_sender(update)

    if not text:
        return

    text_lower = text.lower().strip()

    if text_lower == '/start':
        await handle_start(sender['user_id'], session)
    elif text_lower.startswith('/q'):
        await handle_question(update, session)
    elif text_lower.startswith('/a'):
        await handle_answer(update, session)
    elif text_lower == '/list':
        await handle_list(update, session)


if __name__ == "__main__":
    asyncio.run(run_bot())
