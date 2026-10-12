"""Telethon client lifecycle and helpers shared by the tools."""

import asyncio
import os
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from telethon import TelegramClient, utils
from telethon.sessions import StringSession
from telethon.tl.custom import Dialog, Message
from telethon.tl.types import Channel, Chat, User

from tg_mcp.config import Settings

TZ = ZoneInfo(os.environ.get("TIMEZONE", "UTC"))
DIALOG_CACHE_TTL = 60


class ChatNotFound(ValueError):
    pass


class SessionInvalid(RuntimeError):
    pass


class Telegram:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: TelegramClient | None = None
        self._lock = asyncio.Lock()
        self._dialogs: list[Dialog] = []
        self._dialogs_at = 0.0

    async def client(self) -> TelegramClient:
        # Created lazily so it binds to the event loop the server actually runs on.
        async with self._lock:
            if self._client is None:
                client = TelegramClient(
                    StringSession(self._settings.session),
                    self._settings.api_id,
                    self._settings.api_hash,
                    device_model=self._settings.device_name,
                )
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    raise SessionInvalid("Telegram-сессия невалидна (завершена в Devices?). Нужно перелогиниться.")
                self._client = client
            elif not self._client.is_connected():
                await self._client.connect()
            return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()

    async def dialogs(self, *, refresh: bool = False) -> list[Dialog]:
        if refresh or time.monotonic() - self._dialogs_at > DIALOG_CACHE_TTL:
            client = await self.client()
            self._dialogs = await client.get_dialogs(limit=None)
            self._dialogs_at = time.monotonic()
        return self._dialogs

    async def resolve(self, chat: str | int) -> Any:
        """Accepts 'me', numeric id, @username, t.me link, +phone or (part of) a dialog title."""
        client = await self.client()
        ref = str(chat).strip()
        if ref.lower() in ("me", "self", "saved", "saved messages"):
            return await client.get_input_entity("me")
        if ref.lstrip("-").isdigit():
            peer_id = int(ref)
            try:
                return await client.get_input_entity(peer_id)
            except ValueError:
                for d in await self.dialogs(refresh=True):
                    if d.id == peer_id:
                        return d.input_entity
                raise ChatNotFound(f"Чат с id {peer_id} не найден среди диалогов") from None
        if ref.startswith(("@", "+", "http://", "https://", "t.me/")):
            return await client.get_input_entity(ref)

        needle = ref.casefold()
        dialogs = await self.dialogs()
        exact = [d for d in dialogs if d.name.casefold() == needle]
        partial = exact or [d for d in dialogs if needle in d.name.casefold()]
        if len(partial) == 1:
            return partial[0].input_entity
        if len(partial) > 1:
            options = ", ".join(f"{d.name} (id {d.id})" for d in partial[:10])
            raise ChatNotFound(f"Под '{ref}' подходит несколько чатов: {options}. Укажи id.")
        try:
            return await client.get_input_entity(ref)
        except ValueError:
            raise ChatNotFound(f"Чат '{ref}' не найден. Попробуй find_contact.") from None


def fmt_date(value: datetime | None) -> str | None:
    return value.astimezone(TZ).isoformat(timespec="seconds") if value else None


def entity_kind(entity: Any) -> str:
    if isinstance(entity, User):
        return "bot" if entity.bot else "user"
    if isinstance(entity, Chat):
        return "group"
    if isinstance(entity, Channel):
        return "channel" if entity.broadcast else "group"
    return "unknown"


def describe_entity(entity: Any) -> dict[str, Any]:
    info: dict[str, Any] = {
        "id": utils.get_peer_id(entity),
        "name": utils.get_display_name(entity),
        "type": entity_kind(entity),
    }
    if getattr(entity, "username", None):
        info["username"] = "@" + entity.username
    if isinstance(entity, User) and entity.phone:
        info["phone"] = "+" + entity.phone
    return info


def describe_media(message: Message) -> dict[str, Any] | None:
    if not message.media:
        return None
    if message.web_preview:
        return {"type": "webpage", "url": getattr(message.web_preview, "url", None)}
    kind = (
        "photo"
        if message.photo
        else "voice"
        if message.voice
        else "video_note"
        if message.video_note
        else "video"
        if message.video
        else "audio"
        if message.audio
        else "sticker"
        if message.sticker
        else "gif"
        if message.gif
        else "document"
        if message.document
        else "poll"
        if message.poll
        else "geo"
        if message.geo
        else "contact"
        if message.contact
        else type(message.media).__name__
    )
    info: dict[str, Any] = {"type": kind}
    if message.file:
        if message.file.name:
            info["file_name"] = message.file.name
        if message.file.mime_type:
            info["mime_type"] = message.file.mime_type
        if message.file.size:
            info["size"] = message.file.size
    return info


def describe_message(message: Message, *, with_chat: bool = False) -> dict[str, Any]:
    info: dict[str, Any] = {
        "id": message.id,
        "date": fmt_date(message.date),
        "from": utils.get_display_name(message.sender) if message.sender else None,
        "from_id": message.sender_id,
        "out": message.out,
        "text": message.message or "",
    }
    if with_chat and message.chat:
        info["chat"] = utils.get_display_name(message.chat)
        info["chat_id"] = message.chat_id
    if message.reply_to_msg_id:
        info["reply_to"] = message.reply_to_msg_id
    if message.fwd_from:
        info["forwarded_from"] = message.fwd_from.from_name or (
            utils.get_peer_id(message.fwd_from.from_id) if message.fwd_from.from_id else "hidden"
        )
    if media := describe_media(message):
        info["media"] = media
    if message.edit_date:
        info["edited"] = fmt_date(message.edit_date)
    return info
