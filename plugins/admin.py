from database.data import hyoshcoder
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
import os
import sys
import time
import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from config import settings
from helpers.utils import get_random_photo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = settings.ADMIN

# Global state for restart prevention
is_restarting = False

class AdminCommands:
    """Class containing all admin command handlers"""
    
    @staticmethod
    async def _send_response(message: Message, text: str, photo: str = None, delete_after: int = None):
        """Helper method to send responses with optional auto-delete"""
        try:
            if photo:
                msg = await message.reply_photo(photo=photo, caption=text)
            else:
                msg = await message.reply_text(text)
            
            if delete_after:
                asyncio.create_task(AdminCommands._auto_delete_message(msg, delete_after))
            return msg
        except Exception as e:
            logger.error(f"Error sending response: {e}", exc_info=True)
            return None

    @staticmethod
    async def _auto_delete_message(message: Message, delay: int):
        """Auto-delete message after delay"""
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Couldn't delete message: {e}")

    @staticmethod
    async def restart_bot(client: Client, message: Message):
        """Restart the bot"""
        global is_restarting
        if is_restarting:
            return
            
        is_restarting = True
        try:
            caption = "**🔄 Bot is restarting...**\n\nAll processes will be back online shortly."
            img = await get_random_photo()
            
            await AdminCommands._send_response(message, caption, photo=img)
            
            # Give time for message to be delivered
            await asyncio.sleep(2)
            
            await client.stop()
            os.execl(sys.executable, sys.executable, *sys.argv)
            
        except Exception as e:
            logger.error(f"Restart failed: {e}", exc_info=True)
            is_restarting = False
            await AdminCommands._send_response(message, f"❌ Restart failed: {str(e)}")

    @staticmethod
    async def ban_user(client: Client, message: Message):
        """Ban a user from using the bot"""
        if len(message.command) < 4:
            help_text = (
                "**Ban Command Usage:**\n\n"
                "`/ban user_id duration_days reason`\n\n"
                "**Example:**\n"
                "`/ban 1234567 30 Spamming`\n\n"
                "This will ban user with ID 1234567 for 30 days for spamming."
            )
            return await AdminCommands._send_response(message, help_text)

        try:
            user_id = int(message.command[1])
            ban_duration = int(message.command[2])
            ban_reason = ' '.join(message.command[3:])
            
            # Check if user exists
            user = await hyoshcoder.read_user(user_id)
            if not user:
                return await AdminCommands._send_response(message, f"❌ User {user_id} not found in database")

            # Ban the user in database
            await hyoshcoder.ban_user(user_id, ban_duration, ban_reason)
            
            # Notify the banned user
            try:
                ban_notification = (
                    f"🚫 **You have been banned**\n\n"
                    f"**Duration:** {ban_duration} days\n"
                    f"**Reason:** {ban_reason}\n\n"
                    "Contact admin if you think this was a mistake."
                )
                await client.send_message(user_id, ban_notification)
                ban_status = "User notified successfully"
            except Exception as e:
                ban_status = f"Failed to notify user: {str(e)}"
            
            log_msg = (
                f"✅ User {user_id} banned successfully\n"
                f"⏳ Duration: {ban_duration} days\n"
                f"📝 Reason: {ban_reason}\n"
                f"🔔 Status: {ban_status}"
            )
            
            await AdminCommands._send_response(message, log_msg)
            logger.info(log_msg)
            
        except Exception as e:
            error_msg = f"❌ Ban failed: {str(e)}"
            await AdminCommands._send_response(message, error_msg)
            logger.error(error_msg, exc_info=True)

    @staticmethod
    async def unban_user(client: Client, message: Message):
        """Unban a previously banned user"""
        if len(message.command) != 2:
            help_text = (
                "**Unban Command Usage:**\n\n"
                "`/unban user_id`\n\n"
                "**Example:**\n"
                "`/unban 1234567`"
            )
            return await AdminCommands._send_response(message, help_text)

        try:
            user_id = int(message.command[1])
            
            # Check if user is actually banned
            user = await hyoshcoder.read_user(user_id)
            if not user or not user.get('ban_status', {}).get('is_banned'):
                return await AdminCommands._send_response(message, f"ℹ️ User {user_id} is not currently banned")

            # Unban the user
            await hyoshcoder.remove_ban(user_id)
            
            # Notify the unbanned user
            try:
                await client.send_message(user_id, "🎉 Your ban has been lifted!")
                unban_status = "User notified successfully"
            except Exception as e:
                unban_status = f"Failed to notify user: {str(e)}"
            
            log_msg = (
                f"✅ User {user_id} unbanned successfully\n"
                f"🔔 Status: {unban_status}"
            )
            
            await AdminCommands._send_response(message, log_msg)
            logger.info(log_msg)
            
        except Exception as e:
            error_msg = f"❌ Unban failed: {str(e)}"
            await AdminCommands._send_response(message, error_msg)
            logger.error(error_msg, exc_info=True)

    @staticmethod
    async def list_banned_users(message: Message):
        """List all currently banned users"""
        try:
            banned_users = []
            async for user in await hyoshcoder.get_all_banned_users():
                banned_users.append(
                    f"👤 **User ID:** `{user['id']}`\n"
                    f"⏳ **Duration:** {user['ban_status']['ban_duration']} days\n"
                    f"📅 **Banned On:** {user['ban_status']['banned_on']}\n"
                    f"📝 **Reason:** {user['ban_status']['ban_reason']}\n"
                )
            
            if not banned_users:
                return await AdminCommands._send_response(message, "ℹ️ No banned users found.")
            
            response = f"🚫 **Banned Users ({len(banned_users)})**\n\n" + "\n".join(banned_users)
            
            if len(response) > 4000:
                filename = f"banned_users_{datetime.now().strftime('%Y%m%d')}.txt"
                with open(filename, 'w') as f:
                    f.write(response)
                await message.reply_document(filename, caption="List of banned users")
                os.remove(filename)
            else:
                await AdminCommands._send_response(message, response)
                
        except Exception as e:
            error_msg = f"❌ Failed to get banned users: {str(e)}"
            await AdminCommands._send_response(message, error_msg)
            logger.error(error_msg, exc_info=True)

    @staticmethod
    async def broadcast_message(client: Client, message: Message):
        """Broadcast a message to all users"""
        if not message.reply_to_message:
            return await AdminCommands._send_response(message, "Please reply to a message to broadcast it.")
        
        # Confirmation step
        confirm = await AdminCommands._send_response(
            message,
            "⚠️ **Are you sure you want to broadcast this message to all users?**\n\n"
            "This action cannot be undone!",
            delete_after=30
        )
        
        # Add confirmation buttons
        confirm_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, broadcast", callback_data="broadcast_confirm")],
            [InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
        ])
        await confirm.edit_reply_markup(confirm_keyboard)
    @staticmethod  
    async def bot_stats(client: Client, message: Message):
        try:
            if not hyoshcoder or not hyoshcoder.db:
                await message.reply_text("⚠️ Database not initialized")
                return

            total_users = await hyoshcoder.total_users_count()
            await message.reply_text(f"Total users: {total_users}")
        except Exception as e:
            logger.error(f"Error in bot_stats: {e}")
            await message.reply_text("❌ Failed to get stats")
    @staticmethod
    async def execute_broadcast(client: Client, message: Message):
        """Actually execute the broadcast after confirmation"""
        broadcast_msg = message.reply_to_message
        total_users = await hyoshcoder.total_users_count()
        start_time = time.time()

        # Log broadcast start
        await client.send_message(
            settings.LOG_CHANNEL,
            f"📢 Broadcast started by {message.from_user.mention}\n"
            f"Total recipients: {total_users}"
        )
        
        status_msg = await AdminCommands._send_response(
            message,
            "📢 **Broadcast Started**\n\n"
            f"Total Users: {total_users}\n"
            "Completed: 0\n"
            "Success: 0\n"
            "Failed: 0"
        )
        
        success = failed = 0
        async for user in await hyoshcoder.get_all_users():
            try:
                await broadcast_msg.copy(user['_id'])
                success += 1
            except (InputUserDeactivated, UserIsBlocked):
                await hyoshcoder.delete_user(user['_id'])
                failed += 1
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast failed for {user['_id']}: {str(e)}")
            
            # Update status every 20 users
            if (success + failed) % 20 == 0:
                await status_msg.edit_text(
                    "📢 **Broadcast In Progress**\n\n"
                    f"Total Users: {total_users}\n"
                    f"Completed: {success + failed}\n"
                    f"Success: {success}\n"
                    f"Failed: {failed}"
                )
        
        # Final report
        time_taken = str(timedelta(seconds=int(time.time() - start_time)))
        await status_msg.edit_text(
            "✅ **Broadcast Completed**\n\n"
            f"⏱️ Time Taken: {time_taken}\n"
            f"👥 Total Users: {total_users}\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}"
        )
        
        # Log completion
        await client.send_message(
            settings.LOG_CHANNEL,
            f"📢 Broadcast completed\n"
            f"⏱️ Time Taken: {time_taken}\n"
            f"✅ Success: {success}\n"
            f"❌ Failed: {failed}"
        )

    @staticmethod
    async def bot_stats(client: Client, message: Message):
        """Show bot statistics (admin version)"""
        start_time = time.time()
        status_msg = await AdminCommands._send_response(message, "🔄 Gathering bot statistics...")
        
        # Get all stats
        total_users = await hyoshcoder.total_users_count()
        banned_users = await hyoshcoder.total_banned_users_count()
        premium_users = await hyoshcoder.total_premium_users_count()
        daily_active = await hyoshcoder.get_daily_active_users()
        ping_time = (time.time() - start_time) * 1000
        
        await status_msg.edit_text(
            "📊 **Bot Statistics (Admin)**\n\n"
            f"👥 Total Users: {total_users}\n"
            f"🚫 Banned Users: {banned_users}\n"
            f"⭐ Premium Users: {premium_users}\n"
            f"📈 Daily Active Users: {daily_active}\n"
            f"🏓 Ping: {ping_time:.2f} ms"
        )

    @staticmethod
    async def list_users(message: Message):
        """List all bot users"""
        try:
            users = []
            async for user in await hyoshcoder.get_all_users():
                premium_status = "⭐" if user.get('is_premium') else ""
                users.append(f"👤 User ID: `{user['_id']}` {premium_status}")
            
            response = f"👥 **Total Users: {len(users)}**\n\n" + "\n".join(users)
            
            if len(response) > 4000:
                filename = f"users_{datetime.now().strftime('%Y%m%d')}.txt"
                with open(filename, 'w') as f:
                    f.write(response)
                await message.reply_document(filename, caption="List of users")
                os.remove(filename)
            else:
                await AdminCommands._send_response(message, response)
                
        except Exception as e:
            error_msg = f"❌ Failed to get users: {str(e)}"
            await AdminCommands._send_response(message, error_msg)
            logger.error(error_msg, exc_info=True)

