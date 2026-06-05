"""
main.py — Фёдор, бот приёмной комиссии ЗабГУ
Прямая работа с Max Bot API через aiohttp (без maxapi).
"""
import asyncio
import logging
import json
import os

import aiohttp
from dotenv import load_dotenv

from bot_data import data, BASE

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API = "https://platform-api.max.ru"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("fedor")


# ============================================================
#  Max Bot API — прямой доступ
# ============================================================

async def api_get(path: str, session: aiohttp.ClientSession, **params):
    async with session.get(f"{API}{path}", params=params) as resp:
        text = await resp.text()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            log.error(f"GET {path} non-JSON: {text[:200]}")
            return {}


async def api_post(path: str, session: aiohttp.ClientSession, body: dict | None = None):
    async with session.post(f"{API}{path}", json=body or {}) as resp:
        text = await resp.text()
        log.debug(f"POST {path} → {resp.status}: {text[:300]}")
        try:
            result = json.loads(text)
            if isinstance(result, dict) and ("code" in result or "message" in result):
                if result.get("code") and result["code"] != 200:
                    log.warning(f"POST {path} API error: {result}")
            return result
        except json.JSONDecodeError:
            log.error(f"POST {path} non-JSON ({resp.status}): {text[:200]}")
            return {}


async def send_message(session: aiohttp.ClientSession, chat_id: int | None = None,
                       user_id: int | None = None, text: str = "",
                       attachments: list | None = None):
    """
    Отправка сообщения.
    user_id — для личных диалогов (приоритет).
    chat_id — для групп.
    Передаются как query-параметры URL, не в теле!
    """
    params = {}
    if user_id is not None:
        params["user_id"] = user_id
    elif chat_id is not None:
        params["chat_id"] = chat_id

    body: dict = {"text": text, "format": "markdown"}
    if attachments:
        body["attachments"] = attachments

    result = await api_post("/messages", session, body)
    # api_post не поддерживает params, поэтому формируем URL вручную
    return result


async def _send(session: aiohttp.ClientSession, chat_id: int | None = None,
                user_id: int | None = None, text: str = "",
                attachments: list | None = None):
    """Реальная отправка с правильными query-параметрами"""
    params = {}
    if user_id is not None:
        params["user_id"] = user_id
    elif chat_id is not None:
        params["chat_id"] = chat_id

    body: dict = {"text": text, "format": "markdown"}
    if attachments:
        body["attachments"] = attachments

    async with session.post(f"{API}/messages", params=params, json=body) as resp:
        text_resp = await resp.text()
        try:
            result = json.loads(text_resp)
            if isinstance(result, dict) and result.get("code") and result["code"] != 200:
                log.warning(f"send_message failed user_id={user_id} chat_id={chat_id}: {result}")
            return result
        except json.JSONDecodeError:
            log.error(f"send_message non-JSON: {text_resp[:200]}")
            return {}


async def answer_callback(session: aiohttp.ClientSession, callback_id: str,
                          text: str | None = None, attachments: list | None = None,
                          notification: str | None = None):
    body: dict = {}
    if text is not None:
        msg: dict = {"text": text, "format": "markdown"}
        if attachments:
            msg["attachments"] = attachments
        body["message"] = msg
    if notification:
        body["notification"] = notification
    async with session.post(f"{API}/answers?callback_id={callback_id}", json=body) as resp:
        text_resp = await resp.text()
        try:
            return json.loads(text_resp)
        except json.JSONDecodeError:
            log.error(f"answer_callback non-JSON: {text_resp[:200]}")
            return {}


# ============================================================
#  КЛАВИАТУРЫ
# ============================================================

def cb(text: str, payload: str) -> dict:
    return {"type": "callback", "text": text, "payload": payload}


def url_btn(text: str, link: str) -> dict:
    return {"type": "link", "text": text, "url": link}


def kb(*rows) -> list:
    return [{"type": "inline_keyboard", "payload": {"buttons": [list(row) for row in rows]}}]


def _build_links_kb(links: list, back_payload: str = "back_main") -> list:
    rows = []
    for link_item in links:
        rows.append([url_btn(link_item["title"], link_item["url"])])
    rows.append([cb("⬅️ Назад", back_payload)])
    return kb(*rows)


main_menu = kb(
    [cb("📊 Калькулятор ЕГЭ", "ege")],
    [cb("📚 Программы обучения", "programs")],
    [cb("🏛 Приёмная комиссия", "admission")],
    [cb("📰 Новости", "news")],
    [cb("❓ FAQ", "faq")],
)

programs_menu_kb = kb(
    [cb("🎓 Бакалавриат", "bak")],
    [cb("🎓 Магистратура", "mag")],
    [cb("🎓 Аспирантура", "asp")],
    [cb("🎓 СПО", "spo")],
    [cb("🏠 Главное меню", "back_main")],
)

