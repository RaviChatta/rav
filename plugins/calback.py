import random
import uuid
import asyncio
import logging
import html
from urllib.parse import quote
from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto,
    Message
)
from typing import Optional, Dict, Union
from pyrogram.errors import FloodWait, ChatWriteForbidden
from helpers.utils import get_random_photo, get_shortlink
from scripts import Txt
from database.data import hyoshcoder
from config import settings

logger = logging.getLogger(__name__)

class CallbackHandler:
    def __init__(self):
        self.pending_renames: Dict[int, Dict] = {}
        self.pending_manual_renames: Dict[int, Dict] = {}
        self.user_locks: Dict[int, asyncio.Lock] = {}

    async def get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create a lock for user to prevent race conditions"""
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        return self.user_locks[user_id]

    async def handle_callback(self, client: Client, query: CallbackQuery):
        """Main callback handler for all button presses"""
        data = query.data
        user_id = query.from_user.id
        
        try:
            await query.answer()
            
            if data == "home":
                await self.show_home(client, query)
            elif data == "help":
                await self.show_help(client, query, user_id)
            elif data == "mystats":
                await self.show_stats(client, query, user_id)
            elif data in ["thumbnail", "showThumb"]:
                await self.handle_thumbnail(client, query, user_id, data)
            elif data in ["sequential", "toggle_src", "toggle_auto_rename"]:
                await self.handle_toggles(client, query, user_id, data)
            elif data == "close":
                await self.close_message(query)
            elif data.startswith("cancel_"):
                await self.cancel_operation(client, query, user_id, data)
            elif data.startswith("rename_"):
                await self.handle_manual_rename(client, query, user_id, data)
            elif data == "freepoints":
                await self.handle_free_points(client, query, user_id)
            elif data == "leaderboard":
                await self.show_leaderboard(client, query)
            elif data == "about":
                await self.show_about(client, query)
            elif data == "source":
                await self.show_source(client, query)
            else:
                await query.answer("Button not implemented yet", show_alert=True)
                
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await self.handle_callback(client, query)
        except Exception as e:
            logger.error(f"Callback error: {e}", exc_info=True)
            await query.answer("❌ An error occurred", show_alert=True)

    async def show_home(self, client: Client, query: CallbackQuery):
        """Show home menu with all main options"""
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ My Commands ✨", callback_data='help')],
            [
                InlineKeyboardButton("💎 My Stats", callback_data='mystats'),
                InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard')
            ],
            [
                InlineKeyboardButton("🆕 Updates", url='https://t.me/Raaaaavi'),
                InlineKeyboardButton("🛟 Support", url='https://t.me/Raaaaavi')
            ],
            [
                InlineKeyboardButton("📜 About", callback_data='about'),
                InlineKeyboardButton("🧑‍💻 Source", callback_data='source')
            ]
        ])
        
        await query.message.edit_text(
            Txt.START_TXT.format(query.from_user.mention),
            reply_markup=buttons,
            disable_web_page_preview=True
        )

    async def show_help(self, client: Client, query: CallbackQuery, user_id: int):
        """Show help menu with all available commands and current settings"""
        async with await self.get_user_lock(user_id):
            try:
                sequential_status = await hyoshcoder.get_sequential_mode(user_id)
                src_info = await hyoshcoder.get_src_info(user_id)
                auto_rename_status = await hyoshcoder.get_auto_rename_status(user_id)
                
                btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
                src_txt = "File name" if src_info == "file_name" else "File caption"
                auto_rename_text = "Auto-Rename ✅" if auto_rename_status else "Auto-Rename ❌"

                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("• Automatic Renaming Format •", callback_data='file_names')],
                    [
                        InlineKeyboardButton('• Thumbnail', callback_data='thumbnail'), 
                        InlineKeyboardButton('Caption •', callback_data='caption')
                    ],
                    [
                        InlineKeyboardButton('• Metadata', callback_data='meta'), 
                        InlineKeyboardButton('Set Media •', callback_data='setmedia')
                    ],
                    [
                        InlineKeyboardButton('• Set Dump', callback_data='setdump'), 
                        InlineKeyboardButton('View Dump •', callback_data='viewdump')
                    ],
                    [
                        InlineKeyboardButton(f'• {btn_sec_text}', callback_data='sequential'), 
                        InlineKeyboardButton('Premium •', callback_data='premiumx')
                    ],
                    [
                        InlineKeyboardButton(f'• Extract from: {src_txt}', callback_data='toggle_src'),
                        InlineKeyboardButton(f'• {auto_rename_text}', callback_data='toggle_auto_rename')
                    ],
                    [InlineKeyboardButton('• Home', callback_data='home')]
                ])
                
                await query.message.edit_text(
                    Txt.HELP_TXT.format((await client.get_me()).mention),
                    reply_markup=buttons,
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Error showing help menu: {e}")
                await query.answer("❌ Failed to load help menu", show_alert=True)

    async def handle_toggles(self, client: Client, query: CallbackQuery, user_id: int, data: str):
        """Handle all toggle buttons (sequential, src info, auto-rename)"""
        async with await self.get_user_lock(user_id):
            try:
                if data == "sequential":
                    new_status = await hyoshcoder.toggle_sequential_mode(user_id)
                    status_text = "ON" if new_status else "OFF"
                    await query.answer(f"Sequential mode turned {status_text}", show_alert=True)
                elif data == "toggle_src":
                    new_src = await hyoshcoder.toggle_src_info(user_id)
                    src_text = "File name" if new_src == "file_name" else "File caption"
                    await query.answer(f"Now extracting from: {src_text}", show_alert=True)
                elif data == "toggle_auto_rename":
                    new_status = await hyoshcoder.toggle_auto_rename(user_id)
                    status_text = "ON" if new_status else "OFF"
                    await query.answer(f"Auto-rename turned {status_text}", show_alert=True)
                
                # Refresh help menu to show updated status
                await self.show_help(client, query, user_id)
            except Exception as e:
                logger.error(f"Toggle error: {e}")
                await query.answer("❌ Failed to update setting", show_alert=True)

    async def cancel_operation(self, client: Client, query: CallbackQuery, user_id: int, data: str):
        """Cancel any pending rename operation"""
        try:
            file_id = data.split("_", 1)[1]
            if user_id in self.pending_renames and self.pending_renames[user_id].get("file_id") == file_id:
                del self.pending_renames[user_id]
            if user_id in self.pending_manual_renames and self.pending_manual_renames[user_id].get("file_id") == file_id:
                del self.pending_manual_renames[user_id]
            
            await query.message.edit_text("❌ Processing cancelled by user")
        except Exception as e:
            logger.error(f"Cancel error: {e}")
            await query.answer("❌ Failed to cancel operation", show_alert=True)

    async def handle_manual_rename(self, client: Client, query: CallbackQuery, user_id: int, data: str):
        """Handle manual rename when auto-rename is off"""
        try:
            file_id = data.split("_", 1)[1]
            
            # Check if user has sufficient points
            points_config = await hyoshcoder.get_config("points_config") or {}
            points_per_rename = points_config.get("per_rename", 2)
            current_points = await hyoshcoder.get_points(user_id)
            
            premium_status = await hyoshcoder.check_premium_status(user_id)
            if not premium_status.get("is_premium", False) and current_points < points_per_rename:
                await query.answer(
                    f"❌ Insufficient points! Each rename costs {points_per_rename} points\n"
                    f"Your balance: {current_points} points",
                    show_alert=True
                )
                return
            
            # Store pending rename operation
            self.pending_manual_renames[user_id] = {
                "file_id": file_id,
                "callback_message": query.message,
                "points_deducted": False
            }
            
            await query.message.edit_text(
                "📝 Please send me the new filename for this file:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{file_id}")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Manual rename setup error: {e}")
            await query.answer("❌ Failed to setup rename", show_alert=True)

    async def handle_manual_rename_input(self, client: Client, message: Message):
        """Process manual rename filename input from user"""
        user_id = message.from_user.id
        
        if user_id not in self.pending_manual_renames:
            return
            
        rename_data = self.pending_manual_renames[user_id]
        file_id = rename_data["file_id"]
        callback_msg = rename_data["callback_message"]
        
        try:
            new_name = message.text.strip()
            if len(new_name) > 100:
                raise ValueError("Filename too long (max 100 chars)")
            if not new_name:
                raise ValueError("Filename cannot be empty")
            
            # Get the original message with the file
            original_msg = await client.get_messages(user_id, message_ids=int(file_id))
            if not original_msg or not (original_msg.document or original_msg.video or original_msg.audio):
                raise ValueError("Original file message not found")
            
            # Process points deduction if not already done
            if not rename_data.get("points_deducted", False):
                points_config = await hyoshcoder.get_config("points_config") or {}
                points_per_rename = points_config.get("per_rename", 2)
                
                premium_status = await hyoshcoder.check_premium_status(user_id)
                if not premium_status.get("is_premium", False):
                    await hyoshcoder.deduct_points(user_id, points_per_rename, "manual_rename")
                
                rename_data["points_deducted"] = True
            
            # Process the rename (implement your file processing logic here)
            # This would involve:
            # 1. Downloading the file
            # 2. Renaming it
            # 3. Uploading back to user
            # 4. Tracking in database
            
            original_name = original_msg.document.file_name if original_msg.document else (
                original_msg.video.file_name if original_msg.video else (
                    original_msg.audio.file_name if original_msg.audio else "unknown"
                )
            )
            
            await callback_msg.edit_text(f"✅ File renamed from {original_name} to: {new_name}")
            
            # Track the rename in database
            await hyoshcoder.track_file_rename(
                user_id=user_id,
                original_name=original_name,
                new_name=new_name,
                file_type=(
                    "document" if original_msg.document else 
                    "video" if original_msg.video else 
                    "audio"
                ),
                file_size=(
                    original_msg.document.file_size if original_msg.document else 
                    original_msg.video.file_size if original_msg.video else 
                    original_msg.audio.file_size if original_msg.audio else 0
                )
            )
            
        except Exception as e:
            logger.error(f"Manual rename error: {e}")
            await callback_msg.edit_text(f"❌ Rename failed: {str(e)}")
            
            # Refund points if deduction was made but rename failed
            if rename_data.get("points_deducted", False):
                try:
                    points_config = await hyoshcoder.get_config("points_config") or {}
                    points_per_rename = points_config.get("per_rename", 2)
                    await hyoshcoder.add_points(user_id, points_per_rename, "rename_failed_refund")
                except Exception as refund_error:
                    logger.error(f"Failed to refund points: {refund_error}")
        finally:
            if user_id in self.pending_manual_renames:
                del self.pending_manual_renames[user_id]
            try:
                await message.delete()
            except:
                pass

    async def show_stats(self, client: Client, query: CallbackQuery, user_id: int):
        """Show user statistics"""
        try:
            user_data = await hyoshcoder.get_user_stats(user_id)
            if not user_data:
                raise ValueError("User data not found")
            
            text = f"""
