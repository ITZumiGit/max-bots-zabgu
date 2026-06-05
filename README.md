# 🤖 Max Messenger Bots — ЗабГУ

Три бота для платформы Max (бывший ICQ) приёмной комиссии Забайкальского государственного университета.

## 📦 Боты

| Бот | Описание | Команды |
|---|---|---|
| **Фёдор** | Бот приёмной комиссии — ЕГЭ калькулятор, программы, FAQ, новости | `/start`, `/refresh` |
| **QA** | Вопрос-ответ — студенты задают, модераторы отвечают | `/q <вопрос>`, `/a <номер> <ответ>`, `/list` |
| **Забава** | Сбор новостей — отправка новостей в группу | `/news <текст>` |

## 🛠 Стек

- Python 3.12+
- aiohttp (чистый, без maxgram/maxapi — они мёртвые)
- BeautifulSoup4 (Фёдор — парсинг сайта ЗабГУ)
- python-dotenv

## 🚀 Запуск

### Docker Compose (рекомендуется)

```bash
# Клонировать
git clone https://github.com/ITZumiGit/max-bots-zabgu.git
cd max-bots-zabgu

# Скопировать и заполнить .env
cp fedor/.env.example fedor/.env
cp qa/.env.example qa/.env
cp zabava/.env.example zabava/.env

# Запустить
docker compose up -d
```

### Без Docker

```bash
# Фёдор
cd fedor
pip install -r requirements.txt
# Заполнить .env
python main.py

# QA
cd ../qa
pip install -r requirements.txt
python main.py

# Забава
cd ../zabava
pip install -r requirements.txt
python main.py
```

## ⚙️ Переменные окружения

### Фёдор
| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота Max |

### QA
| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота Max |
| `GROUP_ID` | ID группы модераторов |

### Забава
| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен бота Max |
| `GROUP_ID` | ID группы для новостей |

## 🔑 Получение токена Max Bot

1. Перейдите на [dev.max.ru](https://dev.max.ru)
2. Создайте нового бота
3. Скопируйте токен в `.env`

## 📁 Структура

```
├── docker-compose.yml
├── fedor/
│   ├── main.py          # Основная логика бота
│   ├── bot_data.py      # Парсинг сайта ЗабГУ
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
├── qa/
│   ├── main.py
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
└── zabava/
    ├── main.py
    ├── .env.example
    ├── Dockerfile
    └── requirements.txt
```

## ⚠️ Max Bot API особенности

- `user_id` / `chat_id` — **query-параметры** URL, не тело запроса
- Личные диалоги → `?user_id=<id>`, группы → `?chat_id=<id>`
- Тело запроса: `{"text": "...", "format": "markdown"}`
- Авторизация: `Authorization: <token>` (без Bearer)
- Inline-клавиатура: `type: "inline_keyboard"` + `payload: {buttons: [[...]]}`

## 📄 Лицензия

MIT
