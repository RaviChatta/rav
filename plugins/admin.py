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
        
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
            
        return " ".join(parts) if parts else "Just started"

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
    def _parse_duration(duration_str: str) -> timedelta:
        """Parse duration string (e.g., 30m, 2h, 7d) into timedelta"""
        try:
            if duration_str.endswith('m'):
                return timedelta(minutes=int(duration_str[:-1]))
            elif duration_str.endswith('h'):
                return timedelta(hours=int(duration_str[:-1]))
            elif duration_str.endswith('d'):
                return timedelta(days=int(duration_str[:-1]))
            else:
                return timedelta(hours=1)  # Default to 1 hour if format is invalid
        except:
            return timedelta(hours=1)

    @staticmethod
    def _format_timedelta(delta: timedelta) -> str:
        """Format timedelta into human-readable string"""
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
            
        return " ".join(parts) if parts else "Less than 1 minute"

    # ========================
    # Points System Configuration
    # ========================

    @staticmethod
    async def setup_points_config():
        """Initialize points config if not exists"""
        default_config = {
            "per_rename": 2,
            "new_user_bonus": 70,
            "referral_bonus": 10,
            "daily_cap": 100,
            "premium_multiplier": 2,
            "premium_unlimited_renames": True,
            "ad_watch": {
                "min_points": 5,
                "max_points": 20,
                "cooldown": 3600,  # 1 hour in seconds
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
        """Configure all points-related settings"""
        try:
            config = await AdminCommands.setup_points_config()
            
            if len(message.command) < 3:
                # Show current configuration
                response = (
                    "🪙 <b>Points System Configuration</b>\n\n"
                    "📝 <b>Basic Settings:</b>\n"
                    f"• Per Rename: {config['per_rename']} points\n"
                    f"• New User Bonus: {config['new_user_bonus']} points\n"
                    f"• Referral Bonus: {config['referral_bonus']} points\n"
                    f"• Daily Cap: {config['daily_cap']} points\n"
                    f"• Premium Multiplier: {config['premium_multiplier']}x\n"
                    f"• Premium Unlimited Renames: {'✅' if config['premium_unlimited_renames'] else '❌'}\n\n"
                    "📺 <b>Ad Watch Rewards:</b>\n"
                    f"• Min: {config['ad_watch']['min_points']} points\n"
                    f"• Max: {config['ad_watch']['max_points']} points\n"
                    f"• Cooldown: {config['ad_watch']['cooldown']//3600} hours\n"
                    f"• Daily Limit: {config['ad_watch']['daily_limit']} watches\n\n"
                    "<b>Usage:</b> <code>/pointconfig section.setting value</code>\n"
                    "<b>Examples:</b>\n"
                    "<code>/pointconfig basic.per_rename 3</code>\n"
                    "<code>/pointconfig ad_watch.min_points 10</code>\n"
                    "<code>/pointconfig basic.premium_unlimited_renames true</code>"
                )
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Reset Defaults", callback_data="reset_points_config")],
                    [InlineKeyboardButton("❌ Close", callback_data="close_admin")]
                ])
                
                return await AdminCommands._send_response(message, response, reply_markup=buttons)

            # Parse command
            try:
                section_setting = message.command[1]
                value = message.command[2]
                
                if '.' in section_setting:
                    section, setting = section_setting.split('.')
                else:
                    section = "basic"
                    setting = section_setting
            except:
                return await AdminCommands._send_response(
                    message,
                    "❌ Invalid format. Use: <code>/pointconfig section.setting value</code>"
                )

            # Validate section
            valid_sections = ["basic", "ad_watch"]
            if section not in valid_sections:
                return await AdminCommands._send_response(
                    message,
                    f"❌ Invalid section. Available: {', '.join(valid_sections)}"
                )

            # Validate and convert value
            try:
                if section == "basic":
                    if setting in ["per_rename", "new_user_bonus", "referral_bonus", "daily_cap"]:
                        value = int(value)
                        if value <= 0:
                            raise ValueError("Must be positive")
                    elif setting == "premium_multiplier":
                        value = float(value)
                        if value < 1:
                            raise ValueError("Must be ≥ 1")
                    elif setting == "premium_unlimited_renames":
                        value = value.lower() in ["true", "yes", "1"]
                    else:
                        return await AdminCommands._send_response(
                            message,
                            f"❌ Invalid setting for basic config. Available: per_rename, new_user_bonus, referral_bonus, daily_cap, premium_multiplier, premium_unlimited_renames"
                        )
                
                elif section == "ad_watch":
                    if setting in ["min_points", "max_points"]:
                        value = int(value)
                        if value <= 0:
                            raise ValueError("Must be positive")
                    elif setting == "cooldown":
                        value = int(value)
                        if value < 300:
                            return await AdminCommands._send_response(
                                message,
                                "❌ Cooldown must be at least 300 seconds (5 minutes)"
                            )
                    elif setting == "daily_limit":
                        value = int(value)
                        if value <= 0:
                            raise ValueError("Must be positive")
                    else:
                        return await AdminCommands._send_response(
                            message,
                            f"❌ Invalid setting for ad_watch. Available: min_points, max_points, cooldown, daily_limit"
                        )
            except ValueError:
                return await AdminCommands._send_response(
                    message,
                    "❌ Invalid value. Use integers for most settings, float for multipliers, true/false for toggles"
                )

            # Update configuration
            if section == "basic":
                config[setting] = value
            else:
                config["ad_watch"][setting] = value

            await hyoshcoder.db.config.update_one(
                {"key": "points_config"},
                {"$set": {"value": config}},
                upsert=True
            )

            # Special handling for new user bonus changes
            if section == "basic" and setting == "new_user_bonus":
                await hyoshcoder.users.update_many(
                    {},
                    [{
                        "$set": {
                            "points.balance": value,
                            "points.total_earned": value
                        }
                    }]
                )

            await AdminCommands._send_response(
                message,
                f"✅ Points configuration updated!\n\n"
                f"<b>{section}.{setting}</b> set to <code>{value}</code>",
                delete_after=15
            )

        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Configuration error: {str(e)}")
            logger.error(f"Points config error: {e}", exc_info=True)

    # ========================
    # User Points Management
    # ========================

    @staticmethod
    async def manage_user_points(client: Client, message: Message):
        """Manage points for specific users"""
        try:
            if len(message.command) < 4:
                return await AdminCommands._send_response(
                    message,
                    "👤 <b>User Points Management</b>\n\n"
                    "<b>Usage:</b> <code>/userpoints user_id action amount [reason]</code>\n"
                    "<b>Actions:</b> add, deduct, set\n"
                    "<b>Examples:</b>\n"
                    "<code>/userpoints 1234567 add 50 Bonus</code>\n"
                    "<code>/userpoints 1234567 deduct 30 Refund</code>\n"
                    "<code>/userpoints 1234567 set 100 Reset</code>",
                    delete_after=30
                )

            user_id = int(message.command[1])
            action = message.command[2].lower()
            amount = int(message.command[3])
            reason = ' '.join(message.command[4:]) or "Admin action"

            if action not in ["add", "deduct", "set"]:
                return await AdminCommands._send_response(
                    message,
                    "❌ Invalid action. Use: add, deduct, or set",
                    delete_after=10
                )

            user = await hyoshcoder.read_user(user_id)
            if not user:
                return await AdminCommands._send_response(message, "❌ User not found", delete_after=10)

            if action == "add":
                success = await hyoshcoder.add_points(user_id, amount, "admin", reason)
                new_balance = user["points"]["balance"] + amount
            elif action == "deduct":
                if user["points"]["balance"] < amount:
                    return await AdminCommands._send_response(
                        message,
                        f"❌ User only has {user['points']['balance']} points (trying to deduct {amount})",
                        delete_after=10
                    )
                success = await hyoshcoder.deduct_points(user_id, amount, reason)
                new_balance = user["points"]["balance"] - amount
            else:  # set
                current = user["points"]["balance"]
                difference = amount - current
                if difference > 0:
                    success = await hyoshcoder.add_points(user_id, difference, "admin", reason)
                else:
                    success = await hyoshcoder.deduct_points(user_id, abs(difference), reason)
                new_balance = amount

            if not success:
                return await AdminCommands._send_response(message, "❌ Failed to update points", delete_after=10)

            await AdminCommands._send_response(
                message,
                f"✅ <b>User Points Updated</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"📝 Action: {action.title()}\n"
                f"🪙 Amount: {amount}\n"
                f"💳 New Balance: {new_balance}\n"
                f"📝 Reason: {reason}",
                delete_after=15
            )

        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Points management error: {str(e)}", delete_after=10)
            logger.error(f"User points error: {e}", exc_info=True)

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
                    "🔗 <b>Points Link Generator</b>\n\n"
                    "<b>Usage:</b> <code>/genlink points max_uses expires_in [note]</code>\n"
                    "<b>Examples:</b>\n"
                    "<code>/genlink 50 10 24h Welcome bonus</code>\n"
                    "<code>/genlink 100 1 7d Special reward</code>\n\n"
                    "<b>Expiration formats:</b>\n"
                    "• 24h (24 hours)\n• 7d (7 days)\n• 30m (30 minutes)",
                    delete_after=30
                )

            points = int(message.command[1])
            max_uses = int(message.command[2])
            expires_in = message.command[3]
            note = ' '.join(message.command[4:]) if len(message.command) > 4 else None

            # Parse expiration time
            expires_delta = AdminCommands._parse_duration(expires_in)
            expires_at = datetime.now() + expires_delta

            # Generate link
            code, link = await hyoshcoder.create_points_link(
                admin_id=message.from_user.id,
                points=points,
                max_claims=max_uses,
                expires_at=expires_at,
                note=note
            )

            if not code:
                raise Exception("Failed to generate link")

            await AdminCommands._send_response(
                message,
                f"🔗 <b>Points Link Created</b>\n\n"
                f"🪙 Points: {points}\n"
                f"👥 Max Uses: {max_uses}\n"
                f"⏳ Expires: {expires_in} ({expires_at.strftime('%Y-%m-%d %H:%M')})\n"
                f"📝 Note: {note or 'None'}\n\n"
                f"🔗 Link: {link}\n"
                f"📌 Code: <code>{code}</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Copy Link", callback_data=f"copy_link_{code}")],
                    [InlineKeyboardButton("🗑 Delete Link", callback_data=f"delete_link_{code}")]
                ]),
                delete_after=60
            )

        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Link generation error: {str(e)}", delete_after=10)
            logger.error(f"Link generation error: {e}", exc_info=True)

    # ========================
    # Premium Management
    # ========================

    @staticmethod
    async def manage_premium(client: Client, message: Message):
        """Manage premium subscriptions for users"""
        try:
            if len(message.command) < 3:
                return await AdminCommands._send_response(
                    message,
                    "🌟 <b>Premium User Management</b>\n\n"
                    "<b>Usage:</b> <code>/premium user_id action duration</code>\n\n"
                    "<b>Actions:</b>\n"
                    "• <code>activate</code> - Grant premium\n"
                    "• <code>deactivate</code> - Remove premium\n"
                    "• <code>check</code> - View status\n\n"
                    "<b>Duration formats:</b>\n"
                    "• 30m (30 minutes)\n• 2h (2 hours)\n• 7d (7 days)\n\n"
                    "<b>Examples:</b>\n"
                    "<code>/premium 1234567 activate 30d</code>\n"
                    "<code>/premium 1234567 deactivate</code>\n"
                    "<code>/premium 1234567 check</code>",
                    delete_after=30
                )

            user_id = int(message.command[1])
            action = message.command[2].lower()
            
            if action == "check":
                status = await hyoshcoder.check_premium_status(user_id)
                if status.get("is_premium"):
                    until = datetime.fromisoformat(status["until"]).strftime("%Y-%m-%d %H:%M")
                    response = (
                        f"🌟 <b>Premium Status for {user_id}</b>\n\n"
                        f"✅ <b>Active Subscription</b>\n"
                        f"⏳ Valid Until: {until}\n"
                        f"⏱ Time Left: {AdminCommands._format_timedelta(datetime.fromisoformat(status['until']) - datetime.now())}\n"
                        f"✨ Benefits: Unlimited renames"
                    )
                else:
                    response = (
                        f"🌟 <b>Premium Status for {user_id}</b>\n\n"
                        f"❌ <b>No Active Subscription</b>\n"
                        f"📝 Reason: {status.get('reason', 'Unknown')}"
                    )
                return await AdminCommands._send_response(message, response, delete_after=15)

            elif action == "activate":
                if len(message.command) < 4:
                    return await AdminCommands._send_response(
                        message,
                        "❌ Missing duration. Usage: <code>/premium user_id activate duration</code>",
                        delete_after=10
                    )
                
                duration = AdminCommands._parse_duration(message.command[3])
                success = await hyoshcoder.activate_premium(
                    user_id=user_id,
                    duration_days=int(duration.total_seconds() / 86400)
                )
                
                if not success:
                    return await AdminCommands._send_response(message, "❌ Failed to activate premium", delete_after=10)
                
                until = (datetime.now() + duration).strftime("%Y-%m-%d %H:%M")
                return await AdminCommands._send_response(
                    message,
                    f"✅ <b>Premium Activated</b>\n\n"
                    f"👤 User: <code>{user_id}</code>\n"
                    f"⏳ Duration: {AdminCommands._format_timedelta(duration)}\n"
                    f"📅 Valid Until: {until}\n"
                    f"✨ Benefits: Unlimited renames",
                    delete_after=15
                )

            elif action == "deactivate":
                success = await hyoshcoder.deactivate_premium(user_id)
                if not success:
                    return await AdminCommands._send_response(message, "❌ Failed to deactivate premium", delete_after=10)
                
                return await AdminCommands._send_response(
                    message,
                    f"✅ <b>Premium Deactivated</b>\n\n"
                    f"👤 User: <code>{user_id}</code>\n"
                    f"❌ Subscription removed",
                    delete_after=15
                )

            else:
                return await AdminCommands._send_response(
                    message,
                    "❌ Invalid action. Use: activate, deactivate, or check",
                    delete_after=10
                )

        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Premium management error: {str(e)}", delete_after=10)
            logger.error(f"Premium management error: {e}", exc_info=True)

    # ========================
    # Bot Statistics
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

    # ========================
    # Points Reports
    # ========================

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
                f"• Renames: {report['rename_points']} points\n"
                f"• Referrals: {report['referral_points']} points\n"
                f"• Admin Grants: {report['admin_points']} points\n"
                f"• Ad Rewards: {report['ad_points']} points\n"
                f"• Link Claims: {report['link_points']} points\n\n"
                f"👥 Active Users: {report['active_users']}\n"
                f"🆕 New Users: {report['new_users']}"
            )

            await AdminCommands._send_response(
                message,
                response,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 7 Days", callback_data="points_report_7"),
                    InlineKeyboardButton("📈 30 Days", callback_data="points_report_30")]
                ])
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Report error: {str(e)}")
            logger.error(f"Points report error: {e}", exc_info=True)

    # ========================
    # User Ban Management
    # ========================

    @staticmethod
    async def ban_user(client: Client, message: Message):
        """Ban a user from using the bot"""
        try:
            if len(message.command) < 2:
                return await AdminCommands._send_response(
                    message,
                    "🚫 <b>Ban User</b>\n\n"
                    "<b>Usage:</b> <code>/ban user_id [reason]</code>\n"
                    "<b>Example:</b>\n"
                    "<code>/ban 1234567 Spamming</code>",
                    delete_after=30
                )

            user_id = int(message.command[1])
            reason = ' '.join(message.command[2:]) or "No reason provided"

            if user_id == ADMIN_USER_ID:
                return await AdminCommands._send_response(message, "❌ You can't ban yourself!", delete_after=10)

            success = await hyoshcoder.ban_user(user_id, reason)
            if not success:
                return await AdminCommands._send_response(message, "❌ Failed to ban user", delete_after=10)

            await AdminCommands._send_response(
                message,
                f"✅ <b>User Banned</b>\n\n"
                f"👤 User ID: <code>{user_id}</code>\n"
                f"📝 Reason: {reason}",
                delete_after=15
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Ban error: {str(e)}", delete_after=10)
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
                    "<b>Example:</b>\n"
                    "<code>/unban 1234567</code>",
                    delete_after=30
                )

            user_id = int(message.command[1])
            success = await hyoshcoder.unban_user(user_id)
            if not success:
                return await AdminCommands._send_response(message, "❌ Failed to unban user", delete_after=10)

            await AdminCommands._send_response(
                message,
                f"✅ <b>User Unbanned</b>\n\n"
                f"👤 User ID: <code>{user_id}</code>",
                delete_after=15
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Unban error: {str(e)}", delete_after=10)
            logger.error(f"Unban error: {e}", exc_info=True)

    # ========================
    # Admin Panel & Navigation
    # ========================

    @staticmethod
    async def admin_panel(client: Client, message: Message):
        """Main admin control panel"""
        try:
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🪙 Points System", callback_data="points_management"),
                    InlineKeyboardButton("👤 Users", callback_data="user_management")
                ],
                [
                    InlineKeyboardButton("🌟 Premium", callback_data="premium_management"),
                    InlineKeyboardButton("📊 Stats", callback_data="admin_stats")
                ],
                [InlineKeyboardButton("❌ Close", callback_data="close_admin")]
            ])

            await AdminCommands._send_response(
                message,
                "🛠 <b>Admin Control Panel</b>\n\n"
                "Select an option below:",
                reply_markup=buttons
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Panel error: {str(e)}")
            logger.error(f"Admin panel error: {e}", exc_info=True)

    @staticmethod
    async def points_management_panel(client: Client, message: Message):
        """Dedicated points management panel"""
        try:
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⚙️ Configure", callback_data="config_points"),
                    InlineKeyboardButton("👤 User Points", callback_data="manage_user_points")
                ],
                [
                    InlineKeyboardButton("🔗 Create Links", callback_data="create_points_link"),
                    InlineKeyboardButton("📊 Reports", callback_data="points_reports")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])

            await AdminCommands._send_response(
                message,
                "🪙 <b>Points Management</b>\n\n"
                "Manage all aspects of the points economy:",
                reply_markup=buttons
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Points panel error: {str(e)}")
            logger.error(f"Points panel error: {e}", exc_info=True)

    @staticmethod
    async def premium_management_panel(client: Client, message: Message):
        """Dedicated premium management panel"""
        try:
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➕ Activate", callback_data="activate_premium"),
                    InlineKeyboardButton("➖ Deactivate", callback_data="deactivate_premium")
                ],
                [
                    InlineKeyboardButton("📋 Check Status", callback_data="check_premium"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])

            await AdminCommands._send_response(
                message,
                "🌟 <b>Premium Management</b>\n\n"
                "Manage premium subscriptions:",
                reply_markup=buttons
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ Premium panel error: {str(e)}")
            logger.error(f"Premium panel error: {e}", exc_info=True)

    @staticmethod
    async def user_management_panel(client: Client, message: Message):
        """Dedicated user management panel"""
        try:
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🚫 Ban User", callback_data="ban_user"),
                    InlineKeyboardButton("✅ Unban User", callback_data="unban_user")
                ],
                [
                    InlineKeyboardButton("📊 User Info", callback_data="user_info"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])

            await AdminCommands._send_response(
                message,
                "👤 <b>User Management</b>\n\n"
                "Manage user accounts and restrictions:",
                reply_markup=buttons
            )
        except Exception as e:
            await AdminCommands._send_response(message, f"❌ User panel error: {str(e)}")
            logger.error(f"User panel error: {e}", exc_info=True)