📊 <b>Your Statistics</b> 📊

🆔 <b>User ID:</b> <code>{user_id}</code>
⭐ <b>Points:</b> {user_data.get('points', 0)}
📁 <b>Files Renamed:</b> {user_data.get('files_renamed', 0)}
💾 <b>Total Size Processed:</b> {humanbytes(user_data.get('total_size', 0))}
🎖️ <b>Premium Status:</b> {'✅ Active' if user_data.get('is_premium', False) else '❌ Inactive'}
📅 <b>Account Created:</b> {user_data.get('join_date', 'Unknown')}
"""
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="home")],
                [InlineKeyboardButton("🆓 Get Free Points", callback_data="freepoints")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
        except Exception as e:
            logger.error(f"Stats error: {e}")
            await query.answer("❌ Failed to load stats", show_alert=True)

    async def handle_free_points(self, client: Client, query: CallbackQuery, user_id: int):
        """Handle free points claim"""
        try:
            last_claim = await hyoshcoder.get_last_free_points_claim(user_id)
            if last_claim and (datetime.now() - last_claim).total_seconds() < 86400:  # 24 hours
                await query.answer("❌ You can only claim free points once every 24 hours", show_alert=True)
                return
                
            points_to_add = random.randint(5, 15)
            await hyoshcoder.add_points(user_id, points_to_add, "free_points")
            await hyoshcoder.update_last_free_points_claim(user_id)
            
            await query.answer(f"🎉 You received {points_to_add} free points!", show_alert=True)
            await self.show_stats(client, query, user_id)
        except Exception as e:
            logger.error(f"Free points error: {e}")
            await query.answer("❌ Failed to claim points", show_alert=True)

    async def show_leaderboard(self, client: Client, query: CallbackQuery):
        """Show top users leaderboard"""
        try:
            top_users = await hyoshcoder.get_top_users(limit=10)
            if not top_users:
                raise ValueError("No leaderboard data available")
            
            text = "🏆 <b>Top Users Leaderboard</b> 🏆\n\n"
            for idx, user in enumerate(top_users, 1):
                user_name = html.escape(user.get("name", f"User {user['user_id']}"))
                text += (
                    f"{idx}. {user_name} - {user.get('points', 0)} points\n"
                    f"   📁 Files: {user.get('files_renamed', 0)} | "
                    f"💾 Size: {humanbytes(user.get('total_size', 0))}\n\n"
                )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="home")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="leaderboard")]
            ])
            
            await query.message.edit_text(text, reply_markup=buttons)
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            await query.answer("❌ Failed to load leaderboard", show_alert=True)

    async def close_message(self, query: CallbackQuery):
        """Delete the message"""
        try:
            await query.message.delete()
        except:
            pass

    async def show_about(self, client: Client, query: CallbackQuery):
        """Show about information"""
        await query.message.edit_text(
            Txt.ABOUT_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="home")]
            ]),
            disable_web_page_preview=True
        )

    async def show_source(self, client: Client, query: CallbackQuery):
        """Show source code information"""
        await query.message.edit_text(
            Txt.SOURCE_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="home")]
            ]),
            disable_web_page_preview=True
        )

# Initialize handler
callback_handler = CallbackHandler()

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    await callback_handler.handle_callback(client, query)

@Client.on_message(filters.private & filters.text & ~filters.command)
async def handle_manual_rename_text(client: Client, message: Message):
    await callback_handler.handle_manual_rename_input(client, message)
