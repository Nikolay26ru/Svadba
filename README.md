# Svadba — сайт-приглашение на свадьбу с RSVP и админкой

Лёгкий веб-сервис: персональные ссылки-приглашения для гостей и закрытая
админ-панель для организатора (генерация ссылок и статистика ответов).

- **Гость** открывает персональную ссылку `/(i)/<id>`, нажимает «Принять» или
  «Отклонить», вводит имя и фамилию. Ответ сразу сохраняется; ссылку можно
  открыть повторно и изменить ответ.
- **Админка** (по секретному адресу + пароль) — генерация неограниченного числа
  ссылок, копирование в один клик, счётчики и таблица ответов.

## Стек

Python 3 · Flask · gunicorn · SQLite · nginx · systemd · Let's Encrypt.
Минимум внешних зависимостей: данные в SQLite-файле, всё поднимается из коробки.

## Структура

```
app/            Flask-приложение
  main.py       маршруты (гость + админка)
  db.py         схема и доступ к SQLite
  mailer.py     уведомления на почту (в фоне, best-effort)
  config.py     конфигурация из переменных окружения
  templates/    HTML (Jinja2)
  static/       CSS
deploy/         systemd-юниты, конфиг nginx, скрипты установки и авто-HTTPS
tools/          проверка почты
```

## Конфигурация

Все настройки — через переменные окружения (см. `.env.example`). Секреты
(`SECRET_KEY`, хеш пароля админки, пароль почты) хранятся только на сервере в
`/opt/svadba/svadba.env` и **не** попадают в репозиторий.

## Установка на сервер

```bash
git clone <repo> /opt/svadba
cd /opt/svadba
ADMIN_PASSWORD='<пароль админки>' MAIL_PASS='<пароль почты>' \
  MAIL_ENABLED=true bash deploy/deploy.sh
```

Скрипт ставит зависимости, создаёт сервисного пользователя, виртуальное
окружение, БД, systemd-сервис (автозапуск после перезагрузки), nginx и таймер
авто-выпуска HTTPS. Когда домен начинает резолвиться на сервер, сертификат
Let's Encrypt выпускается автоматически.

## Локальный запуск

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
cd app && SECRET_KEY=dev ADMIN_PATH=admin COOKIE_SECURE=false \
  ADMIN_PASSWORD_HASH="$(python -c "from werkzeug.security import generate_password_hash as g;print(g('753951'))")" \
  python main.py
# http://127.0.0.1:8000/  ·  админка: http://127.0.0.1:8000/admin
```

## Проверка почты

```bash
MAIL_USER=info@kostya-i-gera.ru MAIL_PASS='<пароль>' python3 tools/email_test.py
```
