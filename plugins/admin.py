import os
import sys
import time
import asyncio
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
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
    """Comprehensive admin command handlers with points and premium management"""
    
    # ========================
    # Core Utility Methods
    # ========================

    @staticmethod
    async def _send_response(
        message: Message,
        text: str,
        photo: str = None,
        delete_after: int = None,
        reply_markup=None,
        parse_mode: Optional[enums.ParseMode] = enums.ParseMode.HTML
    ):
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
        except ValueError as e:
            if "Invalid parse mode" in str(e):
                clean_text = re.sub('<[^<]+?>', '', text)
                return await message.reply_text(
                    clean_text,
                    reply_markup=reply_markup,
                    parse_mode=None
                )
            raise
        except Exception as e:
            logger.error(f"Response error: {e}", exc_info=True)
            try:
                return await message.reply_text(
                    "An error occurred while processing this message.",
                    parse_mode=None
                )
            except:
                return None

    @staticmethod
    async def _auto_delete_message(message: Message, delay: int):
        """Auto-delete helper with error handling"""
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Delete failed: {e}")

    @staticmethod
    def _format_uptime():
        """Format bot uptime as human readable string"""
        uptime = datetime.now() - BOT_START_TIME
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m {seconds}s"

    # ========================
    # User Management
    # ========================

    @staticmethod
    async def ban_user(client: Client, message: Message):
        """Ban user with duration and reason"""
        try:
            if len(message.command) < 4:
                return await AdminCommands._send_response(
                    message,
                    "<b>Usage:</b> <code>/ban user_id duration_days reason</code>\n"
                    "<b>Example:</b> <code>/ban 1234567 30 Spamming</code>"
                )

            user_id = int(message.command[1])
            duration = int(message.command[2])
            reason = ' '.join(message.command[3:])

            if not await hyoshcoder.ban_user(user_id, duration, reason):
                return await AdminCommands._send_response(message, "❌ Failed to ban user")

            # Notify user
            try:
                await client.send_message(
                    user_id,
                    f"🚫 <b>You've been banned</b>\n\n"
                    f"⏳ Duration: {duration} days\n"
                    f"📝 Reason: {reason}\n\n"
                    "Contact admin for appeal.",
                    parse_mode=enums.ParseMode.HTML
                )
                notify = "✅ User notified"
            except Exception as e:
                notify = f"⚠️ Notify failed: {e}"

            await AdminCommands._send_response(
                message,
                f"🔨 <b>User Banned</b>\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"⏳ Duration: {duration} days\n"
                f"📝 Reason: {reason}\n"
                f"{notify}"
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Ban error: {str(e)}")
            logger.error(f"Ban error: {e}", exc_info=True)

    @staticmethod
    async def unban_user(client: Client, message: Message):
        """Remove user ban"""
        try:
            if len(message.command) != 2:
                return await AdminCommands._send_response(
                    message,
                    "<b>Usage:</b> <code>/unban user_id</code>\n"
                    "<b>Example:</b> <code>/unban 1234567</code>"
                )

            user_id = int(message.command[1])
            if not await hyoshcoder.remove_ban(user_id):
                return await AdminCommands._send_response(message, "❌ User not banned or failed")

            # Notify user
            try:
                await client.send_message(
                    user_id, 
                    "🎉 Your ban has been lifted!",
                    parse_mode=enums.ParseMode.HTML
                )
                notify = "✅ User notified"
            except Exception as e:
                notify = f"⚠️ Notify failed: {e}"

            await AdminCommands._send_response(
                message,
                f"🔓 <b>User Unbanned</b>\n\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"{notify}"
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Unban error: {str(e)}")
            logger.error(f"Unban error: {e}", exc_info=True)

    # ========================
    # Points Management
    # ========================

    @staticmethod
    async def add_points(client: Client, message: Message):
        """Add points to user balance"""
        try:
            if len(message.command) < 3:
                return await AdminCommands._send_response(
                    message,
                    "<b>Usage:</b> <code>/addpoints user_id amount [reason]</code>\n"
                    "<b>Example:</b> <code>/addpoints 1234567 100 Birthday gift</code>"
                )

            user_id = int(message.command[1])
            amount = int(message.command[2])
            reason = ' '.join(message.command[3:]) or "Admin grant"

            if not await hyoshcoder.add_points(user_id, amount, "admin", reason):
                return await AdminCommands._send_response(message, "❌ Failed to add points")

            new_balance = await hyoshcoder.get_points(user_id)
            await AdminCommands._send_response(
                message,
                f"🪙 <b>Points Added</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"➕ Amount: {amount}\n"
                f"💳 New Balance: {new_balance}\n"
                f"📝 Reason: {reason}"
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Points error: {str(e)}")
            logger.error(f"Add points error: {e}", exc_info=True)

    @staticmethod
    async def generate_points_link(client: Client, message: Message):
        """Create shareable points link"""
        try:
            if len(message.command) < 3:
                return await AdminCommands._send_response(
                    message,
                    "<b>Usage:</b> <code>/genpoints amount max_claims [hours=24] [note]</code>\n"
                    "<b>Example:</b> <code>/genpoints 50 10 48 Welcome bonus</code>"
                )

            points = int(message.command[1])
            max_claims = int(message.command[2])
            hours = int(message.command[3]) if len(message.command) > 3 else 24
            note = ' '.join(message.command[4:]) if len(message.command) > 4 else None

            code, link = await hyoshcoder.create_points_link(
                admin_id=message.from_user.id,
                points=points,
                max_claims=max_claims,
                expires_in_hours=hours,
                note=note
            )

            if not code:
                return await AdminCommands._send_response(message, "❌ Failed to create link")

            await AdminCommands._send_response(
                message,
                f"🔗 <b>Points Link Created</b>\n\n"
                f"🪙 Points: {points}\n"
                f"👥 Max Claims: {max_claims}\n"
                f"⏳ Expires: {hours} hours\n"
                f"📝 Note: {note or 'None'}\n\n"
                f"🔗 Link: {link}\n"
                f"📌 Code: <code>{code}</code>"
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Link error: {str(e)}")
            logger.error(f"Genpoints error: {e}", exc_info=True)

    # ========================
    # Premium Management
    # ========================

    @staticmethod
    async def make_premium(client: Client, message: Message):
        """Grant premium status"""
        try:
            if len(message.command) < 4:
                return await AdminCommands._send_response(
                    message,
                    "<b>Usage:</b> <code>/premium user_id days plan_name</code>\n"
                    "<b>Example:</b> <code>/premium 1234567 30 Gold</code>"
                )

            user_id = int(message.command[1])
            days = int(message.command[2])
            plan = ' '.join(message.command[3:])

            if not await hyoshcoder.activate_premium(user_id, plan, days):
                return await AdminCommands._send_response(message, "❌ Failed to activate premium")

            # Notify user
            try:
                await client.send_message(
                    user_id,
                    f"⭐ <b>You've been upgraded to {plan} Premium!</b>\n\n"
                    f"⏳ Duration: {days} days\n"
                    "Enjoy your exclusive benefits!",
                    parse_mode=enums.ParseMode.HTML
                )
                notify = "✅ User notified"
            except Exception as e:
                notify = f"⚠️ Notify failed: {e}"

            await AdminCommands._send_response(
                message,
                f"🌟 <b>Premium Activated</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"📝 Plan: {plan}\n"
                f"⏳ Duration: {days} days\n"
                f"{notify}"
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Premium error: {str(e)}")
            logger.error(f"Premium error: {e}", exc_info=True)

    # ========================
    # Statistics & Reports
    # ========================

    @staticmethod
    async def bot_stats(client: Client, message: Message):
        """Show comprehensive bot statistics"""
        try:
            # Get all stats in parallel
            stats = await asyncio.gather(
                hyoshcoder.total_users_count(),
                hyoshcoder.total_banned_users_count(),
                hyoshcoder.total_premium_users_count(),
                hyoshcoder.get_daily_active_users(),
                hyoshcoder.total_renamed_files(),
                hyoshcoder.total_points_distributed(),
                hyoshcoder.get_points_links_stats()
            )

            img = await get_random_photo()
            response = (
                "📊 <b>Bot Statistics</b>\n\n"
                f"⏱️ Uptime: {AdminCommands._format_uptime()}\n"
                f"👥 Users: {stats[0]}\n"
                f"🚫 Banned: {stats[1]}\n"
                f"⭐ Premium: {stats[2]}\n"
                f"🔄 Active Today: {stats[3]}\n"
                f"📂 Files Renamed: {stats[4]}\n"
                f"🪙 Points Distributed: {stats[5]}\n\n"
                f"🔗 Points Links:\n"
                f"• Total: {stats[6]['total_links']}\n"
                f"• Active: {stats[6]['active_links']}\n"
                f"• Claimed: {stats[6]['claimed_points']}/{stats[6]['total_points']}"
            )

            await AdminCommands._send_response(
                message,
                response,
                photo=img,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats")]
                ])
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Stats error: {str(e)}")
            logger.error(f"Stats error: {e}", exc_info=True)

    @staticmethod
    async def points_report(client: Client, message: Message):
        """Generate points distribution report"""
        try:
            days = int(message.command[1]) if len(message.command) > 1 else 7
            report = await hyoshcoder.generate_points_report(days)

            response = (
                f"📈 <b>Points Report ({days} days)</b>\n\n"
                f"🪙 Total Distributed: {report['total_points_distributed']}\n\n"
                "📊 Distribution Breakdown:\n"
            )

            for item in report['distribution']:
                response += f"• {item['_id']}: {item['total_points']} pts ({item['count']}x)\n"

            response += "\n🏆 Top Earners:\n"
            for i, user in enumerate(report['top_earners'][:5], 1):
                response += f"{i}. {user.get('username', user['user_id'])}: {user['points']} pts\n"

            await AdminCommands._send_response(message, response)
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Report error: {str(e)}")
            logger.error(f"Report error: {e}", exc_info=True)

    # ========================
    # Admin Panel
    # ========================

    @staticmethod
    async def admin_panel(client: Client, message: Message):
        """Interactive admin control panel"""
        try:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
                    InlineKeyboardButton("🪙 Points", callback_data="admin_points")
                ],
                [
                    InlineKeyboardButton("👤 Users", callback_data="admin_users"),
                    InlineKeyboardButton("⭐ Premium", callback_data="admin_premium")
                ],
                [InlineKeyboardButton("❌ Close", callback_data="close_admin")]
            ])

            await AdminCommands._send_response(
                message,
                "🛠 <b>Admin Control Panel</b>\n\n"
                "Select an option below:",
                reply_markup=keyboard
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Panel error: {str(e)}")
            logger.error(f"Panel error: {e}", exc_info=True)

# ========================
# Command Handlers
# ========================

@Client.on_message(filters.private & filters.command(
    ["admin", "ban", "unban", "addpoints", "premium", "genpoints", "stats", "report"]
) & filters.user(ADMIN_USER_ID))
async def admin_commands_handler(client: Client, message: Message):
    """Main admin command router"""
    try:
        cmd = message.command[0].lower()
        
        if cmd == "admin":
            await AdminCommands.admin_panel(client, message)
        elif cmd == "ban":
            await AdminCommands.ban_user(client, message)
        elif cmd == "unban":
            await AdminCommands.unban_user(client, message)
        elif cmd == "addpoints":
            await AdminCommands.add_points(client, message)
        elif cmd == "premium":
            await AdminCommands.make_premium(client, message)
        elif cmd == "genpoints":
            await AdminCommands.generate_points_link(client, message)
        elif cmd == "stats":
            await AdminCommands.bot_stats(client, message)
        elif cmd == "report":
            await AdminCommands.points_report(client, message)
            
    except Exception as e:
        await message.reply_text(f"❌ Command failed: {str(e)}")
        logger.error(f"Command error: {e}", exc_info=True)

# ========================
# Callback Handlers
# ========================

@Client.on_callback_query(filters.regex(r"^admin_") & filters.user(ADMIN_USER_ID))
async def admin_callbacks(client: Client, callback: CallbackQuery):
    """Handle admin panel callbacks"""
    try:
        action = callback.data.split("_")[1]
        
        if action == "stats":
            await AdminCommands.bot_stats(client, callback.message)
        elif action == "points":
            await callback.message.edit_text(
                "🪙 <b>Points Management</b>\n\n"
                "Available commands:\n"
                "• /addpoints - Grant points\n"
                "• /genpoints - Create link\n"
                "• /report - Points report",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_admin")]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
        elif action == "users":
            await callback.message.edit_text(
                "👤 <b>User Management</b>\n\n"
                "Available commands:\n"
                "• /ban - Ban user\n"
                "• /unban - Unban user",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_admin")]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
        elif action == "premium":
            await callback.message.edit_text(
                "⭐ <b>Premium Management</b>\n\n"
                "Available commands:\n"
                "• /premium - Grant premium",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_admin")]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
            
        await callback.answer()
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")

@Client.on_callback_query(filters.regex(r"^(refresh_stats|close_admin|back_admin)$") & filters.user(ADMIN_USER_ID))
async def misc_callbacks(client: Client, callback: CallbackQuery):
    """Miscellaneous callback handlers"""
    try:
        action = callback.data
        
        if action == "refresh_stats":
            await AdminCommands.bot_stats(client, callback.message)
        elif action == "close_admin":
            await callback.message.delete()
        elif action == "back_admin":
            await AdminCommands.admin_panel(client, callback.message)
            
        await callback.answer()
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")
