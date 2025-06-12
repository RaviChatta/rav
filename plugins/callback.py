import random
import uuid
import asyncio
import time
import logging
import string
import secrets
from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto,
    InputMediaAnimation,
    Message
)
from urllib.parse import quote
from helpers.utils import get_random_photo, get_random_animation, get_shortlink
from scripts import Txt
from database.data import hyoshcoder
from config import settings
from datetime import datetime
from collections import defaultdict
from pyrogram.errors import QueryIdInvalid, FloodWait, ChatWriteForbidden

logger = logging.getLogger(__name__)
ADMIN_USER_ID = settings.ADMIN

# Emoji Constants
EMOJI = {
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

# Button Styles
BTN_STYLE = {
    'small': {'width': 3, 'max_chars': 10},
    'medium': {'width': 2, 'max_chars': 15},
    'large': {'width': 1, 'max_chars': 20}
}

# State trackers
caption_states = defaultdict(dict)

def create_button(text, callback_data, style='medium', emoji=None):
    """Create button with consistent styling"""
    if emoji:
        text = f"{emoji} {text}"
    max_chars = BTN_STYLE[style]['max_chars']
    if len(text) > max_chars:
        text = text[:max_chars-1] + "…"
    return InlineKeyboardButton(text, callback_data=callback_data)

def create_keyboard(buttons, style='medium'):
    """Create mobile-friendly keyboard layout"""
    width = BTN_STYLE[style]['width']
    return InlineKeyboardMarkup([buttons[i:i+width] for i in range(0, len(buttons), width)])

async def edit_or_resend(client, query, response):
    """Edit existing message or send new one if edit fails"""
    try:
        if 'photo' in response:
            if query.message.photo:
                await query.message.edit_media(
                    media=InputMediaPhoto(
                        media=response['photo'],
                        caption=response['caption']
                    ),
                    reply_markup=response['reply_markup']
                )
            else:
                await query.message.delete()
                await client.send_photo(
                    chat_id=query.message.chat.id,
                    photo=response['photo'],
                    caption=response['caption'],
                    reply_markup=response['reply_markup']
                )
        elif 'animation' in response:
            await query.message.edit_media(
                media=InputMediaAnimation(
                    media=response['animation'],
                    caption=response['caption']
                ),
                reply_markup=response['reply_markup']
            )
        else:
            await query.message.edit_text(
                text=response['caption'],
                reply_markup=response['reply_markup'],
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        await query.message.reply(
            text=response['caption'],
            reply_markup=response['reply_markup'],
            disable_web_page_preview=True
        )

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    try:
        # Get common resources
        img = await get_random_photo()
        anim = await get_random_animation()
        thumb = await hyoshcoder.get_thumbnail(user_id)
        sequential_status = await hyoshcoder.get_sequential_mode(user_id)
        src_info = await hyoshcoder.get_src_info(user_id)
        src_txt = "File name" if src_info == "file_name" else "File caption"
        
        # Home Menu
        if data == "home":
            btn = create_keyboard([
                create_button("MY COMMANDS", 'help'),
                create_button("My Stats", 'mystats', emoji=EMOJI['stats']),
                create_button("Leaderboard", 'leaderboard', emoji=EMOJI['leaderboard']),
                create_button("Earn Points", 'freepoints', emoji=EMOJI['points']),
                create_button("Close", 'close', emoji='❌')
            ])
            
            await edit_or_resend(client, query, {
                'caption': Txt.START_TXT.format(query.from_user.mention),
                'reply_markup': btn,
                'animation': anim
            })

        # Help Menu
        elif data == "help":
            btn_sec_text = f"Sequential {'✅' if sequential_status else '❌'}"
            btn = create_keyboard([
                create_button("AUTORENAME", 'file_names'),
                create_button("THUMB", 'thumbnail'),
                create_button("CAPTION", 'caption'),
                create_button("METADATA", 'meta'),
                create_button("MEDIA", 'setmedia'),
                create_button("DUMP", 'setdump'),
                create_button(btn_sec_text, 'sequential'),
                create_button("PREMIUM", 'premiumx'),
                create_button(f"Source: {src_txt}", 'toggle_src'),
                create_button("HOME", 'home')
            ], style='small')
            
            await edit_or_resend(client, query, {
                'caption': Txt.HELP_TXT.format(client.mention),
                'reply_markup': btn,
                'photo': img
            })

        # My Stats
        elif data == "mystats":
            stats = await hyoshcoder.get_user_file_stats(user_id)
            points = await hyoshcoder.get_points(user_id)
            premium_status = await hyoshcoder.check_premium_status(user_id)
            user_data = await hyoshcoder.read_user(user_id)
            referral_stats = user_data.get('referral', {})
            
            text = (
                f"📊 <b>Your Statistics</b>\n\n"
                f"{EMOJI['points']} <b>Points Balance:</b> {points}\n"
                f"{EMOJI['premium']} <b>Premium Status:</b> {'Active ' + EMOJI['success'] if premium_status.get('is_premium', False) else 'Inactive ' + EMOJI['error']}\n"
                f"{EMOJI['referral']} <b>Referrals:</b> {referral_stats.get('referred_count', 0)} "
                f"(Earned {referral_stats.get('referral_earnings', 0)} {EMOJI['points']})\n\n"
                f"{EMOJI['rename']} <b>Files Renamed</b>\n"
                f"• Total: {stats.get('total_renamed', 0)}\n"
                f"• Today: {stats.get('today', 0)}\n"
                f"• This Week: {stats.get('this_week', 0)}\n"
                f"• This Month: {stats.get('this_month', 0)}\n"
            )
            
            btn = create_keyboard([
                create_button("Leaderboard", "leaderboard", emoji=EMOJI['leaderboard']),
                create_button("Invite Friends", "invite", emoji=EMOJI['referral']),
                create_button("Back", "help")
            ])
            
            await edit_or_resend(client, query, {
                'caption': text,
                'reply_markup': btn,
                'photo': img
            })

        # Leaderboard
        elif data == "leaderboard":
            try:
                period = await hyoshcoder.get_leaderboard_period(user_id)
                lb_type = await hyoshcoder.get_leaderboard_type(user_id)
        
                emoji_map = {
                    "points": EMOJI['points'],
                    "renames": EMOJI['file'],
                    "referrals": EMOJI['referral']
                }
                title_map = {
                    "points": "Points",
                    "renames": "Files Renamed",
                    "referrals": "Referrals"
                }
        
                emoji = emoji_map.get(lb_type, EMOJI['points'])
                title = title_map.get(lb_type, "Points")
        
                if lb_type == "referrals":
                    leaders = await hyoshcoder.get_referrals_leaderboard(period, limit=10)
                elif lb_type == "renames":
                    leaders = await hyoshcoder.get_renames_leaderboard(period, limit=10)
                else:
                    leaders_raw = await hyoshcoder.get_leaderboard(period, limit=10)
                    leaders = []
                    for user in leaders_raw:
                        try:
                            user_info = await client.get_users(user['_id'])
                            username = f"@{user_info.username}" if user_info.username else user_info.first_name
                        except:
                            username = f"User {user['_id']}"
                        leaders.append({
                            'username': username,
                            'value': user.get('points', 0),
                            'is_premium': user.get('is_premium', False)
                        })
        
                if not leaders:
                    response = {
                        'caption': "📭 No leaderboard data available yet",
                        'reply_markup': create_keyboard([
                            create_button("Back", "help")
                        ]),
                        'photo': img
                    }
                else:
                    period_name = {
                        "daily": "Daily",
                        "weekly": "Weekly",
                        "monthly": "Monthly",
                        "alltime": "All-Time"
                    }.get(period, period.capitalize())
        
                    text = f"🏆 **{period_name} Leaderboard - {emoji} {title}**\n\n"
                    for i, user in enumerate(leaders, 1):
                        premium_tag = " 💎" if user.get("is_premium") else ""
                        text += f"**{i}.** {user['username']} — `{user['value']}` {emoji}{premium_tag}\n"
        
                    # Period buttons
                    period_btns = [
                        create_button("• Daily •" if period == "daily" else "Daily", "lb_period_daily"),
                        create_button("• Weekly •" if period == "weekly" else "Weekly", "lb_period_weekly"),
                        create_button("• Monthly •" if period == "monthly" else "Monthly", "lb_period_monthly"),
                        create_button("• All-Time •" if period == "alltime" else "All-Time", "lb_period_alltime")
                    ]
                    
                    # Type buttons
                    type_btns = [
                        create_button("• Points •" if lb_type == "points" else "Points", "lb_type_points"),
                        create_button("• Files •" if lb_type == "renames" else "Files", "lb_type_renames"),
                        create_button("• Referrals •" if lb_type == "referrals" else "Referrals", "lb_type_referrals")
                    ]
                    
                    btn = InlineKeyboardMarkup([
                        period_btns[:2],
                        period_btns[2:],
                        type_btns,
                        [create_button("Back", "help")]
                    ])
        
                    response = {
                        'caption': text,
                        'reply_markup': btn,
                        'photo': img
                    }
                
                await edit_or_resend(client, query, response)
        
            except Exception as e:
                logger.error(f"Error in leaderboard handler: {e}")
                await query.answer("⚠️ Error loading leaderboard", show_alert=True)

        # Free Points
        elif data == "freepoints":
            me = await client.get_me()
            user = await hyoshcoder.read_user(user_id)
            
            # Generate referral code if not exists
            if not user or not user.get("referral_code"):
                referral_code = secrets.token_hex(4)
                await hyoshcoder.users.update_one(
                    {"_id": user_id},
                    {"$set": {"referral_code": referral_code}},
                    upsert=True
                )
            else:
                referral_code = user["referral_code"]
            
            refer_link = f"https://t.me/{me.username}?start=ref_{referral_code}"
            
            # Generate points link
            point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))
            deep_link = f"https://t.me/{me.username}?start={point_id}"
            short_url = await get_shortlink(
                url=settings.SHORTED_LINK,
                api=settings.SHORTED_LINK_API,
                link=deep_link
            )
            
            # Save the points link
            await hyoshcoder.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)

            # Create buttons
            btn = create_keyboard([
                create_button("Share Referral", f"share_referral:{refer_link}", emoji=EMOJI['link']),
                create_button("Earn Points", f"open_points:{short_url}", emoji=EMOJI['money']),
                create_button("Back", "help")
            ])
            
            caption = (
                "**🎁 Free Points Menu**\n\n"
                "**1. Referral Program**\n"
                f"🔗 Your link: `{refer_link}`\n"
                f"• Earn {settings.REFER_POINT_REWARD} points per referral\n\n"
                "**2. Earn Points**\n"
                f"🔗 Click here: {short_url}\n"
                f"• Get {settings.SHORTENER_POINT_REWARD} points instantly\n\n"
                "Your points will be added automatically when someone uses your links."
            )
            
            await edit_or_resend(client, query, {
                'caption': caption,
                'reply_markup': btn,
                'photo': img
            })

        # Sequential Toggle
        elif data == "sequential":
            try:
                new_status = not sequential_status
                await hyoshcoder.set_sequential_mode(user_id, new_status)
                await query.answer(f"Sequential mode {'enabled' if new_status else 'disabled'}")
                # Refresh help menu
                await cb_handler(client, query)
            except Exception as e:
                logger.error(f"Error toggling sequential mode: {e}")
                await query.answer("⚠️ Failed to update setting", show_alert=True)

        # Source Toggle
        elif data == "toggle_src":
            try:
                new_src = "file_caption" if src_info == "file_name" else "file_name"
                await hyoshcoder.set_src_info(user_id, new_src)
                await query.answer(f"Source set to {new_src.replace('_', ' ')}")
                # Refresh help menu
                await cb_handler(client, query)
            except Exception as e:
                logger.error(f"Error toggling source: {e}")
                await query.answer("⚠️ Failed to update source", show_alert=True)

        # Close Button
        elif data == "close":
            try:
                await query.message.delete()
            except:
                pass

        # Answer the callback query
        await query.answer()

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except QueryIdInvalid:
        logger.warning("Query ID was invalid or expired")
    except Exception as e:
        logger.error(f"Callback handler error: {e}", exc_info=True)
        try:
            await query.answer("⚠️ An error occurred", show_alert=True)
        except:
            pass

# Start the cleanup task
asyncio.create_task(cleanup_states())
