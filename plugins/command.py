# commands.py
import os
import random
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, List
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, ChatWriteForbidden
from config import settings
from scripts import Txt
from helpers.utils import get_random_photo, humanbytes, progress_for_pyrogram
from database.data import hyoshcoder

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self):
        self.ADMIN_USER_ID = settings.ADMIN
        self.emoji = {
            'points': "✨", 'premium': "⭐", 'referral': "👥", 'rename': "📝",
            'stats': "📊", 'leaderboard': "🏆", 'admin': "🛠️", 'success': "✅",
            'error': "❌", 'clock': "⏳", 'link': "🔗", 'money': "💰",
            'file': "📁", 'video': "🎥"
        }
        self.user_locks: Dict[int, asyncio.Lock] = {}

    async def get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create a lock for user to prevent race conditions"""
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        return self.user_locks[user_id]

    async def send_response(self, client: Client, chat_id: int, text: str, 
                          reply_markup=None, delete_after=None, parse_mode=enums.ParseMode.HTML):
        try:
            msg = await client.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            if delete_after:
                asyncio.create_task(self.auto_delete_message(msg, delete_after))
            return msg
        except Exception as e:
            logger.error(f"Response error: {e}")
            try:
                return await client.send_message(
                    chat_id=chat_id,
                    text="An error occurred while processing this message.",
                    parse_mode=None
                )
            except:
                return None

    async def auto_delete_message(self, message: Message, delay: int = 30):
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except:
            pass

    async def handle_start(self, client: Client, message: Message, args: list):
        user = message.from_user
        user_id = user.id
        
        await hyoshcoder.add_user(user_id)
        
        if len(args) > 0:
            if args[0].startswith("refer_"):
                await self.handle_referral(client, user_id, args[0], user)
            elif args[0].startswith("points_"):
                await self.handle_points_link(client, user_id, args[0], message)
        
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
        
        await self.send_response(
            client,
            message.chat.id,
            Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )

    async def handle_referral(self, client: Client, user_id: int, refer_arg: str, user):
        try:
            referrer_id = int(refer_arg.replace("refer_", ""))
            if referrer_id == user_id:
                return
                
            config = await hyoshcoder.get_config("points_config") or {}
            reward = config.get('referral_bonus', 10)
            
            referrer = await hyoshcoder.read_user(referrer_id)
            if referrer:
                await hyoshcoder.set_referrer(user_id, referrer_id)
                await hyoshcoder.add_points(
                    referrer_id, 
                    reward, 
                    "referral", 
                    f"Referral from {user_id}"
                )
                
                caption = (
                    f"🎉 {user.mention} joined through your referral!\n"
                    f"You received {reward} {self.emoji['points']}"
                )
                await self.send_response(client, referrer_id, caption)
        except Exception as e:
            logger.error(f"Referral error: {e}")

    async def handle_points_link(self, client: Client, user_id: int, points_arg: str, message: Message):
        try:
            code = points_arg[7:]
            result = await hyoshcoder.claim_points_link(user_id, code)
            if result["success"]:
                await self.send_response(
                    client,
                    message.chat.id,
                    f"🎉 You claimed {result['points']} {self.emoji['points']}!\n"
                    f"Remaining claims: {result['remaining_claims']}",
                    delete_after=10
                )
            else:
                await message.reply(f"{self.emoji['error']} {result['reason']}")
        except Exception as e:
            logger.error(f"Points claim error: {e}")

    async def handle_help(self, client: Client, message: Message):
        await self.send_response(
            client,
            message.chat.id,
            Txt.HELP_TXT,
            delete_after=60
        )

    async def handle_about(self, client: Client, message: Message):
        await self.send_response(
            client,
            message.chat.id,
            Txt.ABOUT_TXT,
            delete_after=60
        )

    async def handle_thumbnail(self, client: Client, message: Message):
        if message.photo:
            await hyoshcoder.set_thumbnail(message.from_user.id, message.photo.file_id)
            await message.reply("✅ Thumbnail saved successfully!")
        else:
            await message.reply("Please send a photo to set as thumbnail")

    async def handle_view_thumbnail(self, client: Client, message: Message):
        thumb = await hyoshcoder.get_thumbnail(message.from_user.id)
        if thumb:
            await client.send_photo(message.chat.id, thumb, caption="Your current thumbnail")
        else:
            await message.reply("No thumbnail set!")

    async def handle_del_thumbnail(self, client: Client, message: Message):
        await hyoshcoder.set_thumbnail(message.from_user.id, None)
        await message.reply("✅ Thumbnail removed successfully!")

    async def handle_set_caption(self, client: Client, message: Message):
        caption = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else ""
        await hyoshcoder.set_caption(message.from_user.id, caption)
        await message.reply(f"✅ Caption set successfully!\n\n{caption}")

    async def handle_autorename(self, client: Client, message: Message):
        template = message.text.split(" ", 1)[1] if len(message.text.split()) > 1 else ""
        if not template:
            await message.reply("Please provide a template for renaming")
            return
            
        await hyoshcoder.set_format_template(message.from_user.id, template)
        await message.reply(f"✅ Auto-rename template set to:\n\n<code>{template}</code>")

    async def handle_metadata(self, client: Client, message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Usage: /metadata [on/off]")
            return
            
        status = args[1].lower() == "on"
        await hyoshcoder.set_metadata(message.from_user.id, status)
        await message.reply(f"Metadata embedding {'enabled' if status else 'disabled'}")

    async def handle_stats(self, client: Client, message: Message):
        user_id = message.from_user.id
        stats = await hyoshcoder.get_user_stats(user_id)
        
        if not stats:
            await message.reply("Could not fetch your stats")
            return
            
        text = f"""
