import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Union
import secrets
import asyncio

from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)
from pyrogram.errors import FloodWait

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
            [InlineKeyboardButton("🔄 Update Config", callback_data="update_config")]
        ])
    
    @staticmethod
    def points_menu() -> InlineKeyboardMarkup:
        """Complete points configuration menu"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Set Rename Cost", callback_data="set_rename_cost")],
            [InlineKeyboardButton("🎁 Referral Bonus", callback_data="set_referral_bonus")],
            [InlineKeyboardButton("📺 Ad Points", callback_data="set_ad_points")],
            [InlineKeyboardButton("🔗 Generate Points Link", callback_data="gen_points_link")],
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
            [InlineKeyboardButton("🔍 Find User", callback_data="find_user")],
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
            [InlineKeyboardButton("📝 Check Status", callback_data="check_premium")],
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
            [InlineKeyboardButton("📊 Stats Only", callback_data="stats_broadcast")],
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
    async def get_points_config() -> dict:
        """Get current points configuration with defaults"""
        config = await hyoshcoder.get_config("points_config", {})
        return config or {
            "rename_cost": 1,
            "referral_bonus": 10,
            "ad_points": {"min": 5, "max": 20, "daily_limit": 5},
            "new_user_balance": 70
        }
    
    @staticmethod
    async def update_config(key: str, value: Any) -> None:
        """Safely update configuration"""
        await hyoshcoder.db.config.update_one(
            {"key": "points_config"},
            {"$set": {f"value.{key}": value}},
            upsert=True
        )
    
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
            num = int(duration_str[:-1])
            if duration_str.endswith('m'):
                return timedelta(minutes=num)
            elif duration_str.endswith('h'):
                return timedelta(hours=num)
            elif duration_str.endswith('d'):
                return timedelta(days=num)
            return timedelta(hours=1)
        except (ValueError, TypeError):
            return timedelta(hours=1)
    
    @staticmethod
    async def _edit_or_reply(
        target: Union[Message, CallbackQuery],
        text: str,
        reply_markup: InlineKeyboardMarkup = None,
        parse_mode: enums.ParseMode = enums.ParseMode.HTML
    ) -> Message:
        """Smart response handler for both messages and callbacks"""
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            await target.answer()
            return target.message
        else:
            return await target.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

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
        config = await AdminPanel.get_points_config()
        
        text = (
            "⚙️ <b>Points Configuration</b>\n\n"
            f"• Rename Cost: {config['rename_cost']} point(s)\n"
            f"• Referral Bonus: {config['referral_bonus']} points\n"
            f"• Ad Points: {config['ad_points']['min']}-{config['ad_points']['max']}\n"
            f"• Daily Ad Limit: {config['ad_points']['daily_limit']}\n"
            f"• New User Balance: {config['new_user_balance']}"
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

    # ========================
    # Action Handlers
    # ========================
    
    @staticmethod
    async def handle_set_rename_cost(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Handle rename cost configuration"""
        return await AdminPanel._edit_or_reply(
            target,
            "💳 <b>Set Rename Cost</b>\n\n"
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
                
            await AdminPanel.update_config("rename_cost", cost)
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Rename cost set to {cost} point(s)",
                reply_markup=AdminPanel.back_button("points_menu")
            )
        except (IndexError, ValueError) as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Invalid input: {str(e)}\n"
                "Usage: <code>/setcost [amount]</code>",
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
    async def handle_add_points(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate add points flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "➕ <b>Add Points</b>\n\n"
            "Enter command:\n"
            "<code>/addpoints user_id amount</code>\n\n"
            "Example: <code>/addpoints 123456 50</code>",
            reply_markup=AdminPanel.back_button("user_menu")
        )
    
    @staticmethod
    async def process_add_points(client: Client, message: Message) -> Message:
        """Process adding points to user"""
        try:
            parts = message.text.split()
            if len(parts) < 3:
                raise ValueError("Missing parameters")
            
            user_id = int(parts[1])
            amount = int(parts[2])
            
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            await hyoshcoder.add_points(user_id, amount, "admin_addition")
            user = await hyoshcoder.get_user(user_id)
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Added {amount} points to user {user_id}\n"
                f"🪙 New balance: {user['points']['balance']}",
                reply_markup=AdminPanel.back_button("user_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/addpoints user_id amount</code>\n"
                "Example: <code>/addpoints 123456 50</code>",
                reply_markup=AdminPanel.back_button("user_menu")
            )
    
    @staticmethod
    async def handle_ban_user(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate user ban flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "🚫 <b>Ban User</b>\n\n"
            "Enter command:\n"
            "<code>/ban user_id reason</code>\n\n"
            "Example: <code>/ban 123456 Spamming</code>",
            reply_markup=AdminPanel.back_button("user_menu")
        )
    
    @staticmethod
    async def process_ban_user(client: Client, message: Message) -> Message:
        """Process banning a user"""
        try:
            parts = message.text.split()
            if len(parts) < 2:
                raise ValueError("Missing user ID")
            
            user_id = int(parts[1])
            reason = ' '.join(parts[2:]) if len(parts) > 2 else "No reason provided"
            
            await hyoshcoder.ban_user(user_id, 30, reason)  # 30 day ban
            
            return await AdminPanel._edit_or_reply(
                message,
                f"✅ Banned user {user_id}\n"
                f"📝 Reason: {reason}",
                reply_markup=AdminPanel.back_button("user_menu")
            )
        except Exception as e:
            return await AdminPanel._edit_or_reply(
                message,
                f"❌ Error: {str(e)}\n\n"
                "Usage: <code>/ban user_id reason</code>\n"
                "Example: <code>/ban 123456 Spamming</code>",
                reply_markup=AdminPanel.back_button("user_menu")
            )
    
    @staticmethod
    async def handle_activate_premium(client: Client, target: Union[Message, CallbackQuery]) -> Message:
        """Initiate premium activation flow"""
        return await AdminPanel._edit_or_reply(
            target,
            "🌟 <b>Activate Premium</b>\n\n"
            "Enter command:\n"
            "<code>/premium user_id duration plan</code>\n\n"
            "Example: <code>/premium 123456 30d gold</code>\n"
            "Duration formats: 7d, 30d, 1y\n"
            "Plan options: basic, premium, gold",
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
    async def handle_broadcast(client: Client, callback: CallbackQuery) -> Message:
        """Initiate broadcast flow"""
        return await AdminPanel._edit_or_reply(
            callback,
            "📢 <b>Broadcast Message</b>\n\n"
            "Enter your broadcast message:\n"
            "(Reply to this message with your content)",
            reply_markup=AdminPanel.back_button("broadcast_menu")
        )
    
    @staticmethod
    async def process_broadcast(client: Client, message: Message) -> Message:
        """Process sending broadcast to all users"""
        try:
            if not message.reply_to_message:
                raise ValueError("You must reply to the broadcast instruction message")
            
            broadcast_msg = message.reply_to_message
            users = await hyoshcoder.get_all_users()
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
                            parse_mode=enums.ParseMode.HTML
                        )
                    else:
                        await broadcast_msg.copy(chat_id=user["_id"])
                    success += 1
                except Exception:
                    failed += 1
                
                if (success + failed) % 10 == 0:
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

