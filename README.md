# tg-mcp

MCP-коннектор к личному Telegram-аккаунту (MTProto через Telethon) для claude.ai, позже — Gemini.
Деплой — в кластер tihonove.dev ([GUIDE](https://github.com/tihonove/tihonove.dev-apps/blob/main/GUIDE.md)).

Доступ в PoC — секрет в пути URL: `https://tg-mcp.tihonove.dev/mcp/<MCP_PATH_SECRET>`.
Аварийная кнопка: Telegram → Settings → Devices → завершить сессию `tg-mcp prod`.

## Команды (`mise tasks`)

| | |
|---|---|
| `mise run setup` | зависимости + GPG-ключ платформы для sops |
| `mise run login` | вход в Telegram (QR; `-- --phone` — по коду) → `.env` |
| `mise run dev` | локальный HTTP-сервер на :8080 |
| `mise run inspect` | MCP Inspector |
| `mise run url` | URL коннекторов (с секретом) |
| `mise run login:prod` | отдельная сессия для кластера → `.env.prod` |
| `mise run secrets:encrypt` | `.env.prod` → `deploy/secrets.enc.yaml` (sops) |
| `mise run release` | сборка образа в Actions + бамп тега в `deploy/` |
| `mise run register` | PR с регистрацией в tihonove.dev-apps |
| `mise run status` | healthz прода |

## Где лежат секреты

| Файл | Что | В git |
|---|---|---|
| `.env` | локальные `TG_API_ID`, `TG_API_HASH`, `TG_SESSION`, `MCP_PATH_SECRET` | нет |
| `.env.prod` | то же для прода (своя сессия, свой секрет) | нет |
| `deploy/secrets.enc.yaml` | `.env.prod`, зашифрованный sops | да |

В кластере секрет монтируется файлами в `/run/secrets/app` (не env).