📊 <b>Your Statistics</b> 📊

🆔 <b>User ID:</b> <code>{user_id}</code>
⭐ <b>Points:</b> {stats.get('points', 0)}
📁 <b>Files Renamed:</b> {stats.get('files_renamed', 0)}
💾 <b>Total Size Processed:</b> {humanbytes(stats.get('total_size', 0))}
🎖️ <b>Premium Status:</b> {'✅ Active' if stats.get('is_premium', False) else '❌ Inactive'}
"""
        await self.send_response(client, message.chat.id, text)

command_handler = CommandHandler()

@Client.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    await command_handler.handle_start(client, message, args)

@Client.on_message(filters.command("help") & filters.private)
async def help(client: Client, message: Message):
    await command_handler.handle_help(client, message)

@Client.on_message(filters.command("about") & filters.private)
async def about(client: Client, message: Message):
    await command_handler.handle_about(client, message)

@Client.on_message(filters.command("thumbnail") & filters.private)
async def thumbnail(client: Client, message: Message):
    await command_handler.handle_thumbnail(client, message)

@Client.on_message(filters.command("view_thumb") & filters.private)
async def view_thumbnail(client: Client, message: Message):
    await command_handler.handle_view_thumbnail(client, message)

@Client.on_message(filters.command("del_thumb") & filters.private)
async def del_thumbnail(client: Client, message: Message):
    await command_handler.handle_del_thumbnail(client, message)

@Client.on_message(filters.command("set_caption") & filters.private)
async def set_caption(client: Client, message: Message):
    await command_handler.handle_set_caption(client, message)

@Client.on_message(filters.command("autorename") & filters.private)
async def autorename(client: Client, message: Message):
    await command_handler.handle_autorename(client, message)

@Client.on_message(filters.command("metadata") & filters.private)
async def metadata(client: Client, message: Message):
    await command_handler.handle_metadata(client, message)

@Client.on_message(filters.command("stats") & filters.private)
async def stats(client: Client, message: Message):
    await command_handler.handle_stats(client, message)