# ========================
# Command Handlers
# ========================

@Client.on_message(filters.command("admin") & filters.user(ADMIN_USER_ID))
async def admin_command(client: Client, message: Message):
    await AdminPanel.show_main_menu(client, message)

@Client.on_message(filters.command("setcost") & filters.user(ADMIN_USER_ID))
async def set_cost_command(client: Client, message: Message):
    await AdminPanel.process_set_cost(client, message)

@Client.on_message(filters.command("genlink") & filters.user(ADMIN_USER_ID))
async def gen_link_command(client: Client, message: Message):
    await AdminPanel.process_gen_link(client, message)

@Client.on_message(filters.command("addpoints") & filters.user(ADMIN_USER_ID))
async def add_points_command(client: Client, message: Message):
    await AdminPanel.process_add_points(client, message)

@Client.on_message(filters.command("ban") & filters.user(ADMIN_USER_ID))
async def ban_command(client: Client, message: Message):
    await AdminPanel.process_ban_user(client, message)

@Client.on_message(filters.command("premium") & filters.user(ADMIN_USER_ID))
async def premium_command(client: Client, message: Message):
    await AdminPanel.process_activate_premium(client, message)

# ========================
# Callback Handlers
# ========================

@Client.on_callback_query(filters.user(ADMIN_USER_ID))
async def handle_admin_callbacks(client: Client, callback: CallbackQuery):
    data = callback.data
    
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
    elif data == "set_rename_cost":
        await AdminPanel.handle_set_rename_cost(client, callback)
    elif data == "gen_points_link":
        await AdminPanel.generate_points_link_ui(client, callback)
    elif data == "add_points":
        await AdminPanel.handle_add_points(client, callback)
    elif data == "ban_user":
        await AdminPanel.handle_ban_user(client, callback)
    elif data == "activate_premium":
        await AdminPanel.handle_activate_premium(client, callback)
    elif data == "text_broadcast":
        await AdminPanel.handle_broadcast(client, callback)
    elif data.startswith("del_link_"):
        code = data.split("_")[2]
        await hyoshcoder.point_links.delete_one({"code": code})
        await callback.answer("✅ Link deleted")
        await AdminPanel.show_points_menu(client, callback)
    
    await callback.answer()
