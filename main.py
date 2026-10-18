import os
import gc
import re
import time
import shutil
import ctypes
import base64
import struct
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Set, Optional, Tuple, Any
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.storage import Storage
from pyrogram.types import Message
from pyrogram.enums import ChatType
from pyrogram.errors import (
    FloodWait,
    PremiumAccountRequired,
    UserPrivacyRestricted,
    PeerFlood,
    UserIsBlocked,
    PeerIdInvalid,
    UsernameNotOccupied,
    UsernameInvalid,
    RPCError,
)

# ---------------------------------------------------------------------------
# Logging & Memory Configuration for Render (512 MB RAM Tier Optimized)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("PyroFleet")
logging.getLogger("pyrogram").setLevel(logging.WARNING)

CACHE_CLEAR_INTERVAL = 3600  # 1 hour (3600 seconds)
COMMAND_PREFIXES = ["*", "."]
TEMP_DIRS = ["./downloads", "./cache", "./temp_media"]
MAX_VAULT_MESSAGES_PER_CHAT = 150

last_cache_clear_iso: str = "Never"
active_clients: List[Client] = []

# Anti-Delete (*Lockme) Vault Structures
locked_chats_per_client: Dict[str, Set[int]] = {}
global_lockme_enabled: Dict[str, bool] = {}
message_vault: Dict[str, Dict[int, Dict[str, Any]]] = {}

