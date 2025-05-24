import os
import sys
import time
import asyncio
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import re
import html

from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid, ChatWriteForbidden

from database.data import hyoshcoder
from config import settings
from helpers.utils import get_random_photo

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ADMIN_USER_ID = settings.ADMIN
BOT_START_TIME = datetime.now()

class AdminCommands:
    """Comprehensive admin command handlers with all management features"""
    
    # ========================
    # Core Utility Methods
    # ========================

    @staticmethod
    def _format_uptime() -> str:
        """Format bot uptime into human-readable string"""
        uptime = datetime.now() - BOT_START_TIME
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"

    @staticmethod
    async def _send_response(
        message: Message,
        text: str,
        photo: str = None,
        delete_after: int = None,
        reply_markup=None,
        parse_mode: Optional[enums.ParseMode] = enums.ParseMode.HTML
    ) -> Optional[Message]:
        """Smart response sender with auto-delete and media support"""
        try:
            if photo:
                msg = await message.reply_photo(
                    photo=photo,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            else:
                msg = await message.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            
            if delete_after:
                asyncio.create_task(AdminCommands._auto_delete_message(msg, delete_after))
            return msg
        except Exception as e:
            logger.error(f"Response error: {e}", exc_info=True)
            return None

    @staticmethod
    async def _auto_delete_message(message: Message, delay: int):
        """Auto-delete helper with error handling"""
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception:
            pass

    @staticmethod
    def _parse_duration(duration_str: str) -> timedelta:
        """Parse duration string into timedelta"""
        try:
            num = int(duration_str[:-1])
            if duration_str.endswith('m'):
                return timedelta(minutes=num)
            elif duration_str.endswith('h'):
                return timedelta(hours=num)
            elif duration_str.endswith('d'):
                return timedelta(days=num)
        except:
            return timedelta(hours=1)

    @staticmethod
    def _format_timedelta(delta: timedelta) -> str:
        """Format timedelta into human-readable string"""
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"

    # ========================
    # Points System Configuration
    # ========================

    @staticmethod
    async def setup_points_config() -> Dict[str, Any]:
        """Initialize points config if not exists"""
        default_config = {
            "per_rename": 2,
            "new_user_bonus": 70,
            "referral_bonus": 10,
            "daily_cap": 100,
            "premium_multiplier": 2,
            "ad_watch": {
                "min_points": 5,
                "max_points": 20,
                "cooldown": 3600,
                "daily_limit": 5
            }
        }
        
        if not await hyoshcoder.get_config("points_config"):
            await hyoshcoder.db.config.update_one(
                {"key": "points_config"},
                {"$set": {"value": default_config}},
                upsert=True
            )
        return default_config

    @staticmethod
    async def config_points_system(client: Client, message: Message):
        """Configure points system settings"""
        try:
            config = await AdminCommands.setup_points_config()
            
            if len(message.command) < 3:
                response = (
                    "🛠 <b>Points Configuration</b>\n\n"
                    f"• Per Rename: {config['per_rename']}\n"
                    f"• New User Bonus: {config['new_user_bonus']}\n"
                    f"• Referral Bonus: {config['referral_bonus']}\n"
                    f"• Daily Cap: {config['daily_cap']}\n"
                    f"• Premium Multiplier: {config['premium_multiplier']}x\n\n"
                    "<b>Usage:</b> <code>/pointconfig setting value</code>\n"
                    "<b>Example:</b> <code>/pointconfig per_rename 5</code>"
                )
                return await AdminCommands._send_response(message, response)

            setting = message.command[1]
            value = message.command[2]

            if setting not in config or (setting == "ad_watch" and len(message.command) < 4):
                return await AdminCommands._send_response(message, "❌ Invalid setting")

            try:
                if setting == "ad_watch":
                    sub_setting = message.command[2]
                    value = message.command[3]
                    config[setting][sub_setting] = int(value)
                else:
                    config[setting] = int(value) if setting != "premium_multiplier" else float(value)
            except ValueError:
                return await AdminCommands._send_response(message, "❌ Invalid value")

            await hyoshcoder.db.config.update_one(
                {"key": "points_config"},
                {"$set": {"value": config}},
                upsert=True
            )

            await AdminCommands._send_response(
                message,
                f"✅ Updated {setting} to {value}",
                delete_after=10
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Error: {str(e)}")
            logger.error(f"Config error: {e}", exc_info=True)

    # ========================
    # Points Link Generation
    # ========================

    @staticmethod
    async def generate_points_link(client: Client, message: Message):
        """Generate shareable points links"""
        try:
            if len(message.command) < 4:
                return await AdminCommands._send_response(
                    message,
                    "🔗 <b>Generate Points Link</b>\n\n"
                    "<b>Usage:</b> <code>/genlink points uses expires</code>\n"
                    "<b>Example:</b> <code>/genlink 50 10 24h</code>\n\n"
                    "<b>Expires formats:</b> 24h, 7d, 30m"
                )

            points = int(message.command[1])
            max_uses = int(message.command[2])
            expires_in = message.command[3]

            expires_delta = AdminCommands._parse_duration(expires_in)
            expires_at = datetime.now() + expires_delta

            code = secrets.token_urlsafe(8)
            link = f"https://t.me/{(await client.get_me()).username}?start=points_{code}"

            await hyoshcoder.point_links.insert_one({
                "code": code,
                "points": points,
                "max_uses": max_uses,
                "uses_left": max_uses,
                "expires_at": expires_at,
                "created_by": message.from_user.id,
                "created_at": datetime.now()
            })

            await AdminCommands._send_response(
                message,
                f"🔗 <b>Points Link Created</b>\n\n"
                f"🪙 Points: {points}\n"
                f"🔢 Uses: {max_uses}\n"
                f"⏳ Expires: {expires_in}\n\n"
                f"📌 Code: <code>{code}</code>\n"
                f"🔗 Link: {link}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 Delete", callback_data=f"del_link_{code}")]
                ])
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Error: {str(e)}")
            logger.error(f"Link gen error: {e}", exc_info=True)

    # ========================
    # User Points Management
    # ========================

    @staticmethod
    async def manage_user_points(client: Client, message: Message):
        """Manage user points"""
        try:
            if len(message.command) < 4:
                return await AdminCommands._send_response(
                    message,
                    "👤 <b>Manage User Points</b>\n\n"
                    "<b>Usage:</b> <code>/userpoints user_id action amount</code>\n"
                    "<b>Actions:</b> add, deduct, set\n"
                    "<b>Example:</b> <code>/userpoints 123456 add 50</code>"
                )

            user_id = int(message.command[1])
            action = message.command[2].lower()
            amount = int(message.command[3])

            user = await hyoshcoder.get_user(user_id)
            if not user:
                return await AdminCommands._send_response(message, "❌ User not found")

            if action == "add":
                await hyoshcoder.add_points(user_id, amount, "admin")
                new_balance = user["points"]["balance"] + amount
            elif action == "deduct":
                if user["points"]["balance"] < amount:
                    return await AdminCommands._send_response(message, "❌ Not enough points")
                await hyoshcoder.deduct_points(user_id, amount, "admin")
                new_balance = user["points"]["balance"] - amount
            elif action == "set":
                await hyoshcoder.users.update_one(
                    {"_id": user_id},
                    {"$set": {"points.balance": amount}}
                )
                new_balance = amount
            else:
                return await AdminCommands._send_response(message, "❌ Invalid action")

            await AdminCommands._send_response(
                message,
                f"✅ Updated user {user_id}\n"
                f"🪙 New balance: {new_balance}",
                delete_after=10
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Error: {str(e)}")
            logger.error(f"Points error: {e}", exc_info=True)

    # ========================
    # Premium Management
    # ========================

    @staticmethod
    async def manage_premium(client: Client, message: Message):
        """Manage premium subscriptions"""
        try:
            if len(message.command) < 3:
                return await AdminCommands._send_response(
                    message,
                    "🌟 <b>Premium Management</b>\n\n"
                    "<b>Usage:</b> <code>/premium user_id action [duration]</code>\n"
                    "<b>Actions:</b> activate, deactivate, check\n"
                    "<b>Example:</b> <code>/premium 123456 activate 7d</code>"
                )

            user_id = int(message.command[1])
            action = message.command[2].lower()

            if action == "check":
                status = await hyoshcoder.check_premium_status(user_id)
                response = (
                    f"🌟 <b>Premium Status for {user_id}</b>\n\n"
                    f"Status: {'✅ Active' if status['is_premium'] else '❌ Inactive'}\n"
                    f"Valid Until: {status.get('until', 'N/A')}"
                )
                return await AdminCommands._send_response(message, response)

            elif action == "activate":
                if len(message.command) < 4:
                    return await AdminCommands._send_response(message, "❌ Missing duration")
                
                duration = AdminCommands._parse_duration(message.command[3])
                success = await hyoshcoder.activate_premium(
                    user_id=user_id,
                    duration_days=duration.days
                )
                
                if not success:
                    return await AdminCommands._send_response(message, "❌ Failed to activate premium")
                
                return await AdminCommands._send_response(
                    message,
                    f"✅ Activated premium for {user_id}\n"
                    f"⏳ Duration: {AdminCommands._format_timedelta(duration)}"
                )

            elif action == "deactivate":
                success = await hyoshcoder.deactivate_premium(user_id)
                if not success:
                    return await AdminCommands._send_response(message, "❌ Failed to deactivate premium")
                return await AdminCommands._send_response(message, f"✅ Deactivated premium for {user_id}")

            else:
                return await AdminCommands._send_response(message, "❌ Invalid action")

        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Error: {str(e)}")
            logger.error(f"Premium error: {e}", exc_info=True)

    # ========================
    # Bot Statistics
    # ========================

    @staticmethod
    async def bot_stats(client: Client, message: Message):
        """Show bot statistics"""
        try:
            stats = await asyncio.gather(
                hyoshcoder.total_users_count(),
                hyoshcoder.total_premium_users_count(),
                hyoshcoder.total_renamed_files(),
                hyoshcoder.total_points_distributed()
            )

            response = (
                "📊 <b>Bot Statistics</b>\n\n"
                f"⏱ Uptime: {AdminCommands._format_uptime()}\n"
                f"👥 Users: {stats[0]}\n"
                f"⭐ Premium: {stats[1]}\n"
                f"📂 Files Renamed: {stats[2]}\n"
                f"🪙 Points Distributed: {stats[3]}"
            )

            await AdminCommands._send_response(message, response)
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Error: {str(e)}")
            logger.error(f"Stats error: {e}", exc_info=True)

    # ========================
    # User Ban Management
    # ========================

    @staticmethod
    async def ban_user(client: Client, message: Message):
        """Ban a user"""
        try:
            if len(message.command) < 2:
                return await AdminCommands._send_response(
                    message,
                    "🚫 <b>Ban User</b>\n\n"
                    "<b>Usage:</b> <code>/ban user_id [reason]</code>\n"
                    "<b>Example:</b> <code>/ban 123456 Spamming</code>"
                )

            user_id = int(message.command[1])
            reason = ' '.join(message.command[2:]) or "No reason provided"

            success = await hyoshcoder.ban_user(user_id, reason)
            if not success:
                return await AdminCommands._send_response(message, "❌ Failed to ban user")

            await AdminCommands._send_response(
                message,
                f"✅ Banned user {user_id}\n"
                f"📝 Reason: {reason}",
                delete_after=15
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Error: {str(e)}")
            logger.error(f"Ban error: {e}", exc_info=True)

    @staticmethod
    async def unban_user(client: Client, message: Message):
        """Unban a user"""
        try:
            if len(message.command) < 2:
                return await AdminCommands._send_response(
                    message,
                    "✅ <b>Unban User</b>\n\n"
                    "<b>Usage:</b> <code>/unban user_id</code>\n"
                    "<b>Example:</b> <code>/unban 123456</code>"
                )

            user_id = int(message.command[1])
            success = await hyoshcoder.unban_user(user_id)
            if not success:
                return await AdminCommands._send_response(message, "❌ Failed to unban user")

            await AdminCommands._send_response(
                message,
                f"✅ Unbanned user {user_id}",
                delete_after=15
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Error: {str(e)}")
            logger.error(f"Unban error: {e}", exc_info=True)

    # ========================
    # Admin Panel
    # ========================

    @staticmethod
    async def admin_panel(client: Client, message: Message):
        """Show admin panel"""
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛠 Points Config", callback_data="points_config")],
            [InlineKeyboardButton("🔗 Generate Link", callback_data="gen_link")],
            [InlineKeyboardButton("👤 Manage Users", callback_data="user_manage")],
            [InlineKeyboardButton("🌟 Premium", callback_data="premium_manage")],
            [InlineKeyboardButton("📊 Stats", callback_data="bot_stats")]
        ])
        await AdminCommands._send_response(
            message,
            "👨‍💼 <b>Admin Panel</b>\n\n"
            "Select an option below:",
            reply_markup=buttons
        )

# Command handlers
@Client.on_message(filters.private & filters.command(["admin", "pointconfig", "genlink", "userpoints", "premium", "stats", "ban", "unban"]) & filters.user(ADMIN_USER_ID))
async def admin_commands_handler(client: Client, message: Message):
    try:
        cmd = message.command[0].lower()
        
        if cmd == "admin":
            await AdminCommands.admin_panel(client, message)
        elif cmd == "pointconfig":
            await AdminCommands.config_points_system(client, message)
        elif cmd == "genlink":
            await AdminCommands.generate_points_link(client, message)
        elif cmd == "userpoints":
            await AdminCommands.manage_user_points(client, message)
        elif cmd == "premium":
            await AdminCommands.manage_premium(client, message)
        elif cmd == "stats":
            await AdminCommands.bot_stats(client, message)
        elif cmd == "ban":
            await AdminCommands.ban_user(client, message)
        elif cmd == "unban":
            await AdminCommands.unban_user(client, message)
    except Exception as e:
        logger.error(f"Command error: {e}", exc_info=True)

# Callback handlers
@Client.on_callback_query(filters.user(ADMIN_USER_ID))
async def admin_callbacks(client: Client, callback: CallbackQuery):
    try:
        data = callback.data
        
        if data == "points_config":
            await AdminCommands.config_points_system(client, callback.message)
        elif data == "gen_link":
            await AdminCommands.generate_points_link(client, callback.message)
        elif data == "user_manage":
            await callback.message.edit_text(
                "👤 <b>User Management</b>\n\n"
                "Commands:\n"
                "<code>/ban user_id [reason]</code>\n"
                "<code>/unban user_id</code>\n"
                "<code>/userpoints user_id action amount</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
                ])
            )
        elif data == "premium_manage":
            await callback.message.edit_text(
                "🌟 <b>Premium Management</b>\n\n"
                "Commands:\n"
                "<code>/premium user_id activate duration</code>\n"
                "<code>/premium user_id deactivate</code>\n"
                "<code>/premium user_id check</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
                ])
            )
        elif data == "bot_stats":
            await AdminCommands.bot_stats(client, callback.message)
        elif data.startswith("del_link_"):
            code = data.split("_")[2]
            await hyoshcoder.point_links.delete_one({"code": code})
            await callback.answer("Link deleted")
            await callback.message.delete()
        elif data == "admin_panel":
            await AdminCommands.admin_panel(client, callback.message)
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")