# ========================
# Command Handlers
# ========================

@Client.on_message(filters.private & filters.command(
    ["admin", "pointconfig", "userpoints", "genlink", "premium", "stats", "pointsreport", "ban", "unban"]
) & filters.user(ADMIN_USER_ID))
async def admin_commands_handler(client: Client, message: Message):
    """Route admin commands to appropriate handlers"""
    try:
        cmd = message.command[0].lower()
        
        if cmd == "admin":
            await AdminCommands.admin_panel(client, message)
        elif cmd == "pointconfig":
            await AdminCommands.config_points_system(client, message)
        elif cmd == "userpoints":
            await AdminCommands.manage_user_points(client, message)
        elif cmd == "genlink":
            await AdminCommands.generate_points_link(client, message)
        elif cmd == "premium":
            await AdminCommands.manage_premium(client, message)
        elif cmd == "stats":
            await AdminCommands.bot_stats(client, message)
        elif cmd == "pointsreport":
            await AdminCommands.points_report(client, message)
        elif cmd == "ban":
            await AdminCommands.ban_user(client, message)
        elif cmd == "unban":
            await AdminCommands.unban_user(client, message)
            
    except Exception as e:
        await message.reply_text(f"❌ Command failed: {str(e)}", delete_after=10)
        logger.error(f"Admin command error: {e}", exc_info=True)