# ---------------------------------------------------------------------------
# 5-Account Configuration Pool (Session Strings Pre-Configured — No OTP Needed)
# ---------------------------------------------------------------------------
ACCOUNTS = [
    {
        "index": 1,
        "name": "Account 1 (+916209065785)",
        "api_id": 33248589,
        "api_hash": "cb94a9acfa11e9aaf1195610f4144e65",
        "phone_number": "+916209065785",
        "session_string": "1BVtsOLwBu7MlAul6aus_Dqc-NYeZYb5HzuH4U3tv9BLx7niAQUkiEA4FegpUXFkVyJvWHIChOHyDNhyXnBgqUIHhNXUOH1Q8dhUNBZ3B1eUXCg4AJUG0JwYLC0u0r_zDDbeth-vC3AdTdsincSJKSv9PMvYlTgoAyLlCFfSkhUxZ0Ng6tgmdz0hRhfVBDMrJAOn7rzeC6hTwIiVQNMMI10uYk-6fzqDdpLqAbWRlyFd7fYIZhquSTbXsDN0AFHOVSF3mv0Hh8qDw1be4-Y6Wh4e7d0ZemA9I2P1u4Hq8uAM5yUsKL6Tkj3U8Yfg7aki1Rm-5z-eN3KgIyTjkjaxeFl6GlVZIdAU=",
    },
    {
        "index": 2,
        "name": "Account 2 (+916306499318)",
        "api_id": 33272640,
        "api_hash": "bb1df63726fabb470b0e3f7262511a9b",
        "phone_number": "+916306499318",
        "session_string": "1BVtsOJMBu7MahlPiCTe_vUcNebguVTyThz38edRlhVg6GNYYk-UAsceo8WyRkiYtL3KSbQZPyzO2lxl86XzRyn0FlQGjzvG8D4YBxQ8UjmJOT7mwjcCmo1MWD9KLC1Cd0eS0vPV9bwz5T2pbhNxxwlG0bjVaaH5wBFxcmULNMuQOskkhkTFTANtpV5wMHleNE3Fx8L0cbNhI5LUQEj891Ic7yk_ZSkVXuKwTsbHpMfFf-gxQL9GwUuvP9sw-5y6kDB-OiZfw0vvxcq7uNFrEiaAjykUf2vWv2N3MHm-gb-RfctAU7p3Ih8o7uK4P2EbQEPSdIL8aL0COX9NyurtRrEzQBcNmHho=",
    },
    {
        "index": 3,
        "name": "Account 3 (+919870857249)",
        "api_id": 39538277,
        "api_hash": "17aa161a9eaafef73a0e7e5aa9a665b5",
        "phone_number": "+919870857249",
        "session_string": "1BVtsOJMBu7YbvYAtt5FpVDQz2fZD66idtGM4QguBtZvoVHwxAYF4obF7XDHLjyEnc1zkRkTdkoaWM9_IhIwEjsdUGJ8nP3K89chIOaVoKiiCnFwYAotCrSD-YM_ueDXn6l8guV1Z3nLELmqtRAIOJTMl4VNBhG4Uq7vCPqVQV8Cz2SI8VSPy38LtOkFxJp2_QTpw0t8PxmLvXZkKIdTYAdsGzS1pb1vUSzNt51Ua-kuRWthuYS20Eh6afCZkLpCJQ-mNKIjNWG8EIExRQrpl9z3qBFdTy8uFmBww7O5tbmWYD_hveyiYUvDUQ2Dy1D75yDc6pHx7uBLoodQAC8ge8PIujMHgouc=",
    },
    {
        "index": 4,
        "name": "Account 4 (+18459083686)",
        "api_id": 34874968,
        "api_hash": "ef6de5c8b022888bcb58b690aab26eea",
        "phone_number": "+18459083686",
        "session_string": "1AZWarzkBu61UP-9NQlbbWKmnDiIi1V3vDZu2dj0Du8vQjVqtz62OoypOtos2dkh8oyq2-4ziZmWUMmtcX2v2mIX-_LscHm4kPjmO9Z0LB7lLWXVHW2rTimr2WwQBjxX0L5nCIUbygrpRc3b0By6mbtzgImoZBPK-cK2TMBahH2Pe9884CPaYdN7deN1m4CENXlNpTQXtAFvHQdWVtnF1pAMtkvr_ZI0qpeLmXa7PJuQPulY1kVvH78QBvhVIJwBh8kTN31IzLYgOyhCGA4MFWWENFxRZn8UdvY8kvxYwCAkIrUcOv8L-6q2rqPGCgJ4C03mVYVw1rNCfrIFnJ2NNssDWkiFn00E=",
    },
    {
        "index": 5,
        "name": "Account 5 (+917051615832)",
        "api_id": 34096655,
        "api_hash": "ed7b99a630dc421b80df31e46f7ae32c",
        "phone_number": "+917051615832",
        "session_string": "1BVtsOIwBuyKYTena2gGIx7PwkIrTV0C03wXcV-P6HtEQjKiGGug9dOVkPEAL-Q_yu2bKVxe7W51Kd7uMBlp8_eIwijaXIqEymwQNVcY1HQDVuavBDJQrwvc_lbPYzZEO9gMEc3GGneXeM_Vv6w8qWYJrDnyOqjUANO1EsGxG54nqZdPEZU-u4VZNLMWGp4TjwBafjsDQP6Ouhked5MZsE0EDvcisVvwN2EnpO19e-Wim6-gcAYw5ULb1TXTcwa3E3XTcEx3EraJCaAwMMVysYXYKGiQDpHntriZw6n13wJuPKObhv7BdZ1zSGgkltKpQz8WITT0ZpAiks1p8EmwASeLgg_g2wkQ=",
    },
]


def normalize_session_string(session_str: str, api_id: int) -> str:
    """
    Converts 1BVts.../1AZWar... session strings into Pyrogram's binary format
    with a non-zero placeholder user_id so Pyrogram NEVER asks for an OTP.
    """
    s = (session_str or "").strip()
    if s.startswith("1") and len(s) in (353, 369):
        try:
            body = s[1:]
            raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
            if len(raw) in (263, 275):
                dc_id = raw[0]
                auth_key = raw[-256:]
                placeholder_uid = 999999999  # Non-zero so Pyrogram skips OTP prompt
                fmt = getattr(Storage, "SESSION_STRING_FORMAT", ">BI?256sQ?")
                if fmt == ">BI?256sQ?":
                    packed = struct.pack(fmt, dc_id, int(api_id), False, auth_key, placeholder_uid, False)
                elif fmt == ">B?256sQ?":
                    packed = struct.pack(fmt, dc_id, False, auth_key, placeholder_uid, False)
                else:
                    packed = struct.pack(">B?256sI?", dc_id, False, auth_key, placeholder_uid, False)
                converted = base64.urlsafe_b64encode(packed).decode().rstrip("=")
                logger.info(f"Loaded pre-authenticated session string (DC {dc_id}) — OTP bypassed.")
                return converted
        except Exception as exc:
            logger.warning(f"Session format normalization error: {exc}")
    return s


