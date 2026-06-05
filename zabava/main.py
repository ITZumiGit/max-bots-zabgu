"""
Забава — Бот для сбора новостей (Max messenger)
/news <текст> — отправить новость в группу
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


# === API ХЕЛПЕРЫ ===

async def api_get(endpoint, session, params=None):
    async with session.get(f"{API_BASE}{endpoint}", params=params) as resp:
        return await resp.json()


async def send_message(text="", chat_id=None, user_id=None, attachments=None, session=None):
    """
    Отправка сообщения.
    user_id — для личных диалогов (приоритет).
    chat_id — для групп.
    """
    params = {}
    if user_id is not None:
        params["user_id"] = user_id
    elif chat_id is not None:
        params["chat_id"] = chat_id

    body = {"text": text, "format": "markdown"}
    if attachments:
        body["attachments"] = attachments

    sess = session or aiohttp.ClientSession()
    try:
        async with sess.post(f"{API_BASE}/messages", params=params, json=body) as resp:
            result = await resp.json()
            print(f"📤 SEND user_id={user_id} chat_id={chat_id}: {resp.status} → {result}")
            return result
    finally:
        if session is None:
            await sess.close()


def build_inline_keyboard(buttons):
    rows = []
    for btn in buttons:
        rows.append([{
            "type": "callback",
            "text": btn["text"],
            "payload": btn["callback"]
        }])
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


# === ПАРСИНГ ===

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


# === ОБРАБОТЧИКИ ===

async def handle_start(user_id, session):
    kb = build_inline_keyboard([{"text": "📝 Отправить новость", "callback": "send_news"}])
    await send_message(
        user_id=user_id,
        text="👋 **Бот для сбора новостей**\n\n"
             "📝 Отправьте новость:\n"
             "`/news Ваш текст`",
        attachments=kb, session=session
    )


async def handle_news(update, session):
    text = get_text(update)
    sender = get_sender(update)
    user_id = sender['user_id']
    sender_name = sender['name']

    print(f"📩 Новость от {sender_name}: {text}")

    if text.startswith('/news '):
        news_text = text[6:].strip()
    elif text.startswith('/news'):
        news_text = text[5:].strip()
    else:
        news_text = text.strip()

    if len(news_text) < 3:
        await send_message(user_id=user_id, text="❌ Текст слишком короткий.", session=session)
        return

    message = (
        f"📨 **Новая новость!**\n\n"
        f"👤 От: {sender_name}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{news_text}"
    )

    try:
        result = await send_message(chat_id=GROUP_ID, text=message, session=session)
        print(f"   ✅ Отправлено в группу! Результат: {result}")
        await send_message(user_id=user_id, text="✅ Новость опубликована в чате!", session=session)
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        await send_message(user_id=user_id, text=f"❌ Ошибка отправки: {e}", session=session)


async def handle_callback(update, session):
    cb = update.get("callback", {})
    payload = cb.get("payload", "")
    callback_id = cb.get("callback_id", "")
    user_id = cb.get("user", {}).get("user_id")

    print(f"🔔 CALLBACK: payload={payload} user_id={user_id}")

    if not user_id:
        return

    if payload == "send_news":
        await send_message(
            user_id=user_id,
            text="📝 Напишите новость:\n"
                 "Используйте `/news` перед текстом\n"
                 "Например: `/news Завтра состоится мероприятие`",
            session=session
        )
    elif payload == "menu":
        await handle_start(user_id, session)

    # Подтверждаем callback
    if callback_id:
        headers = {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}
        try:
            async with session.post(f"{API_BASE}/answers?callback_id={callback_id}", json={}) as resp:
                await resp.json()
        except:
            pass


# === LONG POLLING ===

async def run_bot():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан! Укажите в .env")
        return

    headers = {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}

    async with aiohttp.ClientSession(headers=headers) as session:
        me = await api_get("/me", session)
        print(f"🤖 Бот: {me.get('name', '?')} @{me.get('username', '?')}")

        if "user_id" not in me:
            print(f"❌ Ошибка авторизации: {me}")
            return

        print(f"👥 GROUP_ID: {GROUP_ID}")
        print("⏳ Ожидание сообщений...\n")

        marker = None

        while True:
            try:
                params = {"limit": 100}
                if marker:
                    params["marker"] = marker

                result = await api_get("/updates", session, params)

                if not result:
                    await asyncio.sleep(1)
                    continue

                updates = result.get("updates", [])
                new_marker = result.get("marker", marker)

                if updates:
                    print(f"📥 Получено обновлений: {len(updates)}")

                for update in updates:
                    update_type = update.get("update_type", "")

                    try:
                        # bot_started
                        if update_type == "bot_started":
                            user_id = update.get("user", {}).get("user_id")
                            if user_id:
                                await handle_start(user_id, session)

                        # message_created
                        elif update_type == "message_created":
                            text = get_text(update).strip()
                            sender = get_sender(update)
                            user_id = sender["user_id"]

                            if not text:
                                continue

                            text_lower = text.lower()

                            if text_lower == "/start":
                                await handle_start(user_id, session)
                            elif text_lower.startswith("/news"):
                                await handle_news(update, session)

                        # message_callback
                        elif update_type == "message_callback":
                            await handle_callback(update, session)

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


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\nБот остановлен")
