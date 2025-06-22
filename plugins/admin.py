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
            "screenshot_cost": 5,
            "new_user_balance": 70
        },
        "premium_plans": {
            "1day": {"price": 5, "duration": 1, "points": 10000},
            "1week": {"price": 10, "duration": 7, "points": 10000},
            "2weeks": {"price": 15, "duration": 14, "points": 10000},
            "1month": {"price": 30, "duration": 30, "points": 10000}
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
            ],
            [InlineKeyboardButton("❌ Close", callback_data="close_admin")]
        ])
    
    @staticmethod
    def points_menu() -> InlineKeyboardMarkup:
        """Complete points configuration menu"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Set Rename Cost", callback_data="set_rename_cost")],
            [InlineKeyboardButton("📸 Set Screenshot Cost", callback_data="set_screenshot_cost")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main"),
             InlineKeyboardButton("❌ Close", callback_data="close_admin")]
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
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main"),
             InlineKeyboardButton("❌ Close", callback_data="close_admin")]
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
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main"),
             InlineKeyboardButton("❌ Close", callback_data="close_admin")]
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
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main"),
             InlineKeyboardButton("❌ Close", callback_data="close_admin")]
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
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main"),
             InlineKeyboardButton("❌ Close", callback_data="close_admin")]
        ])
    
    @staticmethod
    def back_button(target: str = "admin_main") -> InlineKeyboardMarkup:
        """Dynamic back button"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=target),
             InlineKeyboardButton("❌ Close", callback_data="close_admin")]
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
                ],
                [InlineKeyboardButton("❌ Close", callback_data="close_admin")]
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
            f"• Screenshot Cost: {config.get('screenshot_cost', 5)} points\n"
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
    async def handle_set_screenshot_cost(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Handle screenshot cost configuration"""
        config = await AdminPanel.get_config("points_config")
        current_cost = config.get("screenshot_cost", 5)
        
        return await AdminPanel._edit_or_reply(
            target,
            "📸 <b>Set Screenshot Cost</b>\n\n"
            f"Current cost: {current_cost} points\n\n"
            "Enter new cost (in points):\n"
            "<code>/setscreenshot [amount]</code>\n\n"
            "Example: <code>/setscreenshot 10</code>",
            reply_markup=AdminPanel.back_button("points_menu")
        )
    
    @staticmethod
    async def process_set_screenshot_cost(client: Client, message: Message) -> Message:
        """Process screenshot cost change command"""
        try:
            cost = int(message.text.split()[1])
            if cost < 0:
                raise ValueError("Cost cannot be negative")
                
            success = await AdminPanel.update_config("screenshot_cost", cost)
            if not success:
                raise Exception("Failed to update config")
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Screenshot cost set to {cost} points",
                reply_markup=AdminPanel.back_button("points_menu")
            )
        except (IndexError, ValueError, Exception) as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/setscreenshot [amount]</code>\n"
                "Example: <code>/setscreenshot 10</code>",
                reply_markup=AdminPanel.back_button("points_menu")
            )

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
                [InlineKeyboardButton("🔙 Back", callback_data="user_menu"),
                 InlineKeyboardButton("❌ Close", callback_data="close_admin")]
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
        """Display premium plans with durations and points"""
        plans = await AdminPanel.get_config("premium_plans")
        
        text = "🌟 <b>Premium Plans</b>\n\n"
        for plan, details in plans.items():
            text += (
                f"✨ <b>{plan.capitalize()}</b>\n"
                f"⏳ Duration: {details['duration']} days\n"
                f"🪙 Points: {details['points']} (unlimited during premium)\n"
                f"💰 Price: {details['price']} points\n\n"
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
    async def handle_deactivate_premium(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate premium deactivation flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "❌ <b>Deactivate Premium</b>\n\n"
            "Enter command:\n"
            "<code>/depremium user_id [reason]</code>\n\n"
            "Example: <code>/depremium 123456 \"Violation of terms\"</code>",
            reply_markup=AdminPanel.back_button("premium_menu")
        )
    @staticmethod
    async def process_activate_premium(client: Client, message: Message) -> Message:
        """Process premium activation with unlimited points"""
        try:
            parts = message.text.split()
            if len(parts) < 3:
                raise ValueError("Missing parameters")
            
            user_id = int(parts[1])
            plan = parts[2].lower()  # e.g., "1week"
            reason = parts[3] if len(parts) > 3 else f"{plan} premium activation"
            
            plans = await AdminPanel.get_config("premium_plans")
            if plan not in plans:
                available_plans = ", ".join(plans.keys())
                raise ValueError(f"Invalid plan. Available: {available_plans}")
            
            # Get plan details
            plan_details = plans[plan]
            duration_days = plan_details["duration"]
            premium_points = plan_details["points"]
            
            # Get user's current points to store for later
            user = await hyoshcoder.get_user(user_id)
            if not user:
                raise ValueError("User not found")
            
            original_points = user['points']['balance']
            
            # Activate premium with unlimited points
            await hyoshcoder.activate_premium(
                user_id=user_id,
                plan=plan,
                duration_days=duration_days,
                original_points=original_points,
                premium_points=premium_points,
                reason=reason
            )
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Activated {plan} premium for user {user_id}\n"
                f"⏳ Duration: {duration_days} days\n"
                f"🪙 Points set to: {premium_points}\n"
                f"📝 Reason: {reason}",
                reply_markup=AdminPanel.back_button("premium_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/premium user_id plan [reason]</code>\n"
                "Example: <code>/premium 123456 1week \"Special offer\"</code>",
                reply_markup=AdminPanel.back_button("premium_menu")
            )
        
    @staticmethod
    async def handle_deactivate_premium_menu(client: Client, callback: CallbackQuery) -> Message:
        """Show deactivate premium menu"""
        return await AdminPanel._edit_or_reply(
            callback,
            "❌ <b>Deactivate Premium</b>\n\n"
            "Enter user ID to deactivate premium:\n"
            "<code>/depremium user_id [reason]</code>\n\n"
            "Example: <code>/depremium 123456 \"Violation of terms\"</code>",
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
            reason = parts[2] if len(parts) > 2 else "Admin deactivation"
            
            # Get user's current premium status
            user = await hyoshcoder.get_user(user_id)
            if not user:
                raise ValueError("User not found")
            
            if not user.get("premium", {}).get("is_premium", False):
                return await AdminPanel._edit_or_reply(
                    message,
                    f"ℹ️ User {user_id} doesn't have active premium",
                    reply_markup=AdminPanel.back_button("premium_menu")
                )
            
            # Store original points before deactivation
            original_points = user["premium"].get("original_points", user["points"]["balance"])
            
            # Deactivate premium
            await hyoshcoder.db.users.update_one(
                {"_id": user_id},
                {"$set": {
                    "premium.is_premium": False,
                    "premium.expired_at": datetime.now(),
                    "premium.deactivation_reason": reason,
                    "points.balance": original_points
                }}
            )
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Premium deactivated for user {user_id}\n"
                f"📝 Reason: {reason}\n"
                f"🪙 Points reverted to: {original_points}",
                reply_markup=AdminPanel.back_button("premium_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/depremium user_id [reason]</code>\n"
                "Example: <code>/depremium 123456 \"Violation\"</code>",
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
        """Process premium status check with points info"""
        try:
            user_id = int(message.text.split()[1])
            user = await hyoshcoder.get_user(user_id)
            
            if not user:
                raise ValueError("User not found")
            
            premium = user.get('premium', {})
            points = user.get('points', {})
            
            if premium.get('is_premium'):
                remaining = (premium['expires_at'] - datetime.now()).days
                text = (
                    f"🌟 <b>Premium Status</b> - User {user_id}\n\n"
                    f"✅ Active Premium ({premium.get('plan', 'Unknown')})\n"
                    f"⏳ Days remaining: {remaining}\n"
                    f"💎 Unlimited Points: {points.get('balance', 0)}/{premium.get('premium_points', 0)}\n"
                    f"📅 Original Points: {premium.get('original_points', 0)}"
                )
            else:
                text = (
                    f"🌟 <b>Premium Status</b> - User {user_id}\n\n"
                    f"❌ No active premium\n"
                    f"🪙 Current Points: {points.get('balance', 0)}\n"
                    f"📅 Last Premium: {premium.get('expired_at', 'Never')}"
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
    async def handle_broadcast_menu(client: Client, callback: CallbackQuery) -> Message:
        """Show broadcast options with clear instructions"""
        return await AdminPanel._edit_or_reply(
            callback,
            "📢 <b>Broadcast Message</b>\n\n"
            "1. First, prepare your message (text, photo, video, etc.)\n"
            "2. Reply to that message with <code>/broadcast</code>\n\n"
            "Options:\n"
            "- Add <code>--silent</code> to send silently\n"
            "- Add <code>--pin</code> to pin the message\n"
            "- Add <code>--users</code> to broadcast to users only\n"
            "- Add <code>--groups</code> to broadcast to groups only",
            reply_markup=AdminPanel.back_button("broadcast_menu")
        )
    
    @staticmethod
    async def process_broadcast(client: Client, message: Message) -> Message:
        """Completely rewritten broadcast handler with better reliability"""
        try:
            if not message.reply_to_message:
                raise ValueError("You must reply to a message to broadcast it")
    
            # Parse broadcast options
            broadcast_msg = message.reply_to_message
            options = message.text.lower().split()
            silent = "--silent" in options
            pin_message = "--pin" in options
            users_only = "--users" in options
            groups_only = "--groups" in options
    
            # Get appropriate recipients
            if users_only:
                recipients = await hyoshcoder.get_all_users(filter_banned=True)
            elif groups_only:
                recipients = await hyoshcoder.get_all_groups()
            else:
                recipients = await hyoshcoder.get_all_chats(filter_banned=True)
    
            total = len(recipients)
            if total == 0:
                raise ValueError("No recipients found for broadcast")
    
            # Prepare progress message
            progress_msg = await message.reply_text(
                f"📢 Preparing to broadcast to {total} chats...\n"
                f"🔄 Status: Initializing\n"
                f"✅ Success: 0\n"
                f"❌ Failed: 0\n"
                f"⏳ Progress: 0%"
            )
    
            success = 0
            failed = 0
            start_time = datetime.now()
    
            async def send_to_chat(chat):
                nonlocal success, failed
                try:
                    if broadcast_msg.text:
                        sent_msg = await client.send_message(
                            chat_id=chat["_id"],
                            text=broadcast_msg.text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_notification=silent
                        )
                    else:
                        sent_msg = await broadcast_msg.copy(
                            chat_id=chat["_id"],
                            disable_notification=silent
                        )
    
                    if pin_message:
                        try:
                            await sent_msg.pin(disable_notification=True)
                        except Exception as pin_error:
                            logger.warning(f"Couldn't pin message in {chat['_id']}: {pin_error}")
    
                    success += 1
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await send_to_chat(chat)  # Retry after flood wait
                except (UserIsBlocked, PeerIdInvalid, ChatWriteForbidden):
                    failed += 1
                except Exception as e:
                    logger.error(f"Broadcast error for {chat['_id']}: {e}")
                    failed += 1
    
                # Update progress every 10 messages or when complete
                if (success + failed) % 10 == 0 or (success + failed) == total:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    remaining = (total - (success + failed)) * (elapsed / (success + failed + 1))
                    progress = (success + failed) / total * 100
    
                    try:
                        await progress_msg.edit_text(
                            f"📢 Broadcasting to {total} chats...\n"
                            f"🔄 Status: Active\n"
                            f"✅ Success: {success}\n"
                            f"❌ Failed: {failed}\n"
                            f"⏳ Progress: {progress:.1f}%\n"
                            f"⏱ ETA: {timedelta(seconds=int(remaining))}"
                        )
                    except Exception as e:
                        logger.error(f"Error updating progress: {e}")
    
            # Process broadcasting in batches to avoid flooding
            batch_size = 10
            for i in range(0, total, batch_size):
                batch = recipients[i:i + batch_size]
                await asyncio.gather(*[send_to_chat(chat) for chat in batch])
    
            # Final report
            elapsed_time = datetime.now() - start_time
            success_rate = (success / total) * 100 if total > 0 else 0
    
            final_report = (
                f"📢 <b>Broadcast Complete!</b>\n\n"
                f"⏱ Time taken: {elapsed_time}\n"
                f"👥 Total recipients: {total}\n"
                f"✅ Successfully sent: {success}\n"
                f"❌ Failed to send: {failed}\n"
                f"📊 Success rate: {success_rate:.1f}%"
            )
    
            await progress_msg.edit_text(final_report)
            return await message.reply_text(
                "✅ Broadcast completed successfully!",
                reply_markup=AdminPanel.back_button("broadcast_menu")
            )
    
        except Exception as e:
            logger.error(f"Broadcast error: {e}", exc_info=True)
            error_msg = await message.reply_text(
                f"❌ Broadcast failed: {str(e)}",
                reply_markup=AdminPanel.back_button("broadcast_menu")
            )
            await asyncio.sleep(10)
            await error_msg.delete()
            return None
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
                [InlineKeyboardButton("🔙 Back", callback_data="broadcast_menu"),
                 InlineKeyboardButton("❌ Close", callback_data="close_admin")]
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
    @staticmethod
    async def handle_db_reset(client: Client, callback: CallbackQuery):
        """Handle database reset confirmation"""
        data_parts = callback.data.split("_")
        action = data_parts[0]
        admin_id = int(data_parts[3])
        
        if callback.from_user.id != admin_id:
            await callback.answer("❌ Only the initiating admin can confirm this action!", show_alert=True)
            return

        if action == "cancel":
            await callback.message.edit_text("✅ Database reset cancelled")
            await callback.answer()
            return
            
        await callback.message.edit_text("🔄 Resetting database... This may take a moment")
        
        result = await hyoshcoder.reset_database(admin_id)
        
        if "error" in result:
            await callback.message.edit_text(f"❌ Reset failed: {result['error']}")
        else:
            reset_report = (
                "✅ **Database Reset Complete**\n\n"
                f"🗑 Deleted:\n"
                f"- {result['users_deleted']} users\n"
                f"- {result['files_deleted']} file records\n"
                f"- {result['tokens_deleted']} token links\n\n"
                "The bot now has a fresh database!"
            )
            await callback.message.edit_text(reset_report)
            
        await callback.answer()

    @staticmethod
    async def handle_admin_callbacks(client: Client, callback: CallbackQuery):
        """Updated callback handler with resetdb support"""
        data = callback.data
        
        try:
            # Add this condition to handle resetdb callbacks
            if data.startswith(("confirm_db_reset_", "cancel_db_reset_")):
                await AdminPanel.handle_db_reset(client, callback)
                return
                
            # Keep all your existing conditions
            elif data == "admin_main":
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
            elif data == "close_admin":
                await callback.message.delete()
                return
            
            # Points system
            elif data == "set_rename_cost":
                await AdminPanel.handle_set_rename_cost(client, callback)
            elif data == "set_screenshot_cost":
                await AdminPanel.handle_set_screenshot_cost(client, callback)
            
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
            # Add this empty elif to prevent the indentation error
            elif data.startswith("finduser_"):
                pass  # Or implement the proper handler
            
            await callback.answer()
        except Exception as e:
            logger.error(f"Error in admin callback {data}: {e}")
            await callback.answer("❌ An error occurred", show_alert=True)

# ========================
# Command Handlers
# ========================
@Client.on_message(filters.command("resetdb") & filters.user(ADMIN_USER_ID))
async def reset_database_command(client: Client, message: Message):
    """Admin command to completely reset the database"""
    try:
        confirm_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ CONFIRM RESET", callback_data=f"confirm_db_reset_{message.from_user.id}")],
            [InlineKeyboardButton("Cancel", callback_data=f"cancel_db_reset_{message.from_user.id}")]
        ])

        warning_msg = (
            "🚨 **DATABASE RESET WARNING** 🚨\n\n"
            "This will PERMANENTLY DELETE:\n"
            "- All user accounts\n"
            "- All file statistics\n"
            "- All point tokens\n"
            "- All transaction history\n\n"
            "This action cannot be undone!\n\n"
            "Are you absolutely sure?"
        )

        await message.reply(warning_msg, reply_markup=confirm_buttons)

    except Exception as e:
        logger.error(f"Reset DB command error: {e}")
        await message.reply("❌ Error processing reset command")
@Client.on_message(filters.command("admin") & filters.user(ADMIN_USER_ID))
async def admin_command(client: Client, message: Message):
    await AdminPanel.show_main_menu(client, message)

@Client.on_message(filters.command("setcost") & filters.user(ADMIN_USER_ID))
async def set_cost_command(client: Client, message: Message):
    await AdminPanel.process_set_cost(client, message)

@Client.on_message(filters.command("setscreenshot") & filters.user(ADMIN_USER_ID))
async def set_screenshot_cost_command(client: Client, message: Message):
    await AdminPanel.process_set_screenshot_cost(client, message)

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
    """Handle premium activation command"""
    try:
        parts = message.text.split()
        if len(parts) < 3:
            raise ValueError("Missing parameters. Usage: /premium user_id plan")
        
        user_id = int(parts[1])
        plan = parts[2].lower()
        reason = " ".join(parts[3:]) if len(parts) > 3 else "Admin activation"
        
        plans = await AdminPanel.get_config("premium_plans")
        if plan not in plans:
            raise ValueError(f"Invalid plan. Available: {', '.join(plans.keys())}")
        
        # Get user's current points
        user = await hyoshcoder.get_user(user_id)
        if not user:
            raise ValueError("User not found")
        
        original_points = user['points']['balance']
        premium_points = plans[plan]["points"]
        duration_days = plans[plan]["duration"]
        
        # Activate premium
        await hyoshcoder.activate_premium(
            user_id=user_id,
            plan=plan,
            duration_days=duration_days,
            original_points=original_points,
            premium_points=premium_points
        )
        
        await message.reply_text(
            f"✅ Premium activated for user {user_id}\n"
            f"📝 Plan: {plan} ({duration_days} days)\n"
            f"🪙 Points: {premium_points}\n"
            f"📝 Reason: {reason}",
            reply_markup=AdminPanel.back_button("premium_menu")
        )
        
    except Exception as e:
        await message.reply_text(
            f"❌ Error: {str(e)}\n\n"
            "Usage: <code>/premium user_id plan [reason]</code>\n"
            "Example: <code>/premium 123456 1week \"Special offer\"</code>",
            reply_markup=AdminPanel.back_button("premium_menu")
        )
@Client.on_message(filters.command("depremium") & filters.user(ADMIN_USER_ID))
async def deactivate_premium_command(client: Client, message: Message):
    await AdminPanel.process_deactivate_premium(client, message)

@Client.on_message(filters.command("checkpremium") & filters.user(ADMIN_USER_ID))
async def check_premium_command(client: Client, message: Message):
    """Check premium status for a user"""
    try:
        if len(message.command) < 2:
            raise ValueError("Missing user ID")
        
        user_id = int(message.command[1])
        status = await hyoshcoder.check_premium_status(user_id)
        
        if status["is_premium"]:
            expires_at = status.get("expires_at", "Unknown")
            if isinstance(expires_at, datetime):
                remaining = (expires_at - datetime.now()).days
                expires_text = f"{expires_at} ({remaining} days remaining)"
            else:
                expires_text = str(expires_at)
            
            response = (
                f"🌟 <b>Premium Status</b> for user {user_id}\n\n"
                f"✅ Active: Yes\n"
                f"📝 Plan: {status.get('plan', 'Unknown')}\n"
                f"⏳ Expires: {expires_text}\n"
                f"🪙 Points: {status.get('points', 'Unlimited')}"
            )
        else:
            response = (
                f"🌟 <b>Premium Status</b> for user {user_id}\n\n"
                f"❌ Active: No\n"
                f"📝 Reason: {status.get('reason', 'Unknown')}"
            )
        
        await message.reply_text(response, reply_markup=AdminPanel.back_button("premium_menu"))
        
    except Exception as e:
        await message.reply_text(
            f"❌ Error: {str(e)}\n\n"
            "Usage: <code>/checkpremium user_id</code>\n"
            "Example: <code>/checkpremium 123456</code>",
            reply_markup=AdminPanel.back_button("premium_menu")
        )
    
@Client.on_message(filters.command("broadcast") & filters.user(ADMIN_USER_ID))
async def broadcast_command(client: Client, message: Message):
    """Handle broadcast command"""
    if message.reply_to_message:
        await AdminPanel.process_broadcast(client, message)
    else:
        await AdminPanel.handle_broadcast(client, message)

# ========================
# Callback Handlers
# ========================

@Client.on_callback_query(filters.user(ADMIN_USER_ID))
async def handle_admin_callbacks(client: Client, callback: CallbackQuery):
    await AdminPanel.handle_admin_callbacks(client, callback)