# ---------------------------------------------------------------------------
# Automatic 1-Hour Cache & Memory Purge Task
# ---------------------------------------------------------------------------
def release_linux_heap_memory() -> bool:
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
        return True
    except Exception:
        return False


async def clear_caches_and_memory() -> dict:
    global last_cache_clear_iso
    removed_files = 0
    freed_bytes = 0

    for folder in TEMP_DIRS:
        if os.path.exists(folder):
            for root, _, files in os.walk(folder):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        freed_bytes += os.path.getsize(fp)
                        os.unlink(fp)
                        removed_files += 1
                    except OSError:
                        pass
            shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)

    for cname, vault in list(message_vault.items()):
        if len(vault) > 500:
            sorted_ids = sorted(vault.keys())
            for old_id in sorted_ids[:-500]:
                vault.pop(old_id, None)

    for app in active_clients:
        if hasattr(app, "message_cache") and app.message_cache:
            try:
                app.message_cache.store.clear()
            except Exception:
                pass

    collected_objects = gc.collect(2)
    trimmed = release_linux_heap_memory()

    last_cache_clear_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return {
        "timestamp": last_cache_clear_iso,
        "removed_files": removed_files,
        "freed_kb": round(freed_bytes / 1024, 2),
        "gc_objects": collected_objects,
        "malloc_trimmed": trimmed,
    }


async def hourly_cache_scheduler():
    while True:
        await asyncio.sleep(CACHE_CLEAR_INTERVAL)
        try:
            await clear_caches_and_memory()
        except Exception as exc:
            logger.error(f"Error during scheduled cache purge: {exc}")


# ---------------------------------------------------------------------------
# Target Resolver: @username, username, numeric user ID, or Profile Name
# ---------------------------------------------------------------------------
async def resolve_target_on_client(app: Client, raw_target: str) -> Optional[Any]:
    target = raw_target.strip()
    if not target:
        return None

    # 1. Numeric User ID without @
    if target.lstrip("-").isdigit():
        uid = int(target)
        try:
            user = await app.get_users(uid)
            return user.id
        except Exception:
            try:
                contacts = await app.get_contacts()
                for c in contacts:
                    if c.id == uid:
                        return c.id
            except Exception:
                pass
            try:
                async for dialog in app.get_dialogs(limit=200):
                    if dialog.chat and dialog.chat.id == uid:
                        return dialog.chat.id
            except Exception:
                pass
            return uid

    # 2. Direct @username or username without @
    clean_uname = target.lstrip("@")
    if " " not in clean_uname:
        try:
            user = await app.get_users(clean_uname)
            if user:
                return user.id
        except Exception:
            pass

    # 3. Profile Name / Display Name lookup in Contacts and Recent Dialogs
    query_lower = target.lower().lstrip("@").strip()
    try:
        contacts = await app.get_contacts()
        for c in contacts:
            full_name = f"{c.first_name or ''} {c.last_name or ''}".strip().lower()
            first_name = (c.first_name or "").strip().lower()
            uname = (c.username or "").strip().lower()
            if query_lower in (full_name, first_name, uname) or (full_name and query_lower in full_name):
                return c.id
    except Exception:
        pass

    try:
        async for dialog in app.get_dialogs(limit=250):
            chat = dialog.chat
            if not chat:
                continue
            full_name = f"{chat.first_name or ''} {chat.last_name or ''}".strip().lower()
            title = (chat.title or "").strip().lower()
            uname = (chat.username or "").strip().lower()
            if query_lower in (full_name, title, uname) or (full_name and query_lower in full_name):
                return chat.id
    except Exception:
        pass

    return None


