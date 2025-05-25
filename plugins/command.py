import os
import random
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from pyrogram.errors import FloodWait, ChatWriteForbidden
from config import settings
from scripts import Txt
from helpers.utils import get_random_photo, get_random_animation, humanbytes
from database.data import hyoshcoder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class CommandHandler:
    def __init__(self):
        self.ADMIN_USER_ID = settings.ADMIN
        self.AUTO_DELETE_DELAY = 30  # Seconds before auto-deleting messages
        self.emoji = {
            'points': "✨",
            'premium': "⭐",
            'referral': "👥",
            'rename': "📝",
            'stats': "📊",
            'leaderboard': "🏆",
            'admin': "🛠️",
            'success': "✅",
            'error': "❌",
            'clock': "⏳",
            'link': "🔗",
            'money': "💰",
            'file': "📁",
            'video': "🎥"
        }
        self.user_locks: Dict[int, asyncio.Lock] = {}

    async def get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create a lock for user to prevent race conditions"""
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        return self.user_locks[user_id]

    async def auto_delete_message(self, message: Message, delay: int = None):
        """Auto-delete message after delay"""
        delay = delay or self.AUTO_DELETE_DELAY
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Couldn't delete message: {e}")

    async def send_response(
        self,
        client: Client,
        chat_id: int,
        text: str,
        reply_markup=None,
        photo=None,
        animation=None,
        delete_after: Optional[int] = None,
        parse_mode: enums.ParseMode = enums.ParseMode.HTML
    ) -> Optional[Message]:
        """Send response with auto-delete and media support"""
        try:
            if animation:
                msg = await client.send_animation(
                    chat_id=chat_id,
                    animation=animation,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            elif photo:
                msg = await client.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            else:
                msg = await client.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True
                )
            
            if delete_after is not None:
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

    def get_leaderboard_keyboard(self, selected_period="weekly", selected_type="points"):
        """Generate leaderboard navigation keyboard"""
        periods = {
            "daily": f"{self.emoji['clock']} Daily",
            "weekly": f"📆 Weekly",
            "monthly": f"🗓 Monthly",
            "alltime": f"{self.emoji['leaderboard']} All-Time"
        }
        types = {
            "points": f"{self.emoji['points']} Points",
            "renames": f"{self.emoji['rename']} Files",
            "referrals": f"{self.emoji['referral']} Referrals"
        }
        
        period_buttons = [
            InlineKeyboardButton(
                f"• {text} •" if period == selected_period else text,
                callback_data=f"lb_period_{period}"
            ) for period, text in periods.items()
        ]
        
        type_buttons = [
            InlineKeyboardButton(
                f"• {text} •" if lb_type == selected_type else text,
                callback_data=f"lb_type_{lb_type}"
            ) for lb_type, text in types.items()
        ]
        
        return InlineKeyboardMarkup([
            period_buttons[:2],
            period_buttons[2:],
            type_buttons,
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ])

    async def handle_start(self, client: Client, message: Message, args: list):
        """Handle /start command with all its features"""
        user = message.from_user
        user_id = user.id
        
        # Add user to database if not exists
        await hyoshcoder.add_user(user_id)
        
        # Welcome message
        welcome_msg = await self.send_response(
            client,
            message.chat.id,
            f"✨ Welcome {user.mention} to our file renaming bot!",
            delete_after=10
        )
        
        # Send sticker
        sticker = await message.reply_sticker("CAACAgIAAxkBAALmzGXSSt3ppnOsSl_spnAP8wHC26jpAAJEGQACCOHZSVKp6_XqghKoHgQ")
        asyncio.create_task(self.auto_delete_message(sticker, delay=3))
        
        # Handle referral links
        if len(args) > 0:
            if args[0].startswith("refer_"):
                await self.handle_referral(client, user_id, args[0], user)
            elif args[0].startswith("points_"):
                await self.handle_points_link(client, user_id, args[0], message)
        
        # Custom start buttons
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
        
        # Send start message with media
        img = await get_random_photo()
        animation = await get_random_animation()
        
        await self.send_response(
            client,
            message.chat.id,
            Txt.START_TXT.format(user.mention),
            reply_markup=buttons,
            photo=img,
            animation=animation,
            delete_after=None  # Don't auto-delete start message
        )

    async def handle_referral(self, client: Client, user_id: int, refer_arg: str, user):
        """Handle referral link processing"""
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
                
                # Notify referrer
                caption = (
                    f"🎉 {user.mention} joined through your referral!\n"
                    f"You received {reward} {self.emoji['points']}"
                )
                await self.send_response(client, referrer_id, caption)
        except Exception as e:
            logger.error(f"Referral error: {e}")

    async def handle_points_link(self, client: Client, user_id: int, points_arg: str, message: Message):
        """Handle points link claims"""
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

    async def handle_leaderboard(self, client: Client, message: Message):
        """Handle leaderboard command"""
        try:
            keyboard = self.get_leaderboard_keyboard()
            leaders = await hyoshcoder.get_leaderboard()
            
            if not leaders:
                return await self.send_response(
                    client,
                    message.chat.id,
                    "No leaderboard data available yet. Be the first to earn points!",
                    reply_markup=keyboard,
                    photo=await get_random_photo(),
                    delete_after=120
                )
            
            text = f"{self.emoji['leaderboard']} Weekly Points Leaderboard:\n\n"
            for i, user in enumerate(leaders[:10], 1):
                username = user.get('username', f"User {user['_id']}")
                text += (
                    f"{i}. {username} - "
                    f"{user.get('points', {}).get('balance', 0)} {self.emoji['points']} "
                    f"{self.emoji['premium'] if user.get('premium', {}).get('is_premium', False) else ''}\n"
                )
            
            await self.send_response(
                client,
                message.chat.id,
                text,
                reply_markup=keyboard,
                photo=await get_random_photo(),
                animation=await get_random_animation(),
                delete_after=120
            )
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} Couldn't load leaderboard. Please try again later.",
                delete_after=15
            )

    async def handle_stats(self, client: Client, message: Message, user_id: int):
        """Handle user statistics command"""
        try:
            stats = await hyoshcoder.get_user_file_stats(user_id)
            points = await hyoshcoder.get_points(user_id)
            premium_status = await hyoshcoder.check_premium_status(user_id)
            user_data = await hyoshcoder.read_user(user_id)
            referral_stats = user_data.get('referral', {})
            
            text = (
                f"📊 <b>Your Statistics</b>\n\n"
                f"{self.emoji['points']} <b>Points Balance:</b> {points}\n"
                f"{self.emoji['premium']} <b>Premium Status:</b> {'Active ' + self.emoji['success'] if premium_status.get('is_premium', False) else 'Inactive ' + self.emoji['error']}\n"
                f"{self.emoji['referral']} <b>Referrals:</b> {referral_stats.get('referred_count', 0)} "
                f"(Earned {referral_stats.get('referral_earnings', 0)} {self.emoji['points']})\n\n"
                f"{self.emoji['rename']} <b>Files Renamed</b>\n"
                f"• Total: {stats.get('total_renamed', 0)}\n"
                f"• Today: {stats.get('today', 0)}\n"
                f"• This Week: {stats.get('this_week', 0)}\n"
                f"• This Month: {stats.get('this_month', 0)}\n"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{self.emoji['leaderboard']} Leaderboard", callback_data="leaderboard")],
                [InlineKeyboardButton(f"{self.emoji['referral']} Invite Friends", callback_data="invite")],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            await self.send_response(
                client,
                message.chat.id,
                text,
                reply_markup=buttons,
                photo=await get_random_photo(),
                delete_after=90
            )
        except Exception as e:
            logger.error(f"Stats error: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} Couldn't load your stats. Please try again later.",
                delete_after=15
            )

    async def handle_autorename(self, client: Client, message: Message, user_id: int, args: list):
        """Handle auto-rename template setting"""
        try:
            config = await hyoshcoder.get_config("points_config") or {}
            points_per_rename = config.get('per_rename', 2)
            current_points = await hyoshcoder.get_points(user_id)
            
            if len(args) < 1:
                caption = (
                    f"{self.emoji['error']} <b>Please provide a rename template</b>\n\n"
                    "Example:\n"
                    "<code>/autorename MyFile_[episode]_[quality]</code>\n\n"
                    "Available placeholders:\n"
                    "[filename], [size], [duration], [date], [time]"
                )
                await self.send_response(client, message.chat.id, caption, delete_after=30)
                return

            format_template = ' '.join(args)
            if len(format_template) > 200:
                raise ValueError("Template too long (max 200 chars)")

            await hyoshcoder.set_format_template(user_id, format_template)
            
            caption = (
                f"{self.emoji['success']} <b>Auto-rename template set!</b>\n\n"
                f"📝 <b>Your template:</b> <code>{format_template}</code>\n\n"
                "Now send me files to rename automatically!"
            )
            
            await self.send_response(client, message.chat.id, caption, delete_after=30)
        except ValueError as e:
            await self.send_response(client, message.chat.id, f"{self.emoji['error']} {str(e)}", delete_after=15)
        except Exception as e:
            logger.error(f"Autorename error: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} Failed to set rename template. Please try again.",
                delete_after=15
            )

    async def handle_caption(self, client: Client, message: Message, user_id: int, args: list, action: str):
        """Handle caption related commands (set/del/view)"""
        try:
            if action == "set":
                if len(args) == 0:
                    caption = (
                        "**Provide the caption\n\nExample : `/set_caption 📕Name ➠ : {filename} \n\n"
                        "🔗 Size ➠ : {filesize} \n\n⏰ Duration ➠ : {duration}`**"
                    )
                    await self.send_response(client, message.chat.id, caption, delete_after=30)
                    return
                
                new_caption = ' '.join(args)
                if len(new_caption) > 500:
                    raise ValueError("Caption too long (max 500 chars)")
                
                await hyoshcoder.set_caption(user_id, caption=new_caption)
                caption = "**Your caption has been saved successfully ✅**"
                await self.send_response(
                    client,
                    message.chat.id,
                    caption,
                    photo=await get_random_photo(),
                    delete_after=30
                )
                    
            elif action == "del":
                old_caption = await hyoshcoder.get_caption(user_id)
                if not old_caption:
                    caption = "**You don't have any caption ❌**"
                    await self.send_response(client, message.chat.id, caption, delete_after=15)
                    return
                
                await hyoshcoder.set_caption(user_id, caption=None)
                caption = "**Your caption has been successfully deleted 🗑️**"
                await self.send_response(
                    client,
                    message.chat.id,
                    caption,
                    photo=await get_random_photo(),
                    delete_after=30
                )
                
            elif action in ["see", "view"]:
                old_caption = await hyoshcoder.get_caption(user_id)
                if old_caption:
                    caption = f"**Your caption:**\n\n`{old_caption}`"
                else:
                    caption = "**You don't have any caption ❌**"
                await self.send_response(
                    client,
                    message.chat.id,
                    caption,
                    photo=await get_random_photo(),
                    delete_after=30
                )
                
        except ValueError as e:
            await self.send_response(client, message.chat.id, f"{self.emoji['error']} {str(e)}", delete_after=15)
        except Exception as e:
            logger.error(f"Caption error: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} Failed to process caption",
                delete_after=15
            )

    async def handle_thumbnail(self, client: Client, message: Message, user_id: int, action: str):
        """Handle thumbnail related commands (view/del)"""
        try:
            if action == "view":
                thumb = await hyoshcoder.get_thumbnail(user_id)
                if thumb:
                    await client.send_photo(chat_id=message.chat.id, photo=thumb)
                else:
                    caption = "**You don't have any thumbnail ❌**"
                    await self.send_response(
                        client,
                        message.chat.id,
                        caption,
                        photo=await get_random_photo(),
                        delete_after=30
                    )
            elif action == "del":
                old_thumb = await hyoshcoder.get_thumbnail(user_id)
                if not old_thumb:
                    caption = "No thumbnail is currently set."
                    await self.send_response(
                        client,
                        message.chat.id,
                        caption,
                        photo=await get_random_photo(),
                        delete_after=30
                    )
                    return

                await hyoshcoder.set_thumbnail(user_id, file_id=None)
                caption = "**Thumbnail successfully deleted 🗑️**"
                await self.send_response(
                    client,
                    message.chat.id,
                    caption,
                    photo=await get_random_photo(),
                    delete_after=30
                )
        except Exception as e:
            logger.error(f"Thumbnail error: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} Failed to process thumbnail",
                delete_after=15
            )

    async def handle_dump(self, client: Client, message: Message, user_id: int, args: list, action: str):
        """Handle dump channel related commands (set/view/del)"""
        try:
            if action == "set":
                if len(args) == 0:
                    caption = "Please enter the dump channel ID after the command.\nExample: `/set_dump -1001234567890`"
                    await self.send_response(client, message.chat.id, caption, delete_after=30)
                    return
                
                channel_id = args[0]
                channel_info = await client.get_chat(channel_id)
                if channel_info:
                    await hyoshcoder.set_user_channel(user_id, channel_id)
                    caption = f"**Channel {channel_id} has been set as the dump channel.**"
                    await self.send_response(client, message.chat.id, caption, delete_after=30)
                else:
                    caption = "The specified channel doesn't exist or is not accessible.\nMake sure I'm an admin in the channel."
                    await self.send_response(client, message.chat.id, caption, delete_after=30)
                    
            elif action == "view":
                channel_id = await hyoshcoder.get_user_channel(user_id)
                if channel_id:
                    caption = f"**Channel {channel_id} is currently set as the dump channel.**"
                else:
                    caption = "**No dump channel is currently set.**"
                await self.send_response(client, message.chat.id, caption, delete_after=30)
                
            elif action == "del":
                channel_id = await hyoshcoder.get_user_channel(user_id)
                if channel_id:
                    await hyoshcoder.set_user_channel(user_id, None)
                    caption = f"**Channel {channel_id} has been removed from the dump list.**"
                else:
                    caption = "**No dump channel is currently set.**"
                await self.send_response(client, message.chat.id, caption, delete_after=30)
                
        except Exception as e:
            logger.error(f"Dump channel error: {e}")
            caption = f"Error: {str(e)}. Please enter a valid channel ID.\nExample: `/set_dump -1001234567890`"
            await self.send_response(client, message.chat.id, caption, delete_after=30)

    async def handle_premium(self, client: Client, message: Message, cmd: str):
        """Handle premium related commands"""
        try:
            if cmd == "donate":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="Back", callback_data="help"),
                     InlineKeyboardButton(text="Owner", url='https://t.me/hyoshassistantBot')]
                ])
                await self.send_response(
                    client,
                    message.chat.id,
                    Txt.DONATE_TXT,
                    reply_markup=buttons,
                    photo=await get_random_photo(),
                    delete_after=300
                )
            elif cmd == "premium":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Owner", url="https://t.me/hyoshassistantBot"),
                     InlineKeyboardButton("Close", callback_data="close")]
                ])
                await self.send_response(
                    client,
                    message.chat.id,
                    Txt.PREMIUM_TXT,
                    reply_markup=buttons,
                    photo=await get_random_photo(),
                    delete_after=300
                )
            elif cmd == "plan":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Pay Your Subscription", url="https://t.me/hyoshassistantBot"),
                     InlineKeyboardButton("Close", callback_data="close")]
                ])
                await self.send_response(
                    client,
                    message.chat.id,
                    Txt.PREPLANS_TXT,
                    reply_markup=buttons,
                    photo=await get_random_photo(),
                    delete_after=300
                )
            elif cmd == "bought":
                msg = await self.send_response(client, message.chat.id, "Hold on, I'm verifying...")
                replied = message.reply_to_message

                if not replied:
                    await msg.edit("<b>Please reply with a screenshot of your payment for the premium purchase so I can check...</b>")
                elif replied.photo:
                    await client.send_photo(
                        chat_id=settings.LOG_CHANNEL,
                        photo=replied.photo.file_id,
                        caption=(
                            f"<b>User - {message.from_user.mention}\n"
                            f"User ID - <code>{message.from_user.id}</code>\n"
                            f"Username - <code>{message.from_user.username}</code>\n"
                            f"First Name - <code>{message.from_user.first_name}</code></b>"
                        ),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Close", callback_data="close_data")]
                        ])
                    )
                    await msg.edit_text("<b>Your screenshot has been sent to the admins.</b>")
        except Exception as e:
            logger.error(f"Premium command error: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} An error occurred while processing premium command",
                delete_after=15
            )

    async def handle_help(self, client: Client, message: Message, user_id: int):
        """Handle help command"""
        try:
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
            auto_rename_status = await hyoshcoder.get_auto_rename_status(user_id)
        
            btn_seq_text = "Sequential ✅" if sequential_status else "Sequential ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
            auto_rename_text = "Auto-Rename ✅" if auto_rename_status else "Auto-Rename ❌"
        
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("• Automatic renaming format •", callback_data='file_names')],
                [InlineKeyboardButton('• Thumbnail', callback_data='thumbnail'), 
                 InlineKeyboardButton('Caption •', callback_data='caption')],
                [InlineKeyboardButton('• Metadata', callback_data='meta'), 
                 InlineKeyboardButton('Set Media •', callback_data='setmedia')],
                [InlineKeyboardButton('• Set Dump', callback_data='setdump'), 
                 InlineKeyboardButton('View Dump •', callback_data='viewdump')],
                [InlineKeyboardButton(f'• {btn_seq_text}', callback_data='sequential'), 
                 InlineKeyboardButton('Premium •', callback_data='premiumx')],
                [InlineKeyboardButton(f'• Extract from: {src_txt}', callback_data='toggle_src'),
                 InlineKeyboardButton(f'• {auto_rename_text}', callback_data='toggle_auto_rename')],
                [InlineKeyboardButton('• Home', callback_data='home')]
            ])
            
            await self.send_response(
                client,
                message.chat.id,
                Txt.HELP_TXT.format(client.mention),
                reply_markup=buttons,
                photo=await get_random_photo(),
                delete_after=None  # Don't auto-delete help message
            )
        except Exception as e:
            logger.error(f"Help command error: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} Failed to load help menu",
                delete_after=15
            )

    async def handle_freepoints(self, client: Client, message: Message):
        """Handle free points command"""
        try:
            config = await hyoshcoder.get_config("points_config") or {}
            ad_config = config.get('ad_watch', {})
            
            min_points = ad_config.get('min_points', 5)
            max_points = ad_config.get('max_points', 20)
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Share Bot", callback_data="invite")],
                [InlineKeyboardButton("💰 Watch Ad", callback_data="watch_ad")],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            caption = (
                "**✨ Free Points System**\n\n"
                "Earn points by helping grow our community:\n\n"
                f"🔹 **Share Bot**: Get {config.get('referral_bonus', 10)} points per referral\n"
                f"🔹 **Watch Ads**: Earn {min_points}-{max_points} points per ad\n\n"
                f"💎 Premium members earn {config.get('premium_multiplier', 2)}x more points!"
            )
            
            await self.send_response(
                client,
                message.chat.id,
                caption,
                reply_markup=buttons,
                photo=await get_random_photo(),
                delete_after=60
            )
        except Exception as e:
            logger.error(f"Free points error: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} Couldn't load points info",
                delete_after=15
            )

    async def handle_command(self, client: Client, message: Message):
        """Main command handler"""
        user_id = message.from_user.id
        is_admin = user_id == self.ADMIN_USER_ID
        
        try:
            command = message.command
            if not command:
                return
                
            cmd = command[0].lower()
            args = command[1:]
            
            # Auto-delete non-start commands after delay
            if cmd != "start":
                asyncio.create_task(self.auto_delete_message(message))
            
            if cmd == 'start':
                await self.handle_start(client, message, args)
            elif cmd in ["leaderboard", "lb"]:
                await self.handle_leaderboard(client, message)
            elif cmd in ["mystats"]:
                await self.handle_stats(client, message, user_id)
            elif cmd == "autorename":
                await self.handle_autorename(client, message, user_id, args)
            elif cmd == "setmedia":
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{self.emoji['file']} Document", callback_data="setmedia_document")],
                    [InlineKeyboardButton(f"{self.emoji['video']} Video", callback_data="setmedia_video")]
                ])
                caption = "**Please select the type of media you want to set:**"
                await self.send_response(
                    client,
                    message.chat.id,
                    caption,
                    reply_markup=keyboard,
                    photo=await get_random_photo(),
                    delete_after=30
                )
            elif cmd == "set_caption":
                await self.handle_caption(client, message, user_id, args, "set")
            elif cmd == "del_caption":
                await self.handle_caption(client, message, user_id, args, "del")
            elif cmd in ['see_caption', 'view_caption']:
                await self.handle_caption(client, message, user_id, args, "view")
            elif cmd in ['view_thumb', 'viewthumb']:
                await self.handle_thumbnail(client, message, user_id, "view")
            elif cmd in ['del_thumb', 'delthumb']:
                await self.handle_thumbnail(client, message, user_id, "del")
            elif cmd in ["donate", "premium", "plan", "bought"]:
                await self.handle_premium(client, message, cmd)
            elif cmd == "help":
                await self.handle_help(client, message, user_id)
            elif cmd == "set_dump":
                await self.handle_dump(client, message, user_id, args, "set")
            elif cmd in ["view_dump", "viewdump"]:
                await self.handle_dump(client, message, user_id, args, "view")
            elif cmd in ["del_dump", "deldump"]:
                await self.handle_dump(client, message, user_id, args, "del")
            elif cmd == "freepoints":
                await self.handle_freepoints(client, message)
            elif is_admin and cmd == "admin":
                await self.handle_admin_commands(client, message, args)
                
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            logger.error(f"Error in command {cmd}: {e}")
            await self.send_response(
                client,
                message.chat.id,
                f"{self.emoji['error']} An error occurred. Please try again later.",
                delete_after=15
            )

# Initialize handler
command_handler = CommandHandler()

@Client.on_message(filters.private & filters.command([
    "start", "autorename", "setmedia", "set_caption", "del_caption", "see_caption",
    "view_caption", "viewthumb", "view_thumb", "del_thumb", "delthumb", "metadata",
    "donate", "premium", "plan", "bought", "help", "set_dump", "view_dump", "viewdump",
    "del_dump", "deldump", "profile", "leaderboard", "lb", "mystats", "freepoints",
    "settitle", "setauthor", "setartist", "setaudio", "setsubtitle", "setvideo", "admin"
]))
async def command_dispatcher(client: Client, message: Message):
    await command_handler.handle_command(client, message)

@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    """Handle thumbnail setting"""
    try:
        mkn = await command_handler.send_response(client, message.chat.id, "Please wait...")
        await hyoshcoder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
        await mkn.edit("**Thumbnail saved successfully ✅️**")
        asyncio.create_task(command_handler.auto_delete_message(mkn, delay=30))
    except Exception as e:
        logger.error(f"Error setting thumbnail: {e}")
        await command_handler.send_response(
            client,
            message.chat.id,
            f"{command_handler.emoji['error']} Failed to save thumbnail",
            delete_after=15
        )