# ========================
# Callback Handlers
# ========================

@Client.on_callback_query(filters.regex(r"^admin_") & filters.user(ADMIN_USER_ID))
async def admin_callbacks(client: Client, callback: CallbackQuery):
    """Handle admin panel callbacks"""
    try:
        action = callback.data.split("_")[1]
        
        if action == "panel":
            await AdminCommands.admin_panel(client, callback.message)
        elif action == "stats":
            await AdminCommands.bot_stats(client, callback.message)
            
        await callback.answer()
    except Exception as e:
        logger.error(f"Admin callback error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")

@Client.on_callback_query(filters.regex(r"^points_") & filters.user(ADMIN_USER_ID))
async def points_management_callbacks(client: Client, callback: CallbackQuery):
    """Handle points management callbacks"""
    try:
        action = callback.data.split("_")[1]
        
        if action == "management":
            await AdminCommands.points_management_panel(client, callback.message)
        elif action == "config":
            await AdminCommands.config_points_system(client, callback.message)
        elif action == "user":
            await callback.message.edit_text(
                "👤 <b>Manage User Points</b>\n\n"
                "Use commands:\n"
                "<code>/userpoints user_id action amount [reason]</code>\n\n"
                "Actions: add, deduct, set",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="points_management")]
                ])
            )
        elif action == "create":
            await AdminCommands.generate_points_link(client, callback.message)
        elif action == "reports":
            await AdminCommands.points_report(client, callback.message)
            
        await callback.answer()
    except Exception as e:
        logger.error(f"Points callback error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")