def parse_sendpremium_args(raw_args: str, replied_text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    args = raw_args.strip()
    if not args:
        return None, None

    if "|" in args:
        left, right = args.split("|", 1)
        return left.strip().strip('"').strip("'"), (right.strip() or replied_text)

    quoted_match = re.match(r'^["\']([^"\']+)["\']\s*(.*)$', args, re.DOTALL)
    if quoted_match:
        return quoted_match.group(1).strip(), (quoted_match.group(2).strip() or replied_text)

    if replied_text and args:
        parts = args.split(maxsplit=1)
        if len(parts) == 1:
            return parts[0].strip(), replied_text

    parts = args.split(maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    elif len(parts) == 1 and replied_text:
        return parts[0].strip(), replied_text

    return None, None


async def smart_deliver_message(raw_target: str, text: str, preferred_client: Optional[Client] = None) -> dict:
    attempt_logs = []
    ordered_pool = sorted(
        active_clients,
        key=lambda c: (getattr(c, "is_premium_account", False), c == preferred_client),
        reverse=True,
    )

    for app in ordered_pool:
        acc_name = app.name
        try:
            resolved_peer = await resolve_target_on_client(app, raw_target)
            peer_to_use = resolved_peer if resolved_peer is not None else raw_target.lstrip("@")
            sent = await app.send_message(chat_id=peer_to_use, text=text)
            return {
                "success": True,
                "used_account": acc_name,
                "resolved_peer": peer_to_use,
                "message_id": sent.id,
                "attempts": attempt_logs,
            }
        except PremiumAccountRequired:
            attempt_logs.append(f"[{acc_name}] PRIVACY_PREMIUM_REQUIRED on {raw_target}; trying next...")
            continue
        except (UserPrivacyRestricted, FloodWait, PeerIdInvalid, UsernameNotOccupied, UsernameInvalid, PeerFlood, UserIsBlocked, RPCError) as exc:
            attempt_logs.append(f"[{acc_name}] {type(exc).__name__}; trying next...")
            continue
        except Exception as err:
            attempt_logs.append(f"[{acc_name}] {err}")
            continue

    return {"success": False, "used_account": None, "resolved_peer": None, "message_id": None, "attempts": attempt_logs}


def store_message_in_vault(client_name: str, msg: Message):
    if not msg or not msg.chat:
        return
    text_content = msg.text or msg.caption or ""
    if not text_content and msg.media:
        text_content = f"[{msg.media.value.upper()} MEDIA]"
    if not text_content or "🔒 **[Lockme Anti-Delete" in text_content:
        return

    sender_label = "Me"
    if msg.from_user and not msg.from_user.is_self:
        sender_label = (
            f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".strip()
            or f"@{msg.from_user.username}"
            or str(msg.from_user.id)
        )

    vault = message_vault.setdefault(client_name, {})
    vault[msg.id] = {
        "chat_id": msg.chat.id,
        "sender": sender_label,
        "text": text_content,
        "date": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    }


def register_handlers(app: Client):
    locked_chats_per_client.setdefault(app.name, set())
    global_lockme_enabled.setdefault(app.name, False)
    message_vault.setdefault(app.name, {})

    @app.on_message(filters.me & filters.command(["sendpremium", "route"], prefixes=COMMAND_PREFIXES))
    async def sendpremium_cmd(client: Client, message: Message):
        raw_text = message.text or message.caption or ""
        parts = raw_text.split(maxsplit=1)
        raw_args = parts[1] if len(parts) > 1 else ""
        replied_text = (
            (message.reply_to_message.text or message.reply_to_message.caption)
            if message.reply_to_message
            else None
        )

        target_query, body = parse_sendpremium_args(raw_args, replied_text)
        if not target_query or not body:
            await message.edit_text(
                "**Usage (works inside any DM):**\n"
                "• `*sendpremium @username Your message`\n"
                "• `*sendpremium 123456789 Your message`\n"
                "• `*sendpremium \"Profile Name\" Your message`\n"
                "• `*sendpremium Profile Name | Your message`"
            )
            return

        status_msg = await message.edit_text(f"Routing message to `{target_query}`...")
        result = await smart_deliver_message(target_query, body, preferred_client=client)

        if result["success"]:
            await status_msg.edit_text(
                f"✅ **Sent to `{target_query}`** (`{result['resolved_peer']}`)\n"
                f"• **Via Account:** `{result['used_account']}`"
            )
            if message.chat and message.chat.type == ChatType.PRIVATE and not message.chat.is_self:
                await asyncio.sleep(4)
                try:
                    await status_msg.delete()
                except Exception:
                    pass
        else:
            log_text = "\n".join(f"- {line}" for line in result["attempts"][-5:])
            await status_msg.edit_text(f"❌ **Delivery failed across pool**\n{log_text}")

    @app.on_message(filters.me & filters.command(["Lockme", "lockme", "unlockme"], prefixes=COMMAND_PREFIXES))
    async def lockme_cmd(client: Client, message: Message):
        cmd_word = (message.command[0] if message.command else "lockme").lower()
        arg = (message.command[1] if message.command and len(message.command) > 1 else "").lower()
        chat_id = message.chat.id

        if cmd_word == "unlockme":
            if arg == "all":
                global_lockme_enabled[client.name] = False
                locked_chats_per_client[client.name].clear()
                await message.edit_text("🔓 **Lockme Disabled** for all DMs.")
            else:
                locked_chats_per_client[client.name].discard(chat_id)
                await message.edit_text(f"🔓 **Chat Unlocked** (`{chat_id}`).")
            return

        if arg == "all":
            global_lockme_enabled[client.name] = True
            await message.edit_text("🔒 **Global Lockme Activated Across All DMs!**")
            return

        locked_chats_per_client[client.name].add(chat_id)
        await message.edit_text(f"🔒 **Locking DM (`{chat_id}`) & Snapshotting History...**")
        snap_count = 0
        try:
            async for old_msg in client.get_chat_history(chat_id, limit=MAX_VAULT_MESSAGES_PER_CHAT):
                store_message_in_vault(client.name, old_msg)
                snap_count += 1
        except Exception:
            pass

        await message.edit_text(
            f"🔒 **Lockme Active on DM (`{chat_id}`)**\n"
            f"• **Protected Messages Cached:** `{snap_count}`\n"
            f"• Any message deleted by another userbot will be immediately restored."
        )

    @app.on_message(filters.private, group=1)
    async def vault_recorder_handler(client: Client, message: Message):
        if not message or not message.chat:
            return
        chat_id = message.chat.id
        if global_lockme_enabled.get(client.name, False) or chat_id in locked_chats_per_client.get(client.name, set()):
            store_message_in_vault(client.name, message)

    @app.on_deleted_messages()
    async def anti_delete_restore_handler(client: Client, messages: List[Message]):
        vault = message_vault.get(client.name, {})
        for del_msg in messages:
            record = vault.pop(del_msg.id, None)
            if not record:
                continue
            chat_id = record["chat_id"]
            if not (global_lockme_enabled.get(client.name, False) or chat_id in locked_chats_per_client.get(client.name, set())):
                continue
            restore_body = (
                f"🔒 **[Lockme Anti-Delete — Message Restored]**\n"
                f"• **From:** `{record['sender']}` ({record['date']})\n"
                f"• **Message:** {record['text']}"
            )
            try:
                await client.send_message(chat_id=chat_id, text=restore_body)
                await client.send_message(chat_id="me", text=f"🛡️ **Lockme Backup (`{chat_id}`)**\n{restore_body}")
            except Exception:
                pass

    @app.on_message(filters.me & filters.command("ping", prefixes=COMMAND_PREFIXES))
    async def ping_cmd(client: Client, message: Message):
        start = time.perf_counter()
        await message.edit_text("Pinging...")
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        await message.edit_text(
            f"**PyroFleet Active**\n"
            f"• **Account:** `{client.name}` | **Pool:** `{len(active_clients)}/5`\n"
            f"• **Latency:** `{elapsed_ms} ms` | **Last Purge:** `{last_cache_clear_iso}`"
        )

    @app.on_message(filters.me & filters.command("clearcache", prefixes=COMMAND_PREFIXES))
    async def force_cache_clear_cmd(client: Client, message: Message):
        stats = await clear_caches_and_memory()
        await message.edit_text(f"**Cache Purged** | GC: `{stats['gc_objects']}` | Trimmed: `{stats['malloc_trimmed']}`"
