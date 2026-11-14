# Аромакадемія (Версія 1 · MVP)

Навчальний PWA-застосунок у форматі Duolingo + цифрова помічниця Арома за ТЗ ([ТЗ на розробку Аромакадемія (застосунок + Арома).md](ТЗ%20на%20розробку%20Аромакадемія%20(застосунок%20+%20Арома).md)).

## Архітектура

- **Бекенд (`backend/`)**: Python 3.13 + FastAPI + SQLAlchemy 2.0 (локально SQLite, у проді PostgreSQL + `pgvector` через `DATABASE_URL`).
- **Фронтенд (`frontend/`)**: PWA (Web Manifest + Service Worker + модульний ES6 UI без потреби у Node.js збірці), українська локалізація (`frontend/js/i18n.uk.js`).
- **Сервіс Арома (`backend/app/aroma_service.py`)**: контракт `POST /v1/aroma/ask`, фільтрація бази знань за тарифом у SQL-запиті, становий автомат безпеки до моделі (вагітність, діти, діагнози/дозування), посилання на уроки-джерела, переіндексація при публікації уроку.
- **Медіа (`media/videos/`)**: локальне сховище для відеофайлів Арома-роликів.

## Швидкий запуск локально (Windows / Python 3.13)

```powershell
C:\Users\arina\.venvs\aromaacademy\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000
```

Відкрити у браузері: `http://127.0.0.1:8000` (Swagger API: `http://127.0.0.1:8000/docs`).

## Як додати своє 1-ше відео

1. Перемкніться у верхньому правому меню на **Наталія (Адмін)** (або увійдіть як `natalia@aroma.ua`).
2. Відкрийте вкладку **Адмін → 🎬 Арома-ролики (14)** та завантажте `.mp4` / `.webm` / `.mov` для ролика `1. Ефірні олії: основи` (урок 1.1).
   *Або просто покладіть файл `1.mp4` у папку `media/videos/` до запуску.*

## Автотести критеріїв приймання (ТЗ розділ 11)

```powershell
C:\Users\arina\.venvs\aromaacademy\Scripts\python.exe -m pytest -v
```

## Запуск у Docker + PostgreSQL (pgvector)

```bash
docker compose up --build
```

