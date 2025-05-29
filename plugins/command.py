import random
import asyncio
import logging
import uuid
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto,
    InputMediaAnimation,
    Message 
)
from pyrogram.errors import FloodWait
from config import settings
from scripts import Txt
from helpers.utils import get_random_photo, get_random_animation
from database.data import hyoshcoder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = settings.ADMIN

@Client.on_message(filters.private & filters.command([
    "start", "autorename", "setmedia", "set_caption", "del_caption", "see_caption",
    "view_caption", "viewthumb", "view_thumb", "del_thumb", "delthumb", "metadata",
    "donate", "premium", "plan", "bought", "help", "set_dump", "view_dump", "viewdump",
    "del_dump", "deldump", "profile", "leaderboard", "lb", "freepoints"
]))
async def command_handler(client: Client, message: Message):
    user_id = message.from_user.id
    img = await get_random_photo()
    anim = await get_random_animation()
    
    try:
        cmd = message.command[0].lower()
        args = message.command[1:]

        if cmd == 'start':
            user = message.from_user
            await hyoshcoder.add_user(user_id)
            
            # Send sticker
            m = await message.reply_sticker("CAACAgIAAxkBAALmzGXSSt3ppnOsSl_spnAP8wHC26jpAAJEGQACCOHZSVKp6_XqghKoHgQ")
            await asyncio.sleep(3)
            await m.delete()

            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("MY COMMANDS", callback_data='help')],
                [InlineKeyboardButton("My Stats", callback_data='mystats'),
                 InlineKeyboardButton("Leaderboard", callback_data='leaderboard')],
                [InlineKeyboardButton("Earn Points", callback_data='freepoints'),
                 InlineKeyboardButton("Go Premium", callback_data='premiumx')],
                [InlineKeyboardButton("Updates", url='https://t.me/Raaaaavi'),
                 InlineKeyboardButton("Support", url='https://t.me/Raaaaavi')]
            ])
            
            # Handle referral
            if args and args[0].startswith("refer_"):
                referrer_id = int(args[0].replace("refer_", ""))
                if referrer_id != user_id:
                    await hyoshcoder.set_referrer(user_id, referrer_id)
                    await hyoshcoder.add_points(referrer_id, 10)
                    await client.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 {user.mention} joined through your referral! You received 10 points."
                    )

            # Handle points claim
            if args and args[0].startswith("adds_"):
                unique_code = args[0].replace("adds_", "")
                user_data = await hyoshcoder.get_user_by_code(unique_code)
                if user_data:
                    points = await hyoshcoder.get_expend_points(user_data["_id"])
                    await hyoshcoder.add_points(user_data["_id"], points)
                    await hyoshcoder.set_expend_points(user_data["_id"], 0, None)
                    await client.send_message(
                        chat_id=user_data["_id"],
                        text=f"🎉 You earned {points} points!"
                    )

            if anim:
                await message.reply_animation(
                    animation=anim,
                    caption=Txt.START_TXT.format(user.mention),
                    reply_markup=buttons
                )
            elif img:
                await message.reply_photo(
                    photo=img,
                    caption=Txt.START_TXT.format(user.mention),
                    reply_markup=buttons
                )
            else:
                await message.reply_text(
                    text=Txt.START_TXT.format(user.mention),
                    reply_markup=buttons
                )

        elif cmd == "autorename":
            if len(args) == 0:
                await message.reply_text(
                    "**Please provide a rename template**\n\n"
                    "Example:\n"
                    "`/autorename MyFile_[episode]_[quality]`\n\n"
                    "Available placeholders:\n"
                    "[filename], [size], [duration], [date], [time]"
                )
                return

            format_template = ' '.join(args)
            await hyoshcoder.set_format_template(user_id, format_template)
            reply_text = (
                f"✅ <b>Auto-rename template set!</b>\n\n"
                f"📝 <b>Your template:</b> <code>{format_template}</code>\n\n"
                "Now send me files to rename automatically!"
            )
            await message.reply_text(reply_text)

        elif cmd == "setmedia":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 Document", callback_data="setmedia_document")],
                [InlineKeyboardButton("🎥 Video", callback_data="setmedia_video")]
            ])
            await message.reply_text(
                "**Please select the type of media you want to set:**",
                reply_markup=keyboard
            )

        elif cmd in ["leaderboard", "lb"]:
            leaders = await hyoshcoder.get_leaderboard()
            if not leaders:
                await message.reply_text(
                    "No leaderboard data available yet. Be the first to earn points!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Back", callback_data="help")]
                    ])
                )
                return
            
            text = f"🏆 Weekly Points Leaderboard:\n\n"
            for i, user in enumerate(leaders[:10], 1):
                username = user.get('username', f"User {user['_id']}")
                text += f"{i}. {username} - {user.get('points', 0)} ✨ {'⭐' if user.get('premium', False) else ''}\n"
            
            await message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Daily", callback_data="lb_period_daily"),
                     InlineKeyboardButton("Weekly", callback_data="lb_period_weekly")],
                    [InlineKeyboardButton("Monthly", callback_data="lb_period_monthly"),
                     InlineKeyboardButton("All-Time", callback_data="lb_period_alltime")],
                    [InlineKeyboardButton("Points", callback_data="lb_type_points"),
                     InlineKeyboardButton("Files", callback_data="lb_type_renames"),
                     InlineKeyboardButton("Referrals", callback_data="lb_type_referrals")],
                    [InlineKeyboardButton("Back", callback_data="help")]
                ])
            )

        elif cmd == "freepoints":
            me = await client.get_me()
            unique_code = str(uuid.uuid4())[:8]
            invite_link = f"https://t.me/{me.username}?start=refer_{user_id}"
            points_link = f"https://t.me/{me.username}?start=adds_{unique_code}"
            shortlink = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, points_link)
            
            points = random.randint(5, 20)
            await hyoshcoder.set_expend_points(user_id, points, unique_code)
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("Share Bot", callback_data="invite")],
                [InlineKeyboardButton("Watch Ad", url=shortlink)],
                [InlineKeyboardButton("Back", callback_data="help")]
            ])
            
            caption = (
                "**✨ Free Points System**\n\n"
                "Earn points by helping grow our community:\n\n"
                f"🔹 Share Bot: Get 10 points per referral\n"
                f"🔹 Watch Ads: Earn 5-20 points per ad\n"
                f"⭐ Premium Bonus: 2x points multiplier\n\n"
                f"🎁 You can earn up to {points} points right now!"
            )
            
            await message.reply_text(caption, reply_markup=buttons)

        elif cmd == "set_dump":
            if len(args) == 0:
                await message.reply_text(
                    "Please enter the dump channel ID after the command.\n"
                    "Example: `/set_dump -1001234567890`"
                )
                return

            channel_id = args[0]
            try:
                channel_info = await client.get_chat(channel_id)
                if channel_info:
                    await hyoshcoder.set_user_channel(user_id, channel_id)
                    await message.reply_text(
                        f"**Channel {channel_id} has been set as the dump channel.**"
                    )
            except Exception as e:
                await message.reply_text(
                    f"Error: {e}\n"
                    "Please enter a valid channel ID.\n"
                    "Example: `/set_dump -1001234567890`"
                )

        elif cmd in ["view_dump", "viewdump"]:
            channel_id = await hyoshcoder.get_user_channel(user_id)
            if channel_id:
                await message.reply_text(
                    f"**Current Dump Channel:** {channel_id}"
                )
            else:
                await message.reply_text("No dump channel is currently set.")

        elif cmd in ["del_dump", "deldump"]:
            channel_id = await hyoshcoder.get_user_channel(user_id)
            if channel_id:
                await hyoshcoder.set_user_channel(user_id, None)
                await message.reply_text(
                    f"**Channel {channel_id} has been removed from dump list.**"
                )
            else:
                await message.reply_text("No dump channel is currently set.")

        elif cmd == "help":
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
            
            btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("ᴀᴜᴛᴏʀᴇɴᴀᴍᴇ", callback_data='file_names'),
                 InlineKeyboardButton('ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'),
                 InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ', callback_data='caption')],
                [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='meta'),
                 InlineKeyboardButton('ꜱᴇᴛ ᴍᴇᴅɪᴀ', callback_data='setmedia'),
                 InlineKeyboardButton('ꜱᴇᴛ ᴅᴜᴍᴘ', callback_data='setdump')],
                [InlineKeyboardButton(btn_sec_text, callback_data='sequential'),
                 InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data='premiumx'),
                 InlineKeyboardButton(f'Source: {src_txt}', callback_data='toggle_src')],
                [InlineKeyboardButton('ʜᴏᴍᴇ', callback_data='home')]
            ])
            
            if img:
                await message.reply_photo(
                    photo=img,
                    caption=Txt.HELP_TXT.format(client.mention),
                    reply_markup=buttons
                )
            else:
                await message.reply_text(
                    text=Txt.HELP_TXT.format(client.mention),
                    reply_markup=buttons
                )

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Command error: {e}")
        await message.reply_text("An error occurred. Please try again later.")

@Client.on_message(filters.private & filters.photo)
async def addthumbs(client: Client, message: Message):
    try:
        m = await message.reply_text("Please wait...")
        await hyoshcoder.set_thumbnail(message.from_user.id, message.photo.file_id)
        await m.edit_text("**Thumbnail saved successfully ✅**")
    except Exception as e:
        await message.reply_text(f"❌ Error saving thumbnail: {e}")