@Client.on_callback_query(filters.regex(r"^premium_") & filters.user(ADMIN_USER_ID))
async def premium_management_callbacks(client: Client, callback: CallbackQuery):
    """Handle premium management callbacks"""
    try:
        action = callback.data.split("_")[1]
        
        if action == "management":
            await AdminCommands.premium_management_panel(client, callback.message)
        elif action == "activate":
            await callback.message.edit_text(
                "➕ <b>Activate Premium</b>\n\n"
                "Use command:\n"
                "<code>/premium user_id activate duration</code>\n\n"
                "<b>Duration formats:</b>\n"
                "• 30m (30 minutes)\n• 2h (2 hours)\n• 7d (7 days)\n\n"
                "<b>Example:</b>\n"
                "<code>/premium 1234567 activate 30d</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="premium_management")]
                ])
            )
        elif action == "deactivate":
            await callback.message.edit_text(
                "➖ <b>Deactivate Premium</b>\n\n"
                "Use command:\n"
                "<code>/premium user_id deactivate</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/premium 1234567 deactivate</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="premium_management")]
                ])
            )
        elif action == "check":
            await callback.message.edit_text(
                "📋 <b>Check Premium Status</b>\n\n"
                "Use command:\n"
                "<code>/premium user_id check</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/premium 1234567 check</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="premium_management")]
                ])
            )
            
        await callback.answer()
    except Exception as e:
        logger.error(f"Premium callback error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")

