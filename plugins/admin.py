import os
import sys
import time
import asyncio
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid, ChatWriteForbidden

from database.data import hyoshcoder
from config import settings
from helpers.utils import get_random_photo
from pyrogram import enums
from typing import Optional
from pyrogram.types import Message

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ADMIN_USER_ID = settings.ADMIN
is_restarting = False

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
            await asyncio.sleep(delete_after)
            await msg.delete()
            
        return msg
        
    except ValueError as e:
        # Fallback if HTML parse mode fails
        if "Invalid parse mode" in str(e):
            clean_text = re.sub('<[^<]+?>', '', text)  # Strip HTML tags
            return await message.reply_text(
                clean_text,
                reply_markup=reply_markup,
                parse_mode=None
            )
        raise
        
    except Exception as e:
        logger.error(f"Response error: {str(e)}")
        # Final fallback to basic text
        await message.reply_text(
            "An error occurred while processing this message.",
            parse_mode=None
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
        except Exception as e:
            logger.warning(f"Delete failed: {e}")

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
                    "**Usage:** `/ban user_id duration_days reason`\n"
                    "**Example:** `/ban 1234567 30 Spamming`"
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
                    f"🚫 **You've been banned**\n\n"
                    f"⏳ Duration: {duration} days\n"
                    f"📝 Reason: {reason}\n\n"
                    "Contact admin for appeal."
                )
                notify = "✅ User notified"
            except Exception as e:
                notify = f"⚠️ Notify failed: {e}"

            await AdminCommands._send_response(
                message,
                f"🔨 **User Banned**\n\n"
                f"🆔 ID: `{user_id}`\n"
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
                    "**Usage:** `/unban user_id`\n"
                    "**Example:** `/unban 1234567`"
                )

            user_id = int(message.command[1])
            if not await hyoshcoder.remove_ban(user_id):
                return await AdminCommands._send_response(message, "❌ User not banned or failed")

            # Notify user
            try:
                await client.send_message(user_id, "🎉 Your ban has been lifted!")
                notify = "✅ User notified"
            except Exception as e:
                notify = f"⚠️ Notify failed: {e}"

            await AdminCommands._send_response(
                message,
                f"🔓 **User Unbanned**\n\n"
                f"🆔 ID: `{user_id}`\n"
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
                    "**Usage:** `/addpoints user_id amount [reason]`\n"
                    "**Example:** `/addpoints 1234567 100 Birthday gift`"
                )

            user_id = int(message.command[1])
            amount = int(message.command[2])
            reason = ' '.join(message.command[3:]) or "Admin grant"

            if not await hyoshcoder.add_points(user_id, amount, "admin", reason):
                return await AdminCommands._send_response(message, "❌ Failed to add points")

            new_balance = await hyoshcoder.get_points(user_id)
            await AdminCommands._send_response(
                message,
                f"🪙 **Points Added**\n\n"
                f"👤 User: `{user_id}`\n"
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
                    "**Usage:** `/genpoints amount max_claims [hours=24] [note]`\n"
                    "**Example:** `/genpoints 50 10 48 Welcome bonus`"
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
                f"🔗 **Points Link Created**\n\n"
                f"🪙 Points: {points}\n"
                f"👥 Max Claims: {max_claims}\n"
                f"⏳ Expires: {hours} hours\n"
                f"📝 Note: {note or 'None'}\n\n"
                f"🔗 Link: {link}\n"
                f"📌 Code: `{code}`"
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
                    "**Usage:** `/premium user_id days plan_name`\n"
                    "**Example:** `/premium 1234567 30 Gold`"
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
                    f"⭐ **You've been upgraded to {plan} Premium!**\n\n"
                    f"⏳ Duration: {days} days\n"
                    "Enjoy your exclusive benefits!"
                )
                notify = "✅ User notified"
            except Exception as e:
                notify = f"⚠️ Notify failed: {e}"

            await AdminCommands._send_response(
                message,
                f"🌟 **Premium Activated**\n\n"
                f"👤 User: `{user_id}`\n"
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
                "📊 **Bot Statistics**\n\n"
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
                f"📈 **Points Report ({days} days)**\n\n"
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
                "🛠 **Admin Control Panel**\n\n"
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
                "🪙 **Points Management**\n\n"
                "Available commands:\n"
                "• /addpoints - Grant points\n"
                "• /genpoints - Create link\n"
                "• /report - Points report",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_admin")]
                ])
            )
        elif action == "users":
            await callback.message.edit_text(
                "👤 **User Management**\n\n"
                "Available commands:\n"
                "• /ban - Ban user\n"
                "• /unban - Unban user",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_admin")]
                ])
            )
        elif action == "premium":
            await callback.message.edit_text(
                "⭐ **Premium Management**\n\n"
                "Available commands:\n"
                "• /premium - Grant premium",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="back_admin")]
                ])
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
