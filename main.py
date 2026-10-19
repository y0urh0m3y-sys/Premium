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

# Ensure a single event loop is set BEFORE importing Pyrogram (Python 3.11+ Render fix)
try:
    MAIN_LOOP = asyncio.get_event_loop()
except RuntimeError:
    MAIN_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(MAIN_LOOP)

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

CACHE_CLEAR_INTERVAL = 3600  # 60 minutes (3600 seconds)
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
    Converts Telethon StringSession strings (353 chars starting with '1',
    such as '1BVts...' or '1AZWar...') into Pyrogram's binary session format.

    CRITICAL ZERO-OTP FIX:
    Pyrogram's `Client.connect()` checks `bool(await self.storage.user_id())`.
    If `user_id` inside the session string is 0, Pyrogram assumes the session
    is unauthorized and asks for a Phone Number + OTP code!
    By packing a non-zero placeholder `user_id = 999999999` during conversion
    and omitting `phone_number` from `Client()`, Pyrogram boots directly from
    the 256-byte `auth_key` without EVER asking for an OTP, and then syncs
    the exact `me.id` via `get_me()`.
    """
    s = (session_str or "").strip()
    if s.startswith("1") and len(s) in (353, 369):
        try:
            body = s[1:]
            raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
            if len(raw) in (263, 275):
                dc_id = raw[0]
                auth_key = raw[-256:]
                placeholder_uid = 999999999  # Non-zero so Pyrogram never prompts for OTP
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
    """Forces glibc on Linux (Render containers) to return freed heap pages to OS."""
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
        return True
    except Exception:
        return False


async def clear_caches_and_memory() -> dict:
    """
    Clears temporary media folders, trims anti-delete vault to bounded size,
    evicts Pyrogram internal message caches, and runs gc.collect + malloc_trim.
    """
    global last_cache_clear_iso
    removed_files = 0
    freed_bytes = 0

    # 1. Remove any downloaded or cached files on disk
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

    # 2. Trim message_vault per client so locked chat backups never exceed RAM budget
    for cname, vault in list(message_vault.items()):
        if len(vault) > 500:
            sorted_ids = sorted(vault.keys())
            for old_id in sorted_ids[:-500]:
                vault.pop(old_id, None)

    # 3. Trim internal Pyrogram client caches
    for app in active_clients:
        if hasattr(app, "message_cache") and app.message_cache:
            try:
                app.message_cache.store.clear()
            except Exception:
                pass

    # 4. Run full multi-generation garbage collection
    collected_objects = gc.collect(2)
    trimmed = release_linux_heap_memory()

    last_cache_clear_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    stats = {
        "timestamp": last_cache_clear_iso,
        "removed_files": removed_files,
        "freed_kb": round(freed_bytes / 1024, 2),
        "gc_objects": collected_objects,
        "malloc_trimmed": trimmed,
    }
    logger.info(
        f"Hourly Cache Purge Complete | GC Objects: {collected_objects} | "
        f"Temp Files Removed: {removed_files} ({stats['freed_kb']} KB) | "
        f"Heap Trimmed: {trimmed}"
    )
    return stats


async def hourly_cache_scheduler():
    """Background loop that clears memory and disk caches every 60 minutes."""
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
    """
    Resolves a target specified as:
      1. Numeric user ID without @ (e.g. 123456789)
      2. @username or username without @ (e.g. @alex or alex)
      3. Profile Name / Display Name (First Name, Last Name, or Full Name)
    """
    target = raw_target.strip()
    if not target:
        return None

    # 1. Numeric User ID (without @)
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

    # 2. Try direct @username or username lookup via get_users
    clean_uname = target.lstrip("@")
    if " " not in clean_uname:
        try:
            user = await app.get_users(clean_uname)
            if user:
                return user.id
        except (UsernameNotOccupied, UsernameInvalid, PeerIdInvalid, RPCError):
            pass
        except Exception:
            pass

    # 3. Profile Name / Display Name Search across Contacts and Recent Dialogs
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
    """
    Parses `*sendpremium` arguments flexibly:
      - `*sendpremium "Profile Name" Your message here`
      - `*sendpremium Profile Name | Your message here`
      - `*sendpremium @username Your message here`
      - `*sendpremium 123456789 Your message here`
      - Or when replying to a message: `*sendpremium <@username / profile name / numeric id>`
    """
    args = raw_args.strip()
    if not args:
        return None, None

    # Format A: Pipe separator -> *sendpremium Profile Name | Message text
    if "|" in args:
        left, right = args.split("|", 1)
        target = left.strip().strip('"').strip("'")
        msg = right.strip() or replied_text
        return target, msg

    # Format B: Quoted profile name -> *sendpremium "First Last" Message text
    quoted_match = re.match(r'^["\']([^"\']+)["\']\s*(.*)$', args, re.DOTALL)
    if quoted_match:
        target = quoted_match.group(1).strip()
        msg = quoted_match.group(2).strip() or replied_text
        return target, msg

    # Format C: Reply mode where entire argument is target (@username, ID, or multi-word Profile Name)
    if replied_text and args:
        parts = args.split(maxsplit=1)
        if len(parts) == 1:
            return parts[0].strip(), replied_text

    # Format D: Standard space-separated -> *sendpremium <target> <message>
    parts = args.split(maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    elif len(parts) == 1 and replied_text:
        return parts[0].strip(), replied_text

    return None, None


# ---------------------------------------------------------------------------
# Multi-Account Smart Delivery for *sendpremium
# ---------------------------------------------------------------------------
async def smart_deliver_message(raw_target: str, text: str, preferred_client: Optional[Client] = None) -> dict:
    """
    Routes message to `raw_target` (@username, profile name, or numeric user ID)
    across all 5 accounts in the pool.
    """
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
            logger.info(f"[{acc_name}] *sendpremium delivered to {raw_target} (peer={peer_to_use})")
            return {
                "success": True,
                "used_account": acc_name,
                "resolved_peer": peer_to_use,
                "message_id": sent.id,
                "attempts": attempt_logs,
            }

        except PremiumAccountRequired:
            reason = f"[{acc_name}] PRIVACY_PREMIUM_REQUIRED on {raw_target}; failing over to next account..."
            logger.warning(reason)
            attempt_logs.append(reason)
            continue

        except UserPrivacyRestricted:
            reason = f"[{acc_name}] UserPrivacyRestricted on {raw_target}; trying next account..."
            logger.warning(reason)
            attempt_logs.append(reason)
            continue

        except FloodWait as fw:
            wait_sec = int(getattr(fw, "value", 5))
            reason = f"[{acc_name}] FloodWait ({wait_sec}s); failing over to next account..."
            logger.warning(reason)
            attempt_logs.append(reason)
            continue

        except (PeerIdInvalid, UsernameNotOccupied, UsernameInvalid) as exc:
            reason = f"[{acc_name}] Could not resolve '{raw_target}' ({type(exc).__name__}); checking next account..."
            logger.warning(reason)
            attempt_logs.append(reason)
            continue

        except (PeerFlood, UserIsBlocked, RPCError) as exc:
            reason = f"[{acc_name}] {type(exc).__name__}; failing over to next account..."
            logger.warning(reason)
            attempt_logs.append(reason)
            continue

        except Exception as err:
            reason = f"[{acc_name}] Unexpected error: {err}"
            logger.error(reason)
            attempt_logs.append(reason)
            continue

    return {
        "success": False,
        "used_account": None,
        "resolved_peer": None,
        "message_id": None,
        "attempts": attempt_logs,
    }


# ---------------------------------------------------------------------------
# Helper to Snapshot Messages for *Lockme Anti-Delete Protection
# ---------------------------------------------------------------------------
def store_message_in_vault(client_name: str, msg: Message):
    if not msg or not msg.chat:
        return
    text_content = msg.text or msg.caption or ""
    if not text_content and msg.media:
        text_content = f"[{msg.media.value.upper()} MEDIA]"
    if not text_content:
        return

    if "🔒 **[Lockme Anti-Delete" in text_content:
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


# ---------------------------------------------------------------------------
# Register Userbot Commands (*sendpremium, *Lockme, *ping, *clearcache)
# ---------------------------------------------------------------------------
def register_handlers(app: Client):
    locked_chats_per_client.setdefault(app.name, set())
    global_lockme_enabled.setdefault(app.name, False)
    message_vault.setdefault(app.name, {})

    # 1. *sendpremium command — Works inside ANY person's DM or chat,
    #    sends the message directly to the specified @username / profile name / numeric user ID!
    @app.on_message(
        filters.me & filters.command(["sendpremium", "route"], prefixes=COMMAND_PREFIXES)
    )
    async def sendpremium_cmd(client: Client, message: Message):
        raw_text = message.text or message.caption or ""
        parts = raw_text.split(maxsplit=1)
        raw_args = parts[1] if len(parts) > 1 else ""
        replied_text = None
        if message.reply_to_message:
            replied_text = message.reply_to_message.text or message.reply_to_message.caption

        target_query, body = parse_sendpremium_args(raw_args, replied_text)

        if not target_query or not body:
            await message.edit_text(
                "**Usage (works in any DM):**\n"
                "• `*sendpremium @username Your message`\n"
                "• `*sendpremium 123456789 Your message`\n"
                "• `*sendpremium \"Profile Name\" Your message`\n"
                "• `*sendpremium Profile Name | Your message`\n"
                "• Or reply to a message with: `*sendpremium @username_or_id_or_name`"
            )
            return

        status_msg = await message.edit_text(
            f"Routing message to `{target_query}` across `{len(active_clients)}` accounts..."
        )
        result = await smart_deliver_message(target_query, body, preferred_client=client)

        if result["success"]:
            await status_msg.edit_text(
                f"✅ **Sent to `{target_query}`** (Peer: `{result['resolved_peer']}`)\n"
                f"• **Via Account:** `{result['used_account']}`\n"
                f"• **Message ID:** `{result['message_id']}`"
            )
            if message.chat and message.chat.type == ChatType.PRIVATE and not message.chat.is_self:
                await asyncio.sleep(4)
                try:
                    await status_msg.delete()
                except Exception:
                    pass
        else:
            log_text = "\n".join(f"- {line}" for line in result["attempts"][-5:])
            await status_msg.edit_text(
                f"❌ **Could not deliver to `{target_query}` on any of the {len(active_clients)} accounts**\n"
                f"**Diagnostics:**\n{log_text}"
            )

    # 2. *Lockme / *unlockme command — Locks DMs and prevents messages from getting deleted by others' userbots
    @app.on_message(
        filters.me & filters.command(["Lockme", "lockme", "unlockme"], prefixes=COMMAND_PREFIXES)
    )
    async def lockme_cmd(client: Client, message: Message):
        cmd_word = (message.command[0] if message.command else "lockme").lower()
        arg = (message.command[1] if message.command and len(message.command) > 1 else "").lower()
        chat_id = message.chat.id

        if cmd_word == "unlockme":
            if arg == "all":
                global_lockme_enabled[client.name] = False
                locked_chats_per_client[client.name].clear()
                await message.edit_text("🔓 **Lockme Disabled** for all DMs on this account.")
            else:
                locked_chats_per_client[client.name].discard(chat_id)
                await message.edit_text(f"🔓 **Chat Unlocked** (`{chat_id}`).")
            return

        if arg == "all":
            global_lockme_enabled[client.name] = True
            await message.edit_text(
                "🔒 **Global Lockme Activated Across All DMs!**\n"
                "Any message deleted by another user or userbot in your DMs will be automatically restored."
            )
            return

        locked_chats_per_client[client.name].add(chat_id)
        await message.edit_text(
            f"🔒 **Locking DM (`{chat_id}`) & Snapshotting History...**"
        )

        snap_count = 0
        try:
            async for old_msg in client.get_chat_history(chat_id, limit=MAX_VAULT_MESSAGES_PER_CHAT):
                store_message_in_vault(client.name, old_msg)
                snap_count += 1
        except Exception as exc:
            logger.warning(f"History snapshot warning on {chat_id}: {exc}")

        await message.edit_text(
            f"🔒 **Lockme Active on this DM (`{chat_id}`)**\n"
            f"• **Protected Messages in Vault:** `{snap_count}`\n"
            f"• **Protection:** If the other user or their userbot deletes any message in this DM, "
            f"it will be immediately restored to this chat and backed up to Saved Messages."
        )

    # 3. Record incoming & outgoing messages in locked DMs into the Anti-Delete Vault
    @app.on_message(filters.private, group=1)
    async def vault_recorder_handler(client: Client, message: Message):
        if not message or not message.chat:
            return
        chat_id = message.chat.id
        is_locked = (
            global_lockme_enabled.get(client.name, False)
            or chat_id in locked_chats_per_client.get(client.name, set())
        )
        if is_locked:
            store_message_in_vault(client.name, message)

    # 4. Intercept Deleted Messages in Locked DMs and Restore Them Immediately
    @app.on_deleted_messages()
    async def anti_delete_restore_handler(client: Client, messages: List[Message]):
        vault = message_vault.get(client.name, {})
        if not vault:
            return

        for del_msg in messages:
            msg_id = del_msg.id
            record = vault.pop(msg_id, None)
            if not record:
                continue

            chat_id = record["chat_id"]
            is_locked = (
                global_lockme_enabled.get(client.name, False)
                or chat_id in locked_chats_per_client.get(client.name, set())
            )
            if not is_locked:
                continue

            restore_body = (
                f"🔒 **[Lockme Anti-Delete — Message Restored]**\n"
                f"• **From:** `{record['sender']}`\n"
                f"• **Time:** `{record['date']}`\n"
                f"• **Content:** {record['text']}"
            )
            try:
                await client.send_message(chat_id=chat_id, text=restore_body)
                await client.send_message(
                    chat_id="me",
                    text=f"🛡️ **Lockme Backup (Chat `{chat_id}`)**\n{restore_body}",
                )
                logger.info(f"[{client.name}] Restored deleted message {msg_id} in locked DM {chat_id}")
            except Exception as exc:
                logger.error(f"[{client.name}] Failed to restore deleted message {msg_id}: {exc}")

    # 5. *ping command
    @app.on_message(filters.me & filters.command("ping", prefixes=COMMAND_PREFIXES))
    async def ping_cmd(client: Client, message: Message):
        start = time.perf_counter()
        await message.edit_text("Pinging fleet...")
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        locked_cnt = len(locked_chats_per_client.get(client.name, set()))
        await message.edit_text(
            f"**PyroFleet Active**\n"
            f"• **Current Account:** `{client.name}`\n"
            f"• **Connected Pool:** `{len(active_clients)} / {len(ACCOUNTS)}` accounts\n"
            f"• **Locked DMs:** `{locked_cnt}` (Global: `{global_lockme_enabled.get(client.name, False)}`)\n"
            f"• **Latency:** `{elapsed_ms} ms`\n"
            f"• **Last Cache Purge:** `{last_cache_clear_iso}`"
        )

    # 6. *clearcache command
    @app.on_message(filters.me & filters.command("clearcache", prefixes=COMMAND_PREFIXES))
    async def force_cache_clear_cmd(client: Client, message: Message):
        await message.edit_text("Purging temporary media, peer caches, and heap memory...")
        stats = await clear_caches_and_memory()
        await message.edit_text(
            f"**Memory & Cache Purge Complete**\n"
            f"• **GC Collected:** `{stats['gc_objects']} objects`\n"
            f"• **Temp Files Deleted:** `{stats['removed_files']} ({stats['freed_kb']} KB)`\n"
            f"• **Linux Heap Trimmed:** `{stats['malloc_trimmed']}`\n"
            f"• **Timestamp:** `{stats['timestamp']}`"
        )


# ---------------------------------------------------------------------------
# Lightweight Render Health-Check Server (Required for Render Web Services)
# ---------------------------------------------------------------------------
async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "ok",
        "active_accounts": len(active_clients),
        "locked_chats_count": sum(len(s) for s in locked_chats_per_client.values()),
        "cache_interval_seconds": CACHE_CLEAR_INTERVAL,
        "last_cache_purge": last_cache_clear_iso,
    })


async def start_health_server() -> web.AppRunner:
    port = int(os.environ.get("PORT", 10000))
    server = web.Application()
    server.router.add_get("/", health_handler)
    server.router.add_get("/health", health_handler)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Render HTTP health server listening on 0.0.0.0:{port}")
    return runner


# ---------------------------------------------------------------------------
# Main Multi-Client Orchestrator (Zero-OTP Session Boot + Render Port Binding)
# ---------------------------------------------------------------------------
async def main():
    logger.info("Starting PyroFleet 5-Account Orchestrator (Zero-OTP Session Mode)...")
    # Bind Render $PORT immediately so Render marks Web Service live without timeout
    health_runner = await start_health_server()
    await clear_caches_and_memory()

    for cfg in ACCOUNTS:
        if not cfg["session_string"]:
            logger.warning(f"Skipping {cfg['name']}: Missing SESSION_STRING.")
            continue

        # Convert 1BVts.../1AZWar... session string with non-zero user_id placeholder
        # and DO NOT pass phone_number to Client() so Pyrogram NEVER prompts for an OTP.
        normalized_session = normalize_session_string(cfg["session_string"], cfg["api_id"])

        client = Client(
            name=f"acc_{cfg['index']}",
            api_id=cfg["api_id"],
            api_hash=cfg["api_hash"],
            session_string=normalized_session,
            in_memory=True,
            no_updates=False,
            sleep_threshold=30,
        )
        register_handlers(client)
        try:
            await client.start()
            me = await client.get_me()
            await client.storage.user_id(me.id)
            setattr(client, "is_premium_account", bool(getattr(me, "is_premium", False)))
            premium_tag = "Premium" if getattr(me, "is_premium", False) else "Standard"
            logger.info(
                f"Started {cfg['name']} ({cfg['phone_number']}) -> @{me.username or me.id} ({premium_tag}) [No OTP]"
            )
            active_clients.append(client)
        except Exception as exc:
            logger.error(f"Failed to start {cfg['name']} ({cfg['phone_number']}): {exc}")

    if not active_clients:
        logger.error("No valid accounts started. Check your session strings.")
    else:
        logger.info(f"All {len(active_clients)} active accounts online and listening for *sendpremium and *Lockme.")

    # Start 1-hour automatic cache & memory cleaner
    cache_task = asyncio.create_task(hourly_cache_scheduler())

    try:
        await idle()
    finally:
        cache_task.cancel()
        await health_runner.cleanup()
        for client in active_clients:
            try:
                await client.stop()
            except Exception:
                pass


if __name__ == "__main__":
    MAIN_LOOP.run_until_complete(main())