@Client.on_callback_query(filters.regex(r"^user_") & filters.user(ADMIN_USER_ID))
async def user_management_callbacks(client: Client, callback: CallbackQuery):
    """Handle user management callbacks"""
    try:
        action = callback.data.split("_")[1]
        
        if action == "management":
            await AdminCommands.user_management_panel(client, callback.message)
        elif action == "ban":
            await callback.message.edit_text(
                "🚫 <b>Ban User</b>\n\n"
                "Use command:\n"
                "<code>/ban user_id [reason]</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/ban 1234567 Spamming</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="user_management")]
                ])
            )
        elif action == "unban":
            await callback.message.edit_text(
                "✅ <b>Unban User</b>\n\n"
                "Use command:\n"
                "<code>/unban user_id</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/unban 1234567</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="user_management")]
                ])
            )
        elif action == "info":
            await callback.message.edit_text(
                "📊 <b>User Information</b>\n\n"
                "Use command:\n"
                "<code>/userinfo user_id</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/userinfo 1234567</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="user_management")]
                ])
            )
            
        await callback.answer()
    except Exception as e:
        logger.error(f"User management callback error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")

@Client.on_callback_query(filters.regex(r"^points_report_") & filters.user(ADMIN_USER_ID))
async def points_report_callbacks(client: Client, callback: CallbackQuery):
    """Handle points report callbacks"""
    try:
        days = int(callback.data.split("_")[-1])
        await AdminCommands.points_report(client, callback.message)
        await callback.answer(f"Showing {days}-day report")
    except Exception as e:
        logger.error(f"Points report callback error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")

@Client.on_callback_query(filters.regex(r"^refresh_stats$") & filters.user(ADMIN_USER_ID))
async def refresh_stats_callback(client: Client, callback: CallbackQuery):
    """Handle stats refresh callback"""
    try:
        await AdminCommands.bot_stats(client, callback.message)
        await callback.answer("Stats refreshed")
    except Exception as e:
        logger.error(f"Refresh stats error: {e}", exc_info=True)
        await callback.answer("❌ Error occurred")

@Client.on_callback_query(filters.regex(r"^close_admin$") & filters.user(ADMIN_USER_ID))
async def close_admin_panel(client: Client, callback: CallbackQuery):
    """Handle admin panel close callback"""
    try:
        await callback.message.delete()
        await callback.answer("Panel closed")
    except Exception as e:
        logger.error(f"Close panel error: {e}", exc_info=True)
        await callback.answer("❌ Error closing panel")
