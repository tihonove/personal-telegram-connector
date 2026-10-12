"""One-time interactive Telegram login: writes TG_SESSION (and other keys if missing) into an env file.

tg-mcp-login --env-file .env          # local dev session
tg-mcp-login --env-file .env.prod     # separate session for the cluster
"""

import argparse
import asyncio
import getpass
import os
import secrets
import sys
from pathlib import Path

import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from tg_mcp.config import require


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def upsert_env_file(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    pending = dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    lines += [f"{key}={value}" for key, value in pending.items()]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)


def print_qr(url: str) -> None:
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.print_ascii(invert=True)


async def login_qr(client: TelegramClient) -> None:
    qr_login = await client.qr_login()
    while True:
        print("\nTelegram на телефоне → Settings → Devices → Link Desktop Device, отсканируй:\n")
        print_qr(qr_login.url)
        try:
            await qr_login.wait(timeout=60)
            return
        except TimeoutError:
            print("QR истёк, генерирую новый...")
            await qr_login.recreate()
        except SessionPasswordNeededError:
            await client.sign_in(password=getpass.getpass("Пароль 2FA: "))
            return


async def login_phone(client: TelegramClient) -> None:
    phone = input("Телефон (+7...): ").strip()
    await client.send_code_request(phone)
    code = input("Код из Telegram: ").strip()
    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        await client.sign_in(password=getpass.getpass("Пароль 2FA: "))


async def run(args: argparse.Namespace) -> None:
    api_id, api_hash = int(require("TG_API_ID")), require("TG_API_HASH")
    client = TelegramClient(StringSession(), api_id, api_hash, device_model=args.device_name)
    await client.connect()
    try:
        await (login_phone(client) if args.phone else login_qr(client))
        me = await client.get_me()
        session = client.session.save()
    finally:
        await client.disconnect()

    env_path = Path(args.env_file)
    existing = read_env_file(env_path)
    updates = {"TG_API_ID": str(api_id), "TG_API_HASH": api_hash, "TG_SESSION": session}
    if not existing.get("MCP_PATH_SECRET"):
        updates["MCP_PATH_SECRET"] = secrets.token_urlsafe(32)
    upsert_env_file(env_path, updates)
    print(f"\nВошёл как {me.first_name} (@{me.username}, id {me.id}). Сессия записана в {env_path} (chmod 600).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--device-name", default="tg-mcp")
    parser.add_argument("--phone", action="store_true", help="вход по телефону и коду вместо QR")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        sys.exit(130)
