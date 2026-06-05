"""
bot_data.py — Динамическая загрузка данных с сайта ЗабГУ
Все тексты, ссылки и PDF тянутся с entrant.zabgu.ru при запуске.
Если сайт недоступен — используются резервные данные.
"""
import requests
from bs4 import BeautifulSoup
import re
import logging

log = logging.getLogger(__name__)

BASE = "https://entrant.zabgu.ru"
TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ============================================================
#  Минимальные баллы ЕГЭ 2026 (из приказа ЗабГУ)
# ============================================================

EGE_MIN_SCORES = {
    "Русский язык": 40,
    "Математика (профиль)": 39,
    "Физика": 41,
    "Обществознание": 45,
    "История": 40,
    "Информатика и ИКТ": 46,
    "Иностранный язык": 40,
    "Литература": 40,
    "Биология": 40,
    "География": 40,
    "Химия": 40,
}

VI_MAX_SCORES = {
    "Русский язык": 100,
    "Математика": 100,
    "Физика": 100,
    "Обществознание": 100,
    "История": 100,
    "Информатика и ИКТ": 100,
    "Иностранный язык": 100,
    "Литература": 100,
    "Биология": 100,
    "География": 100,
    "Химия": 100,
    "Проф. испытание — Физическая культура (практика)": 100,
    "Проф. испытание — Физическая культура (теория)": 100,
    "Творческий конкурс": 100,
    "Проф. испытание — ОБЖ": 100,
}


# ============================================================
#  Утилиты
# ============================================================

