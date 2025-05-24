import asyncio
import time
import logging
from typing import List, Optional, Tuple, Dict
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    Message, 
    CallbackQuery
)
from pyrogram.errors import (
    UserNotParticipant,
    FloodWait,
    ChannelInvalid,
    ChatAdminRequired,
    PeerIdInvalid,
    UsernameNotOccupied,
    UsernameInvalid,
    ChatWriteForbidden,
    MessageNotModified
)
from config import settings
from database.data import hyoshcoder
from helpers.utils import get_random_photo

logger = logging.getLogger(__name__)
FORCE_SUB_CHANNELS = settings.FORCE_SUB_CHANNELS or []

class ForceSubManager:
    def __init__(self):
        self.channel_cache = {}
        self.last_refresh = 0
        self.cache_timeout = 3600  # 1 hour cache

    async def validate_channel(self, client: Client, channel: str) -> bool:
        """Check if channel exists and is accessible"""
        try:
            if channel in self.channel_cache and (time.time() - self.last_refresh) < self.cache_timeout:
                return self.channel_cache[channel]['valid']
            
            if isinstance(channel, int) or (channel.lstrip('-').isdigit()):
                chat = await client.get_chat(int(channel))
            else:
                chat = await client.get_chat(channel)
            
            self.channel_cache[channel] = {
                'valid': True,
                'info': {
                    'id': chat.id,
                    'title': getattr(chat, 'title', f"Channel {chat.id}"),
                    'username': getattr(chat, 'username', None),
                    'invite_link': getattr(chat, 'invite_link', None)
                }
            }
            return True
            
        except (UsernameNotOccupied, UsernameInvalid, PeerIdInvalid, ChannelInvalid):
            logger.warning(f"Invalid channel: {channel}")
            self.channel_cache[channel] = {'valid': False}
            return False
        except Exception as e:
            logger.error(f"Channel validation error: {e}")
            return False

    async def check_membership(self, client: Client, user_id: int, channel: str) -> bool:
        """Check if user is member of channel"""
        try:
            member = await client.get_chat_member(channel, user_id)
            return member.status not in ["left", "kicked"]
        except UserNotParticipant:
            return False
        except (ChannelInvalid, ChatAdminRequired):
            logger.warning(f"Can't check membership in {channel}")
            return True  # Allow access if we can't verify
        except FloodWait as e:
            logger.warning(f"Flood wait {e.x}s for {channel}")
            await asyncio.sleep(e.x)
            return await self.check_membership(client, user_id, channel)
        except Exception as e:
            logger.error(f"Membership check error: {e}")
            return True  # Fail-safe

    async def verify_user(self, client: Client, user_id: int) -> Tuple[bool, List[str]]:
        """Verify user's subscriptions"""
        if not FORCE_SUB_CHANNELS:
            return True, []
            
        # Check premium status first
        premium_status = await hyoshcoder.check_premium_status(user_id)
        if premium_status.get('is_premium', False):
            return True, []
            
        # Validate channels
        valid_channels = []
        for channel in FORCE_SUB_CHANNELS:
            if await self.validate_channel(client, channel):
                valid_channels.append(channel)
            else:
                logger.warning(f"Removing invalid channel: {channel}")
        
        if not valid_channels:
            return True, []
            
        # Check memberships
        results = await asyncio.gather(*[
            self.check_membership(client, user_id, channel) 
            for channel in valid_channels
        ])
        
        missing = [
            channel for channel, is_member 
            in zip(valid_channels, results) 
            if not is_member
        ]
        
        return len(missing) == 0, missing

    async def generate_buttons(self, channels: List[str]) -> Optional[InlineKeyboardMarkup]:
        """Generate subscription buttons"""
        buttons = []
        for channel in channels:
            if channel not in self.channel_cache or not self.channel_cache[channel]['valid']:
                continue
                
            info = self.channel_cache[channel]['info']
            url = None
            if info['username']:
                url = f"https://t.me/{info['username']}"
            elif info['invite_link']:
                url = info['invite_link']
                
            if url:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"✨ Join {info['title']}",
                        url=url
                    )
                ])
        
        if buttons:
            buttons.append([
                InlineKeyboardButton(
                    text="✅ I've Subscribed",
                    callback_data="verify_subs"
                )
            ])
            return InlineKeyboardMarkup(buttons)
        return None

# Initialize manager
sub_manager = ForceSubManager()

async def send_subscription_message(client: Client, user_id: int, message: Message):
    """Send subscription required message"""
    is_verified, missing = await sub_manager.verify_user(client, user_id)
    if is_verified:
        return True
        
    buttons = await sub_manager.generate_buttons(missing)
    if not buttons:
        return True
        
    try:
        photo = await get_random_photo()
        caption = (
            "📢 <b>Subscription Required</b>\n\n"
            "To use this bot, please join our channels first:\n\n"
            "1️⃣ Join all channels below\n"
            "2️⃣ Click the verify button\n\n"
            "🔹 Premium users bypass this requirement"
        )
        
        await client.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=caption,
            reply_markup=buttons
        )
        return False
    except Exception as e:
        logger.error(f"Subscription message error: {e}")
        return True

@Client.on_message(filters.private & ~filters.user(settings.ADMIN))
async def force_sub_check(client: Client, message: Message):
    """Main force subscription handler"""
    try:
        # Skip if user is admin or no channels configured
        if not FORCE_SUB_CHANNELS:
            return
            
        # Check if message is a command
        if message.text and message.text.startswith('/'):
            return
            
        await send_subscription_message(client, message.from_user.id, message)
    except Exception as e:
        logger.error(f"Force sub check error: {e}")

@Client.on_callback_query(filters.regex("^verify_subs$"))
async def verify_subscription_callback(client: Client, callback: CallbackQuery):
    """Handle subscription verification"""
    try:
        await callback.answer()
        user_id = callback.from_user.id
        
        # Check premium status
        premium_status = await hyoshcoder.check_premium_status(user_id)
        if premium_status.get('is_premium', False):
            await callback.message.delete()
            await client.send_message(
                user_id,
                "🌟 Premium access verified!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Home", callback_data="home")]
                ])
            )
            return
            
        is_verified, missing = await sub_manager.verify_user(client, user_id)
        
        if is_verified:
            await callback.message.delete()
            await client.send_message(
                user_id,
                "✅ Subscription verified!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Home", callback_data="home")]
                ])
            )
        else:
            buttons = await sub_manager.generate_buttons(missing)
            if buttons:
                try:
                    await callback.message.edit_reply_markup(buttons)
                except MessageNotModified:
                    pass
                    
            await callback.answer(
                "❌ Please join all required channels!",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Verify callback error: {e}")
        await callback.answer(
            "⚠️ An error occurred. Please try again.",
            show_alert=True
        )

@Client.on_message(filters.command("refresh_subs") & filters.user(settings.ADMIN))
async def refresh_channels_cache(client: Client, message: Message):
    """Admin command to refresh channel cache"""
    try:
        sub_manager.channel_cache = {}
        sub_manager.last_refresh = 0
        await message.reply("🔄 Channel cache refreshed successfully!")
    except Exception as e:
        logger.error(f"Cache refresh error: {e}")
        await message.reply(f"❌ Error: {e}")
