import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Union, Dict, List
import secrets
import asyncio
import re
from contextlib import suppress

from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)
from pyrogram.errors import (
    FloodWait,
    UserIsBlocked,
    PeerIdInvalid,
    ChatWriteForbidden
)

from database.data import hyoshcoder
from config import settings

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ADMIN_USER_ID = settings.ADMIN
BOT_START_TIME = datetime.now()

class AdminPanel:
    """Complete admin interface with all management features"""
    
    # ========================
    # Configuration Defaults
    # ========================
    
    DEFAULT_CONFIG = {
        "points_config": {
            "rename_cost": 1,
            "referral_bonus": 10,
            "ad_points": {"min": 5, "max": 20, "daily_limit": 5},
            "new_user_balance": 70
        },
        "premium_plans": {
            "basic": {"price": 100, "features": "Basic features"},
            "premium": {"price": 200, "features": "Extra features"},
            "gold": {"price": 300, "features": "All features"}
        }
    }
    
    # ========================
    # Keyboard Layouts
    # ========================
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Main admin menu with all options"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Points System", callback_data="points_menu")],
            [InlineKeyboardButton("👤 User Management", callback_data="user_menu")],
            [InlineKeyboardButton("🌟 Premium Tools", callback_data="premium_menu")],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_menu"),
                InlineKeyboardButton("📊 Stats", callback_data="stats_menu")
            ],
            [
                InlineKeyboardButton("🔄 Update Config", callback_data="update_config"),
                InlineKeyboardButton("🔍 Search", callback_data="search_menu")
            ]
        ])
    
    @staticmethod
    def points_menu() -> InlineKeyboardMarkup:
        """Complete points configuration menu"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Set Rename Cost", callback_data="set_rename_cost")],
            [InlineKeyboardButton("🎁 Referral Bonus", callback_data="set_referral_bonus")],
            [InlineKeyboardButton("📺 Ad Points", callback_data="set_ad_points")],
            [InlineKeyboardButton("🔗 Generate Points Link", callback_data="gen_points_link")],
            [InlineKeyboardButton("📋 Points Links", callback_data="list_points_links")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ])
    
    @staticmethod
    def user_menu() -> InlineKeyboardMarkup:
        """Complete user management menu"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Add Points", callback_data="add_points"),
                InlineKeyboardButton("➖ Deduct Points", callback_data="deduct_points")
            ],
            [
                InlineKeyboardButton("🚫 Ban User", callback_data="ban_user"),
                InlineKeyboardButton("✅ Unban User", callback_data="unban_user")
            ],
            [
                InlineKeyboardButton("🔍 Find User", callback_data="find_user"),
                InlineKeyboardButton("📜 User Logs", callback_data="user_logs")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ])
    
    @staticmethod
    def premium_menu() -> InlineKeyboardMarkup:
        """Complete premium management menu"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐ Activate", callback_data="activate_premium"),
                InlineKeyboardButton("❌ Deactivate", callback_data="deactivate_premium")
            ],
            [
                InlineKeyboardButton("📝 Check Status", callback_data="check_premium"),
                InlineKeyboardButton("📊 Plans", callback_data="premium_plans")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ])
    
    @staticmethod
    def broadcast_menu() -> InlineKeyboardMarkup:
        """Broadcast options menu"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📝 Text Broadcast", callback_data="text_broadcast"),
                InlineKeyboardButton("🖼 Media Broadcast", callback_data="media_broadcast")
            ],
            [
                InlineKeyboardButton("📊 Stats Only", callback_data="stats_broadcast"),
                InlineKeyboardButton("🎯 Targeted", callback_data="targeted_broadcast")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ])
    
    @staticmethod
    def search_menu() -> InlineKeyboardMarkup:
        """Search options menu"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔎 By ID", callback_data="search_id"),
                InlineKeyboardButton("📛 By Username", callback_data="search_username")
            ],
            [
                InlineKeyboardButton("📅 By Join Date", callback_data="search_join_date"),
                InlineKeyboardButton("🪙 By Points", callback_data="search_points")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ])
    
    @staticmethod
    def back_button(target: str = "admin_main") -> InlineKeyboardMarkup:
        """Dynamic back button"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=target)]
        ])

    # ========================
    # Core Utilities
    # ========================
    
    @staticmethod
    async def get_config(key: str, default: Any = None) -> Any:
        """Get configuration value with defaults"""
        config = await hyoshcoder.get_config(key)
        if config is None and key in AdminPanel.DEFAULT_CONFIG:
            await hyoshcoder.db.config.update_one(
                {"key": key},
                {"$set": {"value": AdminPanel.DEFAULT_CONFIG[key]}},
                upsert=True
            )
            return AdminPanel.DEFAULT_CONFIG[key]
        return config or default
    
    @staticmethod
    async def update_config(key: str, value: Any) -> bool:
        """Safely update configuration"""
        try:
            await hyoshcoder.db.config.update_one(
                {"key": "points_config"},
                {"$set": {f"value.{key}": value}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return False
    
    @staticmethod
    def _format_uptime() -> str:
        """Format bot uptime for display"""
        uptime = datetime.now() - BOT_START_TIME
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"
    
    @staticmethod
    def _parse_duration(duration_str: str) -> timedelta:
        """Parse duration string into timedelta"""
        try:
            num = int(re.search(r'\d+', duration_str).group())
            unit = re.search(r'[mhd]', duration_str.lower()).group()
            
            if unit == 'm':
                return timedelta(minutes=num)
            elif unit == 'h':
                return timedelta(hours=num)
            elif unit == 'd':
                return timedelta(days=num)
            return timedelta(hours=1)
        except (ValueError, AttributeError):
            return timedelta(hours=1)
    
    @staticmethod
    async def _edit_or_reply(
        target: Union[Message, CallbackQuery],
        text: str,
        reply_markup: InlineKeyboardMarkup = None,
        parse_mode: enums.ParseMode = enums.ParseMode.HTML,
        disable_web_page_preview: bool = True
    ) -> Message:
        """Smart response handler for both messages and callbacks"""
        try:
            if isinstance(target, CallbackQuery):
                await target.message.edit_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
                await target.answer()
                return target.message
            else:
                return await target.reply_text(
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=disable_web_page_preview
                )
        except Exception as e:
            logger.error(f"Error in _edit_or_reply: {e}")
            return None

    @staticmethod
    async def _confirm_action(
        client: Client,
        target: Union[Message, CallbackQuery],
        action: str,
        confirm_data: str,
        cancel_data: str = None
    ) -> Message:
        """Show confirmation dialog for destructive actions"""
        cancel_data = cancel_data or confirm_data.split('_')[0] + "_menu"
        
        return await AdminPanel._edit_or_reply(
            target,
            f"⚠️ <b>Confirm {action}</b>\n\n"
            "Are you sure you want to proceed?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Confirm", callback_data=confirm_data),
                    InlineKeyboardButton("❌ Cancel", callback_data=cancel_data)
                ]
            ])
        )

    # ========================
    # Menu Handlers
    # ========================
    
    @staticmethod
    async def show_main_menu(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Display main admin menu"""
        return await AdminPanel._edit_or_reply(
            target,
            "👨‍💼 <b>Admin Panel</b>\n\n"
            "Select an option below:",
            reply_markup=AdminPanel.main_menu()
        )
    
    @staticmethod
    async def show_points_menu(client: Client, callback: CallbackQuery) -> Message:
        """Display points configuration menu with current values"""
        config = await AdminPanel.get_config("points_config")
        
        text = (
            "⚙️ <b>Points Configuration</b>\n\n"
            f"• Rename Cost: {config.get('rename_cost', 1)} point(s)\n"
            f"• Referral Bonus: {config.get('referral_bonus', 10)} points\n"
            f"• Ad Points: {config.get('ad_points', {}).get('min', 5)}-{config.get('ad_points', {}).get('max', 20)}\n"
            f"• Daily Ad Limit: {config.get('ad_points', {}).get('daily_limit', 5)}\n"
            f"• New User Balance: {config.get('new_user_balance', 70)}"
        )
        
        return await AdminPanel._edit_or_reply(
            callback,
            text,
            reply_markup=AdminPanel.points_menu()
        )

    @staticmethod
    async def show_user_menu(client: Client, callback: CallbackQuery) -> Message:
        """Display user management menu"""
        return await AdminPanel._edit_or_reply(
            callback,
            "👤 <b>User Management</b>\n\n"
            "Select an action:",
            reply_markup=AdminPanel.user_menu()
        )
    
    @staticmethod
    async def show_premium_menu(client: Client, callback: CallbackQuery) -> Message:
        """Display premium management menu"""
        return await AdminPanel._edit_or_reply(
            callback,
            "🌟 <b>Premium Management</b>\n\n"
            "Select an action:",
            reply_markup=AdminPanel.premium_menu()
        )
    
    @staticmethod
    async def show_broadcast_menu(client: Client, callback: CallbackQuery) -> Message:
        """Display broadcast options menu"""
        return await AdminPanel._edit_or_reply(
            callback,
            "📢 <b>Broadcast Options</b>\n\n"
            "Choose broadcast type:",
            reply_markup=AdminPanel.broadcast_menu()
        )
    
    @staticmethod
    async def show_search_menu(client: Client, callback: CallbackQuery) -> Message:
        """Display search options menu"""
        return await AdminPanel._edit_or_reply(
            callback,
            "🔍 <b>Search Users</b>\n\n"
            "Select search criteria:",
            reply_markup=AdminPanel.search_menu()
        )

    # ========================
    # Points System Handlers
    # ========================
    
    @staticmethod
    async def handle_set_rename_cost(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Handle rename cost configuration"""
        config = await AdminPanel.get_config("points_config")
        current_cost = config.get("rename_cost", 1)
        
        return await AdminPanel._edit_or_reply(
            target,
            "💳 <b>Set Rename Cost</b>\n\n"
            f"Current cost: {current_cost} point(s)\n\n"
            "Enter new cost (in points):\n"
            "<code>/setcost [amount]</code>\n\n"
            "Example: <code>/setcost 2</code>",
            reply_markup=AdminPanel.back_button("points_menu")
        )
    
    @staticmethod
    async def process_set_cost(client: Client, message: Message) -> Message:
        """Process rename cost change command"""
        try:
            cost = int(message.text.split()[1])
            if cost < 0:
                raise ValueError("Cost cannot be negative")
                
            success = await AdminPanel.update_config("rename_cost", cost)
            if not success:
                raise Exception("Failed to update config")
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Rename cost set to {cost} point(s)",
                reply_markup=AdminPanel.back_button("points_menu")
            )
        except (IndexError, ValueError, Exception) as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/setcost [amount]</code>\n"
                "Example: <code>/setcost 2</code>",
                reply_markup=AdminPanel.back_button("points_menu")
            )
    
    @staticmethod
    async def handle_set_referral_bonus(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Handle referral bonus configuration"""
        config = await AdminPanel.get_config("points_config")
        current_bonus = config.get("referral_bonus", 10)
        
        return await AdminPanel._edit_or_reply(
            target,
            "🎁 <b>Set Referral Bonus</b>\n\n"
            f"Current bonus: {current_bonus} points\n\n"
            "Enter new bonus amount:\n"
            "<code>/setreferral [amount]</code>\n\n"
            "Example: <code>/setreferral 15</code>",
            reply_markup=AdminPanel.back_button("points_menu")
        )
    
    @staticmethod
    async def process_set_referral(client: Client, message: Message) -> Message:
        """Process referral bonus change"""
        try:
            bonus = int(message.text.split()[1])
            if bonus < 0:
                raise ValueError("Bonus cannot be negative")
                
            success = await AdminPanel.update_config("referral_bonus", bonus)
            if not success:
                raise Exception("Failed to update config")
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Referral bonus set to {bonus} points",
                reply_markup=AdminPanel.back_button("points_menu")
            )
        except (IndexError, ValueError, Exception) as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/setreferral [amount]</code>\n"
                "Example: <code>/setreferral 15</code>",
                reply_markup=AdminPanel.back_button("points_menu")
            )
    
    @staticmethod
    async def generate_points_link_ui(client: Client, callback: CallbackQuery) -> Message:
        """Show points link generation UI"""
        return await AdminPanel._edit_or_reply(
            callback,
            "🔗 <b>Generate Points Link</b>\n\n"
            "Enter command:\n"
            "<code>/genlink points uses expires</code>\n\n"
            "<b>Example:</b> <code>/genlink 50 10 24h</code>\n"
            "<b>Expires formats:</b> 24h, 7d, 30m",
            reply_markup=AdminPanel.back_button("points_menu")
        )
    
    @staticmethod
    async def process_gen_link(client: Client, message: Message) -> Message:
        """Process points link generation"""
        try:
            parts = message.text.split()
            if len(parts) < 4:
                raise ValueError("Missing parameters")
            
            points = int(parts[1])
            max_uses = int(parts[2])
            expires_in = parts[3]
            
            if points <= 0 or max_uses <= 0:
                raise ValueError("Points and uses must be positive")
            
            expires_delta = AdminPanel._parse_duration(expires_in)
            expires_at = datetime.now() + expires_delta
            
            code = secrets.token_urlsafe(8)
            bot_username = (await client.get_me()).username
            link = f"https://t.me/{bot_username}?start=points_{code}"
            
            await hyoshcoder.point_links.insert_one({
                "code": code,
                "points": points,
                "max_uses": max_uses,
                "uses_left": max_uses,
                "expires_at": expires_at,
                "created_at": datetime.now(),
                "created_by": message.from_user.id
            })
            
            return await AdminPanel._edit_or_reply(
                message,
                f"🔗 <b>Points Link Created</b>\n\n"
                f"🪙 Points: {points}\n"
                f"🔢 Uses: {max_uses}\n"
                f"⏳ Expires: {expires_in} ({expires_at.strftime('%Y-%m-%d %H:%M')})\n\n"
                f"📌 Code: <code>{code}</code>\n"
                f"🔗 Link: {link}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 Delete", callback_data=f"del_link_{code}")],
                    [InlineKeyboardButton("🔙 Back", callback_data="points_menu")]
                ])
            )
            
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/genlink points uses expires</code>\n"
                "Example: <code>/genlink 50 10 24h</code>",
                reply_markup=AdminPanel.back_button("points_menu")
            )
    
    @staticmethod
    async def list_points_links(client: Client, callback: CallbackQuery) -> Message:
        """List all active points links"""
        try:
            links = await hyoshcoder.point_links.find({
                "expires_at": {"$gt": datetime.now()},
                "uses_left": {"$gt": 0}
            }).sort("created_at", -1).to_list(length=20)
            
            if not links:
                return await AdminPanel._edit_or_reply(
                    callback,
                    "🔗 <b>Points Links</b>\n\n"
                    "No active points links found.",
                    reply_markup=AdminPanel.back_button("points_menu")
                )
            
            text = "🔗 <b>Active Points Links</b>\n\n"
            for link in links:
                creator = await client.get_users(link["created_by"])
                text += (
                    f"🪙 <b>{link['points']} points</b>\n"
                    f"🔢 Uses: {link['uses_left']}/{link['max_uses']}\n"
                    f"⏳ Expires: {link['expires_at'].strftime('%Y-%m-%d %H:%M')}\n"
                    f"👤 Created by: {creator.mention}\n"
                    f"🔗 <code>https://t.me/{(await client.get_me()).username}?start=points_{link['code']}</code>\n\n"
                )
            
            return await AdminPanel._edit_or_reply(
                callback,
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 Delete All", callback_data="del_all_links")],
                    [InlineKeyboardButton("🔙 Back", callback_data="points_menu")]
                ])
            )
            
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                callback,
                f"❌ Error listing links: {str(e)}",
                reply_markup=AdminPanel.back_button("points_menu")
            )
    
    @staticmethod
    async def delete_points_link(client: Client, callback: CallbackQuery, code: str) -> Message:
        """Delete a points link"""
        try:
            result = await hyoshcoder.point_links.delete_one({"code": code})
            if result.deleted_count:
                await callback.answer("✅ Link deleted")
                return await AdminPanel.list_points_links(client, callback)
            else:
                await callback.answer("❌ Link not found")
                return await callback.message.edit_reply_markup(
                    reply_markup=AdminPanel.back_button("points_menu")
                )
        except Exception as e:
            await callback.answer(f"❌ Error: {str(e)}")
            return await AdminPanel.show_points_menu(client, callback)
    
    @staticmethod
    async def delete_all_points_links(client: Client, callback: CallbackQuery) -> Message:
        """Delete all points links"""
        try:
            result = await hyoshcoder.point_links.delete_many({
                "expires_at": {"$gt": datetime.now()},
                "uses_left": {"$gt": 0}
            })
            await callback.answer(f"✅ Deleted {result.deleted_count} links")
            return await AdminPanel.list_points_links(client, callback)
        except Exception as e:
            await callback.answer(f"❌ Error: {str(e)}")
            return await AdminPanel.show_points_menu(client, callback)

    # ========================
    # User Management Handlers
    # ========================
    
    @staticmethod
    async def handle_add_points(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate add points flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "➕ <b>Add Points</b>\n\n"
            "Enter command:\n"
            "<code>/addpoints user_id amount [reason]</code>\n\n"
            "Example: <code>/addpoints 123456 50 \"Bonus for activity\"</code>",
            reply_markup=AdminPanel.back_button("user_menu")
        )
    
    @staticmethod
    async def process_add_points(client: Client, message: Message) -> Message:
        """Process adding points to user"""
        try:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                raise ValueError("Missing parameters")
            
            user_id = int(parts[1])
            amount = int(parts[2])
            reason = parts[3] if len(parts) > 3 else "Admin addition"
            
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            await hyoshcoder.add_points(user_id, amount, "admin_addition", reason)
            user = await hyoshcoder.get_user(user_id)
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Added {amount} points to user {user_id}\n"
                f"📝 Reason: {reason}\n"
                f"🪙 New balance: {user['points']['balance']}",
                reply_markup=AdminPanel.back_button("user_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/addpoints user_id amount [reason]</code>\n"
                "Example: <code>/addpoints 123456 50 \"Bonus\"</code>",
                reply_markup=AdminPanel.back_button("user_menu")
            )
    
    @staticmethod
    async def handle_deduct_points(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate deduct points flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "➖ <b>Deduct Points</b>\n\n"
            "Enter command:\n"
            "<code>/deductpoints user_id amount [reason]</code>\n\n"
            "Example: <code>/deductpoints 123456 50 \"Refund\"</code>",
            reply_markup=AdminPanel.back_button("user_menu")
        )
    
    @staticmethod
    async def process_deduct_points(client: Client, message: Message) -> Message:
        """Process deducting points from user"""
        try:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 3:
                raise ValueError("Missing parameters")
            
            user_id = int(parts[1])
            amount = int(parts[2])
            reason = parts[3] if len(parts) > 3 else "Admin deduction"
            
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            success = await hyoshcoder.deduct_points(user_id, amount, reason)
            if not success:
                raise Exception("Failed to deduct points (insufficient balance?)")
            
            user = await hyoshcoder.get_user(user_id)
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Deducted {amount} points from user {user_id}\n"
                f"📝 Reason: {reason}\n"
                f"🪙 New balance: {user['points']['balance']}",
                reply_markup=AdminPanel.back_button("user_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/deductpoints user_id amount [reason]</code>\n"
                "Example: <code>/deductpoints 123456 50 \"Refund\"</code>",
                reply_markup=AdminPanel.back_button("user_menu")
            )
    
    @staticmethod
    async def handle_ban_user(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate user ban flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "🚫 <b>Ban User</b>\n\n"
            "Enter command:\n"
            "<code>/ban user_id duration reason</code>\n\n"
            "Example: <code>/ban 123456 7d \"Spamming\"</code>\n"
            "Duration formats: 1h, 7d, 30d, 1y",
            reply_markup=AdminPanel.back_button("user_menu")
        )
    
    @staticmethod
    async def process_ban_user(client: Client, message: Message) -> Message:
        """Process banning a user"""
        try:
            parts = message.text.split(maxsplit=3)
            if len(parts) < 3:
                raise ValueError("Missing parameters")
            
            user_id = int(parts[1])
            duration_str = parts[2]
            reason = parts[3] if len(parts) > 3 else "No reason provided"
            
            duration = AdminPanel._parse_duration(duration_str)
            days = duration.days if duration.days > 0 else 1
            
            await hyoshcoder.ban_user(user_id, days, reason)
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Banned user {user_id}\n"
                f"⏳ Duration: {days} days\n"
                f"📝 Reason: {reason}",
                reply_markup=AdminPanel.back_button("user_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/ban user_id duration reason</code>\n"
                "Example: <code>/ban 123456 7d \"Spamming\"</code>",
                reply_markup=AdminPanel.back_button("user_menu")
            )
    
    @staticmethod
    async def handle_unban_user(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate user unban flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "✅ <b>Unban User</b>\n\n"
            "Enter command:\n"
            "<code>/unban user_id [reason]</code>\n\n"
            "Example: <code>/unban 123456 \"Good behavior\"</code>",
            reply_markup=AdminPanel.back_button("user_menu")
        )
    
    @staticmethod
    async def process_unban_user(client: Client, message: Message) -> Message:
        """Process unbanning a user"""
        try:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 2:
                raise ValueError("Missing user ID")
            
            user_id = int(parts[1])
            reason = parts[2] if len(parts) > 2 else "Manual unban"
            
            await hyoshcoder.remove_ban(user_id)
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Unbanned user {user_id}\n"
                f"📝 Reason: {reason}",
                reply_markup=AdminPanel.back_button("user_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/unban user_id [reason]</code>\n"
                "Example: <code>/unban 123456 \"Good behavior\"</code>",
                reply_markup=AdminPanel.back_button("user_menu")
            )
    
    @staticmethod
    async def handle_find_user(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate user search flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "🔍 <b>Find User</b>\n\n"
            "Enter command:\n"
            "<code>/finduser user_id</code>\n\n"
            "Example: <code>/finduser 123456</code>",
            reply_markup=AdminPanel.back_button("user_menu")
        )
    
    @staticmethod
    async def process_find_user(client: Client, message: Message) -> Message:
        """Process finding a user"""
        try:
            user_id = int(message.text.split()[1])
            user = await hyoshcoder.get_user(user_id)
            
            if not user:
                return await AdminPanel._edit_or_reply(
                    message,
                    f"❌ User {user_id} not found",
                    reply_markup=AdminPanel.back_button("user_menu")
                )
            
            # Format user info
            text = f"👤 <b>User Info</b> - ID: {user_id}\n\n"
            text += f"🆔 ID: <code>{user_id}</code>\n"
            text += f"📅 Joined: {user.get('join_date', 'Unknown')}\n"
            text += f"🪙 Points: {user['points']['balance']} (Total earned: {user['points']['total_earned']})\n"
            text += f"⭐ Premium: {'Yes' if user['premium']['is_premium'] else 'No'}\n"
            text += f"🚫 Banned: {'Yes' if user['ban_status']['is_banned'] else 'No'}\n"
            text += f"📂 Files renamed: {user['activity']['total_files_renamed']}\n"
            
            # Add user actions
            buttons = [
                [
                    InlineKeyboardButton("➕ Add Points", callback_data=f"addpts_{user_id}"),
                    InlineKeyboardButton("➖ Deduct Points", callback_data=f"deductpts_{user_id}")
                ],
                [
                    InlineKeyboardButton("🚫 Ban User", callback_data=f"ban_{user_id}"),
                    InlineKeyboardButton("✅ Unban User", callback_data=f"unban_{user_id}")
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="user_menu")]
            ]
            
            return await AdminPanel._edit_or_reply(
                message,
                text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/finduser user_id</code>\n"
                "Example: <code>/finduser 123456</code>",
                reply_markup=AdminPanel.back_button("user_menu")
            )

    # ========================
    # Premium Management
    # ========================
    
    @staticmethod
    async def show_premium_plans(client: Client, callback: CallbackQuery) -> Message:
        """Display premium plans"""
        plans = await AdminPanel.get_config("premium_plans")
        
        text = "🌟 <b>Premium Plans</b>\n\n"
        for plan, details in plans.items():
            text += (
                f"✨ <b>{plan.capitalize()}</b>\n"
                f"🪙 Price: {details['price']} points\n"
                f"📝 Features: {details['features']}\n\n"
            )
        
        return await AdminPanel._edit_or_reply(
            callback,
            text,
            reply_markup=AdminPanel.back_button("premium_menu")
        )
    
    @staticmethod
    async def handle_activate_premium(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate premium activation flow"""
        plans = await AdminPanel.get_config("premium_plans")
        plan_options = "\n".join([f"• {plan}" for plan in plans.keys()])
        
        return await AdminPanel._edit_or_reply(
            target,
            "🌟 <b>Activate Premium</b>\n\n"
            "Enter command:\n"
            "<code>/premium user_id duration plan</code>\n\n"
            "Example: <code>/premium 123456 30d gold</code>\n"
            "Duration formats: 7d, 30d, 1y\n"
            f"Available plans:\n{plan_options}",
            reply_markup=AdminPanel.back_button("premium_menu")
        )
    
    @staticmethod
    async def process_activate_premium(client: Client, message: Message) -> Message:
        """Process premium activation"""
        try:
            parts = message.text.split()
            if len(parts) < 3:
                raise ValueError("Missing parameters")
            
            user_id = int(parts[1])
            duration_str = parts[2]
            plan = parts[3] if len(parts) > 3 else "premium"
            
            duration = AdminPanel._parse_duration(duration_str)
            
            await hyoshcoder.activate_premium(
                user_id=user_id,
                plan=plan,
                duration_days=duration.days
            )
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Activated premium for user {user_id}\n"
                f"⏳ Duration: {duration_str}\n"
                f"📝 Plan: {plan}",
                reply_markup=AdminPanel.back_button("premium_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/premium user_id duration plan</code>\n"
                "Example: <code>/premium 123456 30d gold</code>",
                reply_markup=AdminPanel.back_button("premium_menu")
            )
    
    @staticmethod
    async def handle_deactivate_premium(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate premium deactivation flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "❌ <b>Deactivate Premium</b>\n\n"
            "Enter command:\n"
            "<code>/depremium user_id [reason]</code>\n\n"
            "Example: <code>/depremium 123456 \"Expired\"</code>",
            reply_markup=AdminPanel.back_button("premium_menu")
        )
    
    @staticmethod
    async def process_deactivate_premium(client: Client, message: Message) -> Message:
        """Process premium deactivation"""
        try:
            parts = message.text.split(maxsplit=2)
            if len(parts) < 2:
                raise ValueError("Missing user ID")
            
            user_id = int(parts[1])
            reason = parts[2] if len(parts) > 2 else "Manual deactivation"
            
            await hyoshcoder.deactivate_premium(user_id)
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Deactivated premium for user {user_id}\n"
                f"📝 Reason: {reason}",
                reply_markup=AdminPanel.back_button("premium_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/depremium user_id [reason]</code>\n"
                "Example: <code>/depremium 123456 \"Expired\"</code>",
                reply_markup=AdminPanel.back_button("premium_menu")
            )
    
    @staticmethod
    async def handle_check_premium(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate premium status check"""
        return await AdminPanel._edit_or_reply(
            target,
            "📝 <b>Check Premium Status</b>\n\n"
            "Enter command:\n"
            "<code>/checkpremium user_id</code>\n\n"
            "Example: <code>/checkpremium 123456</code>",
            reply_markup=AdminPanel.back_button("premium_menu")
        )
    
    @staticmethod
    async def process_check_premium(client: Client, message: Message) -> Message:
        """Process premium status check"""
        try:
            user_id = int(message.text.split()[1])
            status = await hyoshcoder.check_premium_status(user_id)
            
            if status["is_premium"]:
                text = (
                    f"🌟 <b>Premium Status</b> - User {user_id}\n\n"
                    f"✅ Active Premium\n"
                    f"📝 Plan: {status.get('plan', 'Unknown')}\n"
                    f"⏳ Valid until: {status.get('until', 'Unknown')}"
                )
            else:
                text = (
                    f"🌟 <b>Premium Status</b> - User {user_id}\n\n"
                    f"❌ No active premium\n"
                    f"📝 Reason: {status.get('reason', 'Unknown')}"
                )
            
            return await AdminPanel._edit_or_reply(
                message,
                text,
                reply_markup=AdminPanel.back_button("premium_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/checkpremium user_id</code>\n"
                "Example: <code>/checkpremium 123456</code>",
                reply_markup=AdminPanel.back_button("premium_menu")
            )

    # ========================
    # Broadcast Handlers
    # ========================
    
    @staticmethod
    async def handle_broadcast(client: Client, callback: CallbackQuery) -> Message:
        """Initiate broadcast flow"""
        return await AdminPanel._edit_or_reply(
            callback,
            "📢 <b>Broadcast Message</b>\n\n"
            "Reply to this message with your content:\n"
            "- Text for text broadcast\n"
            "- Media for media broadcast\n\n"
            "Add <code>--silent</code> to disable notifications",
            reply_markup=AdminPanel.back_button("broadcast_menu")
        )
    
    @staticmethod
    async def process_broadcast(client: Client, message: Message) -> Message:
        """Process sending broadcast to all users"""
        try:
            if not message.reply_to_message:
                raise ValueError("You must reply to the broadcast instruction message")
            
            broadcast_msg = message.reply_to_message
            silent = "--silent" in message.text.lower()
            
            users = await hyoshcoder.get_all_users(filter_banned=True)
            total = len(users)
            success = 0
            failed = 0
            
            status_msg = await message.reply_text(
                f"📢 Broadcasting to {total} users...\n"
                f"✅ Success: {success}\n"
                f"❌ Failed: {failed}"
            )
            
            for user in users:
                try:
                    if broadcast_msg.text:
                        await client.send_message(
                            chat_id=user["_id"],
                            text=broadcast_msg.text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_notification=silent
                        )
                    else:
                        await broadcast_msg.copy(
                            chat_id=user["_id"],
                            disable_notification=silent
                        )
                    success += 1
                except (UserIsBlocked, PeerIdInvalid, ChatWriteForbidden):
                    failed += 1
                except Exception as e:
                    logger.error(f"Broadcast error for {user['_id']}: {e}")
                    failed += 1
                
                # Update status every 10 sends
                if (success + failed) % 10 == 0:
                    with suppress(Exception):
                        await status_msg.edit_text(
                            f"📢 Broadcasting to {total} users...\n"
                            f"✅ Success: {success}\n"
                            f"❌ Failed: {failed}"
                        )
            
            await status_msg.edit_text(
                f"📢 Broadcast Complete!\n"
                f"✅ Success: {success}\n"
                f"❌ Failed: {failed}"
            )
            
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Broadcast error: {str(e)}",
                reply_markup=AdminPanel.back_button("broadcast_menu")
            )
    
    @staticmethod
    async def handle_stats_broadcast(client: Client, callback: CallbackQuery) -> Message:
        """Initiate stats broadcast"""
        stats = await asyncio.gather(
            hyoshcoder.total_users_count(),
            hyoshcoder.total_premium_users_count(),
            hyoshcoder.total_renamed_files(),
            hyoshcoder.total_points_distributed(),
            hyoshcoder.get_daily_active_users()
        )
        
        text = (
            "📊 <b>Bot Statistics</b>\n\n"
            f"👥 Total Users: {stats[0]}\n"
            f"⭐ Premium Users: {stats[1]}\n"
            f"📂 Files Renamed: {stats[2]}\n"
            f"🪙 Points Distributed: {stats[3]}\n"
            f"📈 Active Today: {stats[4]}"
        )
        
        return await AdminPanel._edit_or_reply(
            callback,
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Send Stats", callback_data="confirm_stats_broadcast")],
                [InlineKeyboardButton("🔙 Back", callback_data="broadcast_menu")]
            ])
        )
    
    @staticmethod
    async def process_stats_broadcast(client: Client, callback: CallbackQuery) -> Message:
        """Send stats broadcast to all users"""
        try:
            users = await hyoshcoder.get_all_users(filter_banned=True)
            total = len(users)
            success = 0
            failed = 0
            
            stats = await asyncio.gather(
                hyoshcoder.total_users_count(),
                hyoshcoder.total_premium_users_count(),
                hyoshcoder.total_renamed_files(),
                hyoshcoder.total_points_distributed(),
                hyoshcoder.get_daily_active_users()
            )
            
            text = (
                "📊 <b>Bot Statistics Update</b>\n\n"
                f"👥 Total Users: {stats[0]}\n"
                f"⭐ Premium Users: {stats[1]}\n"
                f"📂 Files Renamed: {stats[2]}\n"
                f"🪙 Points Distributed: {stats[3]}\n"
                f"📈 Active Today: {stats[4]}"
            )
            
            status_msg = await callback.message.reply_text(
                f"📢 Broadcasting stats to {total} users...\n"
                f"✅ Success: {success}\n"
                f"❌ Failed: {failed}"
            )
            
            for user in users:
                try:
                    await client.send_message(
                        chat_id=user["_id"],
                        text=text,
                        parse_mode=enums.ParseMode.HTML
                    )
                    success += 1
                except (UserIsBlocked, PeerIdInvalid, ChatWriteForbidden):
                    failed += 1
                except Exception as e:
                    logger.error(f"Stats broadcast error for {user['_id']}: {e}")
                    failed += 1
                
                if (success + failed) % 10 == 0:
                    with suppress(Exception):
                        await status_msg.edit_text(
                            f"📢 Broadcasting stats to {total} users...\n"
                            f"✅ Success: {success}\n"
                            f"❌ Failed: {failed}"
                        )
            
            await status_msg.edit_text(
                f"📢 Stats Broadcast Complete!\n"
                f"✅ Success: {success}\n"
                f"❌ Failed: {failed}"
            )
            
            return await callback.message.edit_reply_markup(
                reply_markup=AdminPanel.back_button("broadcast_menu")
            )
            
        except Exception as e:
            await callback.answer(f"❌ Error: {str(e)}")
            return await AdminPanel.show_broadcast_menu(client, callback)

    # ========================
    # Stats & Reports
    # ========================
    
    @staticmethod
    async def show_stats(client: Client, callback: CallbackQuery) -> Message:
        """Display comprehensive bot statistics"""
        stats = await asyncio.gather(
            hyoshcoder.total_users_count(),
            hyoshcoder.total_premium_users_count(),
            hyoshcoder.total_renamed_files(),
            hyoshcoder.total_points_distributed(),
            hyoshcoder.total_banned_users_count(),
            hyoshcoder.get_daily_active_users()
        )
        
        return await AdminPanel._edit_or_reply(
            callback,
            "📊 <b>Bot Statistics</b>\n\n"
            f"⏱ Uptime: {AdminPanel._format_uptime()}\n"
            f"👥 Total Users: {stats[0]}\n"
            f"⭐ Premium Users: {stats[1]}\n"
            f"🚫 Banned Users: {stats[4]}\n"
            f"📈 Active Today: {stats[5]}\n"
            f"📂 Files Renamed: {stats[2]}\n"
            f"🪙 Points Distributed: {stats[3]}",
            reply_markup=AdminPanel.back_button()
        )
    
    @staticmethod
    async def show_user_stats(client: Client, callback: CallbackQuery, user_id: int) -> Message:
        """Display detailed stats for a specific user"""
        user = await hyoshcoder.get_user(user_id)
        if not user:
            await callback.answer("User not found")
            return await AdminPanel.show_user_menu(client, callback)
        
        file_stats = await hyoshcoder.get_user_file_stats(user_id)
        
        text = (
            f"👤 <b>User Stats</b> - ID: {user_id}\n\n"
            f"📅 Joined: {user.get('join_date', 'Unknown')}\n"
            f"🪙 Points: {user['points']['balance']} (Total earned: {user['points']['total_earned']})\n"
            f"⭐ Premium: {'Yes' if user['premium']['is_premium'] else 'No'}\n"
            f"🚫 Banned: {'Yes' if user['ban_status']['is_banned'] else 'No'}\n\n"
            f"📂 <b>File Rename Stats</b>\n"
            f"• Total: {file_stats['total_renamed']}\n"
            f"• Today: {file_stats['today']}\n"
            f"• This Week: {file_stats['this_week']}\n"
            f"• This Month: {file_stats['this_month']}"
        )
        
        return await AdminPanel._edit_or_reply(
            callback,
            text,
            reply_markup=AdminPanel.back_button("user_menu")
        )

    # ========================
    # Callback Handlers
    # ========================
    
    @staticmethod
    async def handle_admin_callbacks(client: Client, callback: CallbackQuery):
        """Central callback handler for all admin actions"""
        data = callback.data
        
        try:
            if data == "admin_main":
                await AdminPanel.show_main_menu(client, callback)
            elif data == "points_menu":
                await AdminPanel.show_points_menu(client, callback)
            elif data == "user_menu":
                await AdminPanel.show_user_menu(client, callback)
            elif data == "premium_menu":
                await AdminPanel.show_premium_menu(client, callback)
            elif data == "broadcast_menu":
                await AdminPanel.show_broadcast_menu(client, callback)
            elif data == "stats_menu":
                await AdminPanel.show_stats(client, callback)
            elif data == "search_menu":
                await AdminPanel.show_search_menu(client, callback)
            
            # Points system
            elif data == "set_rename_cost":
                await AdminPanel.handle_set_rename_cost(client, callback)
            elif data == "set_referral_bonus":
                await AdminPanel.handle_set_referral_bonus(client, callback)
            elif data == "gen_points_link":
                await AdminPanel.generate_points_link_ui(client, callback)
            elif data == "list_points_links":
                await AdminPanel.list_points_links(client, callback)
            elif data.startswith("del_link_"):
                code = data.split("_")[2]
                await AdminPanel.delete_points_link(client, callback, code)
            elif data == "del_all_links":
                await AdminPanel._confirm_action(
                    client, callback, 
                    "delete all points links", 
                    "confirm_del_all_links"
                )
            elif data == "confirm_del_all_links":
                await AdminPanel.delete_all_points_links(client, callback)
            
            # User management
            elif data == "add_points":
                await AdminPanel.handle_add_points(client, callback)
            elif data == "deduct_points":
                await AdminPanel.handle_deduct_points(client, callback)
            elif data == "ban_user":
                await AdminPanel.handle_ban_user(client, callback)
            elif data == "unban_user":
                await AdminPanel.handle_unban_user(client, callback)
            elif data == "find_user":
                await AdminPanel.handle_find_user(client, callback)
            elif data.startswith("addpts_"):
                user_id = int(data.split("_")[1])
                await AdminPanel._edit_or_reply(
                    callback,
                    f"➕ <b>Add Points to User {user_id}</b>\n\n"
                    "Enter amount to add:",
                    reply_markup=AdminPanel.back_button(f"finduser_{user_id}")
                )
            elif data.startswith("deductpts_"):
                user_id = int(data.split("_")[1])
                await AdminPanel._edit_or_reply(
                    callback,
                    f"➖ <b>Deduct Points from User {user_id}</b>\n\n"
                    "Enter amount to deduct:",
                    reply_markup=AdminPanel.back_button(f"finduser_{user_id}")
                )
            
            # Premium management
            elif data == "activate_premium":
                await AdminPanel.handle_activate_premium(client, callback)
            elif data == "deactivate_premium":
                await AdminPanel.handle_deactivate_premium(client, callback)
            elif data == "check_premium":
                await AdminPanel.handle_check_premium(client, callback)
            elif data == "premium_plans":
                await AdminPanel.show_premium_plans(client, callback)
            
            # Broadcast
            elif data == "text_broadcast":
                await AdminPanel.handle_broadcast(client, callback)
            elif data == "media_broadcast":
                await AdminPanel.handle_broadcast(client, callback)
            elif data == "stats_broadcast":
                await AdminPanel.handle_stats_broadcast(client, callback)
            elif data == "confirm_stats_broadcast":
                await AdminPanel.process_stats_broadcast(client, callback)
            
            # Search
            elif data == "search_id":
                await AdminPanel._edit_or_reply(
                    callback,
                    "🔎 <b>Search by User ID</b>\n\n"
                    "Enter user ID to search:",
                    reply_markup=AdminPanel.back_button("search_menu")
                )
            
            await callback.answer()
        except Exception as e:
            logger.error(f"Error in admin callback {data}: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)

# ========================
# Command Handlers
# ========================

@Client.on_message(filters.command("admin") & filters.user(ADMIN_USER_ID))
async def admin_command(client: Client, message: Message):
    await AdminPanel.show_main_menu(client, message)

@Client.on_message(filters.command("setcost") & filters.user(ADMIN_USER_ID))
async def set_cost_command(client: Client, message: Message):
    await AdminPanel.process_set_cost(client, message)

@Client.on_message(filters.command("setreferral") & filters.user(ADMIN_USER_ID))
async def set_referral_command(client: Client, message: Message):
    await AdminPanel.process_set_referral(client, message)

@Client.on_message(filters.command("genlink") & filters.user(ADMIN_USER_ID))
async def gen_link_command(client: Client, message: Message):
    await AdminPanel.process_gen_link(client, message)

@Client.on_message(filters.command("addpoints") & filters.user(ADMIN_USER_ID))
async def add_points_command(client: Client, message: Message):
    await AdminPanel.process_add_points(client, message)

@Client.on_message(filters.command("deductpoints") & filters.user(ADMIN_USER_ID))
async def deduct_points_command(client: Client, message: Message):
    await AdminPanel.process_deduct_points(client, message)

@Client.on_message(filters.command("ban") & filters.user(ADMIN_USER_ID))
async def ban_command(client: Client, message: Message):
    await AdminPanel.process_ban_user(client, message)

@Client.on_message(filters.command("unban") & filters.user(ADMIN_USER_ID))
async def unban_command(client: Client, message: Message):
    await AdminPanel.process_unban_user(client, message)

@Client.on_message(filters.command("finduser") & filters.user(ADMIN_USER_ID))
async def find_user_command(client: Client, message: Message):
    await AdminPanel.process_find_user(client, message)

@Client.on_message(filters.command("premium") & filters.user(ADMIN_USER_ID))
async def premium_command(client: Client, message: Message):
    await AdminPanel.process_activate_premium(client, message)

@Client.on_message(filters.command("depremium") & filters.user(ADMIN_USER_ID))
async def deactivate_premium_command(client: Client, message: Message):
    await AdminPanel.process_deactivate_premium(client, message)

@Client.on_message(filters.command("checkpremium") & filters.user(ADMIN_USER_ID))
async def check_premium_command(client: Client, message: Message):
    await AdminPanel.process_check_premium(client, message)

@Client.on_message(filters.command("broadcast") & filters.user(ADMIN_USER_ID))
async def broadcast_command(client: Client, message: Message):
    await AdminPanel.process_broadcast(client, message)

# ========================
# Callback Handlers
# ========================

@Client.on_callback_query(filters.user(ADMIN_USER_ID))
async def handle_admin_callbacks(client: Client, callback: CallbackQuery):
    await AdminPanel.handle_admin_callbacks(client, callback)