back_menu_kb = kb([cb("🏠 Главное меню", "back_main")])

admission_menu_kb = kb(
    [cb("📞 Контакты", "contacts")],
    [cb("📑 Документы для поступления", "documents")],
    [cb("🗓️ Сроки подачи документов", "dates")],
    [cb("📝 Вступительные испытания", "exams")],
    [cb("📊 Статистика приёма", "stats")],
    [cb("❓ Часто задаваемые вопросы", "faq_full")],
    [cb("🏠 Главное меню", "back_main")],
)


# --- ДИНАМИЧЕСКИЕ КЛАВИАТУРЫ ---

def get_bak_kb():
    if data.BAK_LINKS:
        return _build_links_kb(data.BAK_LINKS, "programs")
    return kb(
        [url_btn("🔗 Очная форма", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%B1%D0%B0%D0%BA%D0%B0%D0%BB%D0%B0%D0%B2%D1%80%D0%B8%D0%B0%D1%82%20%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf")],
        [url_btn("🔗 Очно-заочная форма", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%B1%D0%B0%D0%BA%D0%B0%D0%BB%D0%B0%D0%B2%D1%80%D0%B8%D0%B0%D1%82%20%D0%BE%D1%87%D0%BD%D0%BE-%D0%B7%D0%B0%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf")],
        [url_btn("🔗 Заочная форма", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%B1%D0%B0%D0%BA%D0%B0%D0%BB%D0%B0%D0%B2%D1%80%D0%B8%D0%B0%D1%82%20%D0%B7%D0%B0%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf")],
        [cb("⬅️ Назад", "programs")],
    )

def get_mag_kb():
    if data.MAG_LINKS:
        return _build_links_kb(data.MAG_LINKS, "programs")
    return kb(
        [url_btn("🔗 Очная форма", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%BC%D0%B0%D0%B3%D0%B8%D1%81%D1%82%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0%20%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf")],
        [url_btn("🔗 Очно-заочная форма", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%BC%D0%B0%D0%B3%D0%B8%D1%81%D1%82%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0%20%D0%BE%D1%87%D0%BD%D0%BE-%D0%B7%D0%B0%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf")],
        [url_btn("🔗 Заочная форма", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%BC%D0%B0%D0%B3%D0%B8%D1%81%D1%82%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0%20%D0%B7%D0%B0%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf")],
        [cb("⬅️ Назад", "programs")],
    )

def get_asp_kb():
    if data.ASP_LINKS:
        return _build_links_kb(data.ASP_LINKS, "programs")
    return kb(
        [url_btn("🔗 Очная форма", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%B0%D1%81%D0%BF%D0%B8%D1%80%D0%B0%D0%BD%D1%82%D1%83%D1%80%D0%B0%20%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf")],
        [cb("⬅️ Назад", "programs")],
    )

def get_spo_kb():
    if data.SPO_LINKS:
        return _build_links_kb(data.SPO_LINKS, "programs")
    return kb(
        [url_btn("🔗 На базе 9 классов", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%A1%D0%9F%D0%9E%209.pdf")],
        [url_btn("🔗 На базе 11 классов", f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%A1%D0%9F%D0%9E%2011.pdf")],
        [cb("⬅️ Назад", "programs")],
    )

def get_stats_kb():
    if data.STATS_LINKS:
        return _build_links_kb(data.STATS_LINKS, "admission")
    return back_menu_kb


# --- FAQ ---

def create_faq_keyboard(page_num=0):
    rows = []
    start_idx = page_num * 5
    end_idx = min(start_idx + 5, len(data.FAQ_QUESTIONS))

    for i in range(start_idx, end_idx, 2):
        row = []
        if i < end_idx:
            row.append(cb(str(i + 1), f"faq_{i + 1}"))
        if i + 1 < end_idx:
            row.append(cb(str(i + 2), f"faq_{i + 2}"))
        rows.append(row)

    nav_row = []
    total_pages = max(1, (len(data.FAQ_QUESTIONS) + 4) // 5)
    if page_num > 0:
        nav_row.append(cb("⬅️ Назад", f"faq_page_{page_num - 1}"))
    if page_num < total_pages - 1:
        nav_row.append(cb("Вперёд ➡️", f"faq_page_{page_num + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([cb("⬅️ В главное меню", "back_main")])
    return kb(*rows)


def faq_text_for_page(page_num):
    start_idx = page_num * 5
    end_idx = min(start_idx + 5, len(data.FAQ_QUESTIONS))
    total_pages = max(1, (len(data.FAQ_QUESTIONS) + 4) // 5)
    text = f"{data.FAQ_TEXT} (Страница {page_num + 1} из {total_pages})\n\n"
    for i in range(start_idx, end_idx):
        text += f"{i + 1}. {data.FAQ_QUESTIONS[i]}\n\n"
    return text


# --- НОВОСТИ ---

def create_news_keyboard(page_num=0):
    rows = []
    per_page = 3
    start_idx = page_num * per_page
    end_idx = min(start_idx + per_page, len(data.NEWS))

    for i in range(start_idx, end_idx):
        news_item = data.NEWS[i]
        title = news_item["title"][:35] + ("…" if len(news_item["title"]) > 35 else "")
        rows.append([cb(f"📰 {title}", f"news_{i}")])

    nav_row = []
    total_pages = max(1, (len(data.NEWS) + per_page - 1) // per_page)
    if page_num > 0:
        nav_row.append(cb("⬅️ Назад", f"news_page_{page_num - 1}"))
    if page_num < total_pages - 1:
        nav_row.append(cb("Вперёд ➡️", f"news_page_{page_num + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([cb("🏠 Главное меню", "back_main")])
    return kb(*rows)


def news_text_for_page(page_num):
    per_page = 3
    start_idx = page_num * per_page
    end_idx = min(start_idx + per_page, len(data.NEWS))
    total_pages = max(1, (len(data.NEWS) + per_page - 1) // per_page)
    text = f"📰 Новости приёмной комиссии\n(Страница {page_num + 1} из {total_pages})\n\n"
    for i in range(start_idx, end_idx):
        text += f"📰 {data.NEWS[i]['title']}\n\n"
    return text


# ============================================================
#  ОБРАБОТКА CALLBACK
# ============================================================

def handle_callback(payload: str):
    if payload == "ege":
        return data.EGE_TEXT, back_menu_kb
    elif payload == "programs":
        return data.PROGRAMS_TEXT, programs_menu_kb
    elif payload == "bak":
        return data.BAK_TEXT, get_bak_kb()
    elif payload == "mag":
        return data.MAG_TEXT, get_mag_kb()
    elif payload == "asp":
        return data.ASP_TEXT, get_asp_kb()
    elif payload == "spo":
        return data.SPO_TEXT, get_spo_kb()
    elif payload == "faq":
        return faq_text_for_page(0), create_faq_keyboard(0)
    elif payload == "faq_full":
        return faq_text_for_page(0), create_faq_keyboard(0)
    elif payload.startswith("faq_page_"):
        try:
            page_num = int(payload.split("_")[2])
            return faq_text_for_page(page_num), create_faq_keyboard(page_num)
        except (ValueError, IndexError):
            return faq_text_for_page(0), create_faq_keyboard(0)
    elif payload.startswith("faq_") and len(payload) > 4 and not payload.startswith("faq_page_"):
        try:
            question_num = int(payload[4:]) - 1
            if 0 <= question_num < len(data.FAQ_ANSWERS):
                full_msg = f"{data.FAQ_QUESTIONS[question_num]}\n\n{data.FAQ_ANSWERS[question_num]}"
                answer_kb = kb(
                    [cb("📋 Вернуться к вопросам", "faq")],
                    [cb("🏠 Главное меню", "back_main")],
                )
                return full_msg, answer_kb
        except ValueError:
            pass
        return data.MAIN_TEXT, main_menu
    elif payload == "news":
        if data.NEWS:
            return news_text_for_page(0), create_news_keyboard(0)
        return "📰 Новости временно недоступны", back_menu_kb
    elif payload.startswith("news_page_"):
        try:
            page_num = int(payload.split("_")[2])
            return news_text_for_page(page_num), create_news_keyboard(page_num)
        except (ValueError, IndexError):
            return news_text_for_page(0), create_news_keyboard(0)
    elif payload.startswith("news_"):
        try:
            news_idx = int(payload[5:])
            if 0 <= news_idx < len(data.NEWS):
                news_item = data.NEWS[news_idx]
                news_kb = kb(
                    [url_btn("🔗 Открыть на сайте", news_item["url"])],
                    [cb("📰 Все новости", "news")],
                    [cb("🏠 Главное меню", "back_main")],
                )
                return f"📰 {news_item['title']}", news_kb
        except ValueError:
            pass
        return data.MAIN_TEXT, main_menu
    elif payload == "admission":
        return data.ADMISSION_TEXT, admission_menu_kb
    elif payload == "contacts":
        return data.CONTACTS_TEXT, admission_menu_kb
    elif payload == "documents":
        return data.DOCUMENTS_TEXT, admission_menu_kb
    elif payload == "dates":
        return data.DATES_TEXT, admission_menu_kb
    elif payload == "exams":
        return data.EXAMS_TEXT, admission_menu_kb
    elif payload == "stats":
        return "📊 Статистика приёма", get_stats_kb()
    elif payload == "back_main":
        return data.MAIN_TEXT, main_menu

    return data.MAIN_TEXT, main_menu


# ============================================================
#  ОПРЕДЕЛЕНИЕ user_id ИЗ UPDATE
# ============================================================

def _get_user_id(update: dict) -> int | None:
    """Извлекает user_id из update для отправки в личный диалог"""
    # message_created / bot_started
    msg = update.get("message", {})
    sender = msg.get("sender", {})
    if sender.get("user_id"):
        return sender["user_id"]
    # bot_started — user на верхнем уровне
    user = update.get("user", {})
    if user.get("user_id"):
        return user["user_id"]
    # callback
    cb = update.get("callback", {})
    cb_user = cb.get("user", {})
    if cb_user.get("user_id"):
        return cb_user["user_id"]
    return None


def _get_chat_id(update: dict) -> int | None:
    """Извлекает chat_id группы"""
    msg = update.get("message", {})
    recipient = msg.get("recipient", {})
    chat_type = recipient.get("chat_type", "dialog")
    if chat_type != "dialog" and recipient.get("chat_id"):
        return recipient["chat_id"]
    return None


# ============================================================
#  POLLING LOOP
# ============================================================

async def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан! Укажите в .env")
        return

    print("🏛 Фёдор — Бот приёмной комиссии ЗабГУ")
    print("🔄 Загрузка данных с сайта...")
    data.load_from_site()
    print(f"📊 FAQ: {len(data.FAQ_QUESTIONS)} вопросов")
    print(f"📰 Новости: {len(data.NEWS)}")
    print(f"📄 БАК PDF: {len(data.BAK_LINKS)}, МАГ PDF: {len(data.MAG_LINKS)}")
    print(f"📄 АСП PDF: {len(data.ASP_LINKS)}, СПО PDF: {len(data.SPO_LINKS)}")
    print(f"📊 Статистика: {len(data.STATS_LINKS)} ссылок")
    print("🚀 Запуск...")

    headers = {"Authorization": BOT_TOKEN, "Content-Type": "application/json"}

    async with aiohttp.ClientSession(headers=headers) as session:
        me = await api_get("/me", session)
        if "user_id" not in me:
            print(f"❌ Ошибка авторизации: {me}")
            return
        print(f"✅ Бот подключён: @{me.get('username', '?')} ({me.get('name', me.get('first_name', '?'))})")

        marker = None

        while True:
            try:
                params = {"timeout": 30, "types": "message_created,message_callback,bot_started"}
                if marker is not None:
                    params["marker"] = marker

                result = await api_get("/updates", session, **params)

                if not result or "updates" not in result:
                    await asyncio.sleep(1)
                    continue

                new_marker = result.get("marker")
                if new_marker is not None:
                    marker = new_marker

                for update in result["updates"]:
                    update_type = update.get("update_type", "")
                    user_id = _get_user_id(update)
                    chat_id = _get_chat_id(update)

                    log.info(f"Update: type={update_type} user_id={user_id} chat_id={chat_id}")

                    # --- bot_started ---
                    if update_type == "bot_started":
                        if user_id:
                            await _send(session, user_id=user_id, text=data.MAIN_TEXT, attachments=main_menu)
                        else:
                            log.error(f"bot_started: no user_id!")

                    # --- message_created ---
                    elif update_type == "message_created":
                        msg = update.get("message", {})
                        text = msg.get("body", {}).get("text", "").strip()

                        if not user_id:
                            log.error(f"message_created: no user_id!")
                            continue

                        if text.lower() in ("/start", "start", "начать", "старт", "привет", "hello", "hi"):
                            await _send(session, user_id=user_id, text=data.MAIN_TEXT, attachments=main_menu)

                        elif text.lower() == "/refresh":
                            await _send(session, user_id=user_id, text="🔄 Обновляю данные...")
                            data.load_from_site()
                            await _send(session, user_id=user_id, text="✅ Данные обновлены!", attachments=main_menu)

                    # --- message_callback ---
                    elif update_type == "message_callback":
                        callback = update.get("callback", {})
                        payload = callback.get("payload", "")
                        callback_id = callback.get("callback_id", "")
                        log.info(f"message_callback user_id={user_id} payload={payload!r}")

                        cb_text, attachments = handle_callback(payload)

                        if callback_id:
                            await answer_callback(session, callback_id, text=cb_text, attachments=attachments)
                        elif user_id:
                            await _send(session, user_id=user_id, text=cb_text, attachments=attachments)
                        else:
                            log.error(f"message_callback: no callback_id and no user_id!")

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Ошибка в polling: {e}", exc_info=True)
                await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен")