@Client.on_message(filters.private & filters.command(
    ["restart", "ban", "unban", "banned_users", "broadcast", "botstats", "users"]
) & filters.user(ADMIN_USER_ID))
async def admin_commands_handler(client: Client, message: Message):
    """Handle all admin commands"""
    command = message.command[0].lower()
    
    try:
        if command == "restart":
            await AdminCommands.restart_bot(client, message)
        elif command == "ban":
            await AdminCommands.ban_user(client, message)
        elif command == "unban":
            await AdminCommands.unban_user(client, message)
        elif command == "banned_users":
            await AdminCommands.list_banned_users(message)
        elif command == "broadcast":
            await AdminCommands.broadcast_message(client, message)
        elif command == "botstats":
            await AdminCommands.bot_stats(client, message)
        elif command == "users":
            await AdminCommands.list_users(message)
            
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await admin_commands_handler(client, message)
    except Exception as e:
        error_msg = f"❌ Admin command failed: {str(e)}"
        await message.reply_text(error_msg, quote=True)
        logger.error(error_msg, exc_info=True)

@Client.on_callback_query(filters.regex(r"^broadcast_(confirm|cancel)$") & filters.user(ADMIN_USER_ID))
async def broadcast_confirmation(client: Client, callback_query: CallbackQuery):
    """Handle broadcast confirmation"""
    try:
        action = callback_query.data.split("_")[1]
        
        if action == "confirm":
            await callback_query.message.edit_text("🚀 Starting broadcast...")
            message = await client.get_messages(
                callback_query.message.chat.id,
                callback_query.message.reply_to_message_id
            )
            await AdminCommands.execute_broadcast(client, message)
        else:
            await callback_query.message.edit_text("❌ Broadcast cancelled")
            await AdminCommands._auto_delete_message(callback_query.message, 5)
            
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Broadcast confirmation error: {e}", exc_info=True)
        await callback_query.answer("An error occurred", show_alert=True)