def _get(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        log.warning(f"Не удалось загрузить {url}: {e}")
        return None


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


# ============================================================
#  Парсинг главной страницы — FAQ + Контакты + Новости
# ============================================================

def _parse_main_page():
    soup = _get(BASE)
    if not soup:
        return None

    result = {
        "faq_questions": [],
        "faq_answers": [],
        "contacts": "",
        "news": [],
    }

    # --- FAQ ---
    faq_blocks = soup.find_all(string=re.compile(r'Часто\s*задаваемые\s*вопросы', re.I))
    if faq_blocks:
        for fb in faq_blocks:
            container = fb.find_parent(["div", "section"])
            if not container:
                continue
            questions = container.find_all(["b", "strong"])
            for q in questions:
                q_text = _clean(q.get_text())
                if len(q_text) < 10:
                    continue
                answer_parts = []
                sibling = q.next_sibling
                while sibling:
                    if hasattr(sibling, 'name') and sibling.name in ["b", "strong"]:
                        break
                    if hasattr(sibling, 'get_text'):
                        answer_parts.append(_clean(sibling.get_text()))
                    elif isinstance(sibling, str) and sibling.strip():
                        answer_parts.append(_clean(sibling))
                    sibling = sibling.next_sibling
                answer = " ".join(answer_parts).strip()
                if q_text and answer:
                    result["faq_questions"].append(q_text)
                    result["faq_answers"].append(answer)

    # --- Контакты ---
    contacts_blocks = soup.find_all(string=re.compile(r'Контакты\s*приёмной\s*комиссии', re.I))
    if contacts_blocks:
        for cb in contacts_blocks:
            container = cb.find_parent(["div", "section"])
            if container:
                result["contacts"] = _clean(container.get_text())
                break

    # --- Новости ---
    news_items = soup.find_all("a", href=re.compile(r'open_news'))
    for item in news_items[:10]:
        title = _clean(item.get_text())
        href = item.get("href", "")
        if title and href:
            result["news"].append({"title": title, "url": href if href.startswith("http") else BASE + href})

    return result


# ============================================================
#  Парсинг страницы документов
# ============================================================

def _parse_documents_page():
    soup = _get(f"{BASE}/?page_id=193")
    if not soup:
        return None

    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.find("main")
    if not content:
        return None

    docs = {"short_list": "", "links": []}

    for a in content.find_all("a", href=True):
        text = _clean(a.get_text())
        href = a["href"]
        if text and len(text) > 3:
            full_url = href if href.startswith("http") else BASE + href
            docs["links"].append({"title": text, "url": full_url})

    tables = content.find_all("table")
    for table in tables:
        for row in table.find_all("tr"):
            for cell in row.find_all(["td", "th"]):
                text = _clean(cell.get_text())
                if len(text) > 5:
                    docs["short_list"] += text + "\n"

    if not docs["short_list"]:
        docs["short_list"] = _clean(content.get_text())[:3000]

    return docs


# ============================================================
#  Парсинг сроков приёма
# ============================================================

def _parse_dates_page():
    soup = _get(f"{BASE}/?page_id=16")
    if not soup:
        return None

    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.find("main")
    if not content:
        return None

    return _clean(content.get_text())[:3000]


# ============================================================
#  Парсинг приёмной кампании 2026
# ============================================================

def _parse_campaign_page():
    soup = _get(f"{BASE}/?page_id=4235")
    if not soup:
        return None

    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.find("main")
    if not content:
        return None

    return _clean(content.get_text())[:3000]


# ============================================================
#  Парсинг вступительных испытаний
# ============================================================

def _parse_exams_page():
    soup = _get(f"{BASE}/?page_id=120")
    if not soup:
        return None

    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.find("main")
    if not content:
        return None

    return _clean(content.get_text())[:3000]


# ============================================================
#  Парсинг статистики приёма
# ============================================================

def _parse_stats_page():
    soup = _get(f"{BASE}/?page_id=610")
    if not soup:
        return None

    links = soup.find_all("a", href=re.compile(r'\.pdf'))
    stats = []
    for link in links:
        text = _clean(link.get_text())
        href = link.get("href", "")
        if text and href:
            full_url = href if href.startswith("http") else BASE + href
            stats.append({"title": text, "url": full_url})
    return stats


# ============================================================
#  Парсинг КЦП (планы приёма) — PDF для бак/маг/асп/СПО
# ============================================================

def _parse_kcp_page():
    soup = _get(f"{BASE}/?page_id=8072")
    if not soup:
        return None

    result = {"bak": [], "mag": [], "asp": [], "spo": []}

    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.find("main")
    if not content:
        return None

    for a in content.find_all("a", href=re.compile(r'\.pdf', re.I)):
        text = _clean(a.get_text()).lower()
        href = a["href"]
        full_url = href if href.startswith("http") else BASE + href
        title = _clean(a.get_text())

        if "бакалавр" in text or "бак" in text:
            result["bak"].append({"title": title, "url": full_url})
        elif "магистр" in text or "маг" in text:
            result["mag"].append({"title": title, "url": full_url})
        elif "аспирант" in text or "асп" in text:
            result["asp"].append({"title": title, "url": full_url})
        elif "спо" in text or "колледж" in text or "средн" in text:
            result["spo"].append({"title": title, "url": full_url})

    return result


# ============================================================
#  Парсинг страницы ЕГЭ (минимальные баллы, перечень ВИ)
# ============================================================

def _parse_ege_page():
    soup = _get(f"{BASE}/?page_id=130")
    if not soup:
        return None

    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.find("main")
    if not content:
        return None

    links = []
    for a in content.find_all("a", href=True):
        text = _clean(a.get_text())
        href = a["href"]
        if text and len(text) > 3:
            full_url = href if href.startswith("http") else BASE + href
            links.append({"title": text, "url": full_url})

    text = _clean(content.get_text())[:3000]
    return {"text": text, "links": links}


# ============================================================
#  Глобальное хранилище данных
# ============================================================

class BotData:
    """Хранит все данные бота — загруженные с сайта или резервные"""

    def __init__(self):
        self.MAIN_TEXT = ""
        self.EGE_TEXT = ""
        self.EGE_LINKS = []
        self.PROGRAMS_TEXT = ""
        self.BAK_TEXT = ""
        self.BAK_LINKS = []
        self.MAG_TEXT = ""
        self.MAG_LINKS = []
        self.ASP_TEXT = ""
        self.ASP_LINKS = []
        self.SPO_TEXT = ""
        self.SPO_LINKS = []
        self.ADMISSION_TEXT = ""
        self.ADMISSION_LINKS = []
        self.CONTACTS_TEXT = ""
        self.DOCUMENTS_TEXT = ""
        self.DOCUMENTS_LINKS = []
        self.DATES_TEXT = ""
        self.FAQ_TEXT = ""
        self.FAQ_QUESTIONS = []
        self.FAQ_ANSWERS = []
        self.NEWS = []
        self.STATS_LINKS = []
        self.EXAMS_TEXT = ""
        self.loaded = False

    def load_from_site(self):
        log.info("Загрузка данных с сайта ЗабГУ...")

        main = _parse_main_page()
        if main:
            if main["faq_questions"]:
                self.FAQ_QUESTIONS = main["faq_questions"]
                self.FAQ_ANSWERS = main["faq_answers"]
            if main["contacts"]:
                self.CONTACTS_TEXT = main["contacts"]
            if main["news"]:
                self.NEWS = main["news"]

        docs = _parse_documents_page()
        if docs:
            self.DOCUMENTS_TEXT = docs["short_list"]
            if docs.get("links"):
                self.DOCUMENTS_LINKS = docs["links"]

        dates = _parse_dates_page()
        if dates:
            self.DATES_TEXT = dates

        campaign = _parse_campaign_page()
        if campaign:
            self.ADMISSION_TEXT = campaign

        exams = _parse_exams_page()
        if exams:
            self.EXAMS_TEXT = exams

        stats = _parse_stats_page()
        if stats:
            self.STATS_LINKS = stats

        kcp = _parse_kcp_page()
        if kcp:
            if kcp["bak"]:
                self.BAK_LINKS = kcp["bak"]
            if kcp["mag"]:
                self.MAG_LINKS = kcp["mag"]
            if kcp["asp"]:
                self.ASP_LINKS = kcp["asp"]
            if kcp["spo"]:
                self.SPO_LINKS = kcp["spo"]

        ege = _parse_ege_page()
        if ege:
            self.EGE_TEXT = ege["text"][:2000]
            if ege.get("links"):
                self.EGE_LINKS = ege["links"]

        self._fill_texts()
        self.loaded = True
        log.info(f"Загрузка завершена. FAQ: {len(self.FAQ_QUESTIONS)}, Новости: {len(self.NEWS)}, "
                 f"БАК PDF: {len(self.BAK_LINKS)}, МАГ PDF: {len(self.MAG_LINKS)}, "
                 f"АСП PDF: {len(self.ASP_LINKS)}, СПО PDF: {len(self.SPO_LINKS)}")

    def _fill_texts(self):
        """Заполняет текстовые блоки с Markdown-форматированием.
        Статичные разделы ВСЕГДА перезаписываются форматированными.
        С сайта тянутся только динамические данные: новости, PDF, FAQ."""

        # === ВСЕГДА ФОРМАТИРОВАННЫЕ (перезаписывают сырой текст с сайта) ===

        self.MAIN_TEXT = (
            "🏛 **Добро пожаловать в бот приёмной комиссии ЗабГУ!**\n\n"
            "Здесь вы найдёте информацию о поступлении в Забайкальский "
            "государственный университет в 2026 году.\n\n"
            "Выберите нужный раздел 👇"
        )

        self.EGE_TEXT = self._build_ege_text()

        self.PROGRAMS_TEXT = (
            "📚 **Образовательные программы ЗабГУ**\n\n"
            "Выберите уровень образования:"
        )

        self.BAK_TEXT = (
            "🎓 **Бакалавриат и специалитет**\n\n"
            "Более 70 образовательных программ!\n\n"
            "План приёма (КЦП) 2026:"
        )

        self.MAG_TEXT = (
            "🎓 **Магистратура**\n\n"
            "Готовим высококлассных специалистов!\n\n"
            "План приёма (КЦП) 2026:"
        )

        self.ASP_TEXT = (
            "🎓 **Аспирантура**\n\n"
            "Подготовка научных кадров высшей квалификации!\n\n"
            "План приёма (КЦП) 2026:"
        )

        self.SPO_TEXT = (
            "🏫 **Среднее профессиональное образование**\n\n"
            "Колледж ЗабГУ\n\n"
            "План приёма 2026:"
        )

        # Контакты — ВСЕГДА форматированные
        self.CONTACTS_TEXT = self._build_contacts_text()

        # Документы — ВСЕГДА форматированные
        self.DOCUMENTS_TEXT = (
            "📑 **Документы для поступления**\n\n"
            "📋 **Краткий список:**\n\n"
            "• Копия паспорта (основная страница + прописка)\n"
            "• Копия аттестата/диплома + **оригинал** для зачисления\n"
            "• Копия медицинской справки 086/у\n"
            "• Копия СНИЛС\n"
            "• Копии документов о льготах / целевом / достижениях\n"
            "• 2 фотографии 3×4 см\n\n"
            f"[Подробный список на сайте]({BASE}/?page_id=193)"
        )

        # Сроки — ВСЕГДА форматированные
        self.DATES_TEXT = (
            "🗓 **Сроки приёма документов 2026**\n\n"
            "Подача документов начинается с **20 июня 2026**:\n\n"
            "📍 Лично — ул. Бабушкина, 129\n"
            "💻 Через Госуслуги\n"
            "✉️ Почтой России\n\n"
            f"[Подробные сроки на сайте]({BASE}/?page_id=16)"
        )

        # Вступительные — ВСЕГДА форматированные
        self.EXAMS_TEXT = (
            "📝 **Вступительные испытания**\n\n"
            "Поступление на базе 11 классов — по результатам **ЕГЭ**.\n\n"
            "На базе СПО/ВО — по выбору: ЕГЭ или тестирование в ЗабГУ.\n\n"
            f"[Перечень ВИ]({BASE}/?page_id=124) · "
            f"[Программы ВИ]({BASE}/?page_id=140) · "
            f"[Мин. баллы]({BASE}/?page_id=130) · "
            f"[Расписание]({BASE}/?page_id=132)"
        )

        # Приёмная кампания — ВСЕГДА форматированные
        self.ADMISSION_TEXT = (
            "🏛 **Приёмная кампания 2026**\n\n"
            "ЗабГУ ждёт вас! Выберите нужный раздел ниже 👇\n\n"
            f"[Информация о приёме]({BASE}/?page_id=4235)\n"
            f"[План приёма (КЦП)]({BASE}/?page_id=8072)"
        )

        self.FAQ_TEXT = "❓ **Часто задаваемые вопросы**"

        # === ДИНАМИЧЕСКИЕ ДАННЫЕ (только если сайт не дал) ===

        if not self.BAK_LINKS:
            self.BAK_LINKS = [
                {"title": "🔗 Очная форма", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%B1%D0%B0%D0%BA%D0%B0%D0%BB%D0%B0%D0%B2%D1%80%D0%B8%D0%B0%D1%82%20%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf"},
                {"title": "🔗 Очно-заочная форма", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%B1%D0%B0%D0%BA%D0%B0%D0%BB%D0%B0%D0%B2%D1%80%D0%B8%D0%B0%D1%82%20%D0%BE%D1%87%D0%BD%D0%BE-%D0%B7%D0%B0%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf"},
                {"title": "🔗 Заочная форма", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%B1%D0%B0%D0%BA%D0%B0%D0%BB%D0%B0%D0%B2%D1%80%D0%B8%D0%B0%D1%82%20%D0%B7%D0%B0%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf"},
            ]

        if not self.MAG_LINKS:
            self.MAG_LINKS = [
                {"title": "🔗 Очная форма", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%BC%D0%B0%D0%B3%D0%B8%D1%81%D1%82%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0%20%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf"},
                {"title": "🔗 Очно-заочная форма", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%BC%D0%B0%D0%B3%D0%B8%D1%81%D1%82%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0%20%D0%BE%D1%87%D0%BD%D0%BE-%D0%B7%D0%B0%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf"},
                {"title": "🔗 Заочная форма", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%BC%D0%B0%D0%B3%D0%B8%D1%81%D1%82%D1%80%D0%B0%D1%82%D1%83%D1%80%D0%B0%20%D0%B7%D0%B0%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf"},
            ]

        if not self.ASP_LINKS:
            self.ASP_LINKS = [
                {"title": "🔗 Очная форма", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%B0%D1%81%D0%BF%D0%B8%D1%80%D0%B0%D0%BD%D1%82%D1%83%D1%80%D0%B0%20%D0%BE%D1%87%D0%BD%D0%B0%D1%8F%20%D1%84%D0%BE%D1%80%D0%BC%D0%B0.pdf"},
            ]

        if not self.SPO_LINKS:
            self.SPO_LINKS = [
                {"title": "🔗 На базе 9 классов", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%A1%D0%9F%D0%9E%209.pdf"},
                {"title": "🔗 На базе 11 классов", "url": f"{BASE}/abitur/02%20-%20%D0%9A%D0%A6%D0%9F/%D0%9A%D0%A6%D0%9F%20%D0%A1%D0%9F%D0%9E%2011.pdf"},
            ]

        if not self.FAQ_QUESTIONS:
            self._fallback_faq()

    def _build_ege_text(self) -> str:
        """Строит красивый текст с минимальными баллами ЕГЭ"""
        lines = [
            "📊 **Минимальные баллы ЕГЭ 2026**",
            "",
            "Предмет | Мин. балл",
            "---|---",
        ]
        for subject, score in EGE_MIN_SCORES.items():
            lines.append(f"{subject} | **{score}**")

        lines.append("")
        lines.append("**Макс. балл по вузовским ВИ — 100** для всех предметов")
        lines.append("")
        lines.append(
            f"[Калькулятор ЕГЭ]({BASE}/?page_id=4569) · "
            f"[Перечень ВИ]({BASE}/?page_id=124) · "
            f"[Подробнее на сайте]({BASE}/?page_id=130)"
        )
        return "\n".join(lines)

    def _build_contacts_text(self) -> str:
        """Строит текст контактов с форматированием"""
        return (
            "📞 **Контакты приёмной комиссии ЗабГУ**\n\n"
            "📍 **Адрес:** г. Чита, ул. Бабушкина, д. 129\n\n"
            "📞 **Телефоны:**\n"
            "+7 (3022) 35-16-35\n"
            "+7 (3022) 21-86-35\n\n"
            "📧 **Email:**\n"
            "postupaivzabgu@mail.ru\n"
            "abiturient@zabgu.ru\n\n"
            "🕐 **График работы:**\n"
            "Пн–Пт: 9:00–17:00\n"
            "Сб: 9:00–13:00\n"
            "Вс: выходной\n\n"
            "☎️ **Горячая линия:** 8-800-301-44-55\n"
            "☎️ **Единый контакт-центр Минобрнауки:** 8-800-444-51-15\n\n"
            f"[Личный кабинет поступающего](https://lk.zabgu.ru)"
        )

    def _fallback_faq(self):
        self.FAQ_QUESTIONS = [
            "Что такое «Согласие на зачисление», когда и как его подавать?",
            "Можно ли поступить в ЗабГУ после 9 класса?",
            "Поступил в колледж на базе 9 классов, закончил первый курс. Могу поступить в вуз?",
            "Как перевестись в ЗабГУ из колледжа или техникума?",
            "Есть ли льготы при поступлении в ЗабГУ?",
            "Можно ли перевестись с одной специальности на другую?",
            "Поступил на платную основу. Могу ли перевестись на бюджет?",
            "Можно ли поступить в ЗабГУ без ЕГЭ?",
            "Я сдавал базовую математику. Смогу поступить?",
            "Учился в ЗабГУ, потом бросил. Как восстановиться?",
        ]
        self.FAQ_ANSWERS = [
            "Согласие на зачисление подаётся на **одно конкретное направление одного конкретного вуза**, когда абитуриент окончательно определился. Распечатать можно из кабинета поступающего (lk.zabgu.ru). Скан-копии отправить на postupaivzabgu@mail.ru",
            "Нет, к получению высшего образования допускаются выпускники 11 классов. После 9 класса можно поступить в гуманитарно-технический колледж ЗабГУ.",
            "Студенты первого курса СПО допускаются к сдаче ЕГЭ на основании справки об освоении программы среднего общего образования. Данная справка **не является** документом об образовании, и приёмная комиссия её не принимает.",
            "Переводы возможны только между организациями одного уровня образования. Из СПО нельзя перевестись в ВО. Можно перевестись на программы СПО ЗабГУ.",
            "Право на особую квоту имеют: инвалиды, сироты, ветераны боевых действий. Наличие льготы **не гарантирует** поступление — нужно сдать экзамены и опередить других кандидатов.",
            "Перевод возможен после успешной аттестации за первый семестр. Вопросы решаются в деканате. Бюджетное место при переводе не сохраняется.",
            "Перевод на бюджет возможен после первого курса при наличии свободных бюджетных мест. Сессия должна быть сдана на «хорошо» и «отлично».",
            "Лица на базе 11 классов обязаны предоставить результаты ЕГЭ. На базе диплома СПО или ВО — по усмотрению: ЕГЭ или вузовское тестирование.",
            "Если в перечне ВИ указана математика — нужен **профильный уровень**. Базовая математика нужна только для аттестата. Если математика не указана — сдаются другие предметы.",
            "Обратитесь в деканат своего факультета. Если прошло более 5 лет — нужно забрать документы из архива и поступать заново. ЕГЭ должен быть сдан не более 4 лет назад.",
        ]


# Глобальный экземпляр
data = BotData()
