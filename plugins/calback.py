import random
import uuid
import asyncio
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto
)
from pyrogram.errors import FloodWait
from helpers.utils import get_random_photo, get_shortlink
from scripts import Txt
from database.data import get_database
from config import settings

# Constants
METADATA_TIMEOUT = 60  # seconds
POINT_RANGE = range(5, 21)  # 5-20 points
SHARE_MESSAGE = """
🚀 *Discover This Amazing Bot!* 🚀

I'm using this awesome file renaming bot with these features:
- Automatic file renaming
- Custom metadata editing
- Thumbnail customization
- Sequential file processing
- And much more!

Join me using this link: {invite_link}
"""

class CallbackActions:
    @staticmethod
    async def handle_home(client, query):
        buttons = [
            [InlineKeyboardButton("• My Stats •", callback_data='mystats'),
             InlineKeyboardButton("• Leaderboard •", callback_data='leaderboard')],
            [InlineKeyboardButton("• My Commands •", callback_data='help')],
            [
                InlineKeyboardButton('• Updates', url='https://t.me/sineur_x_bot'), 
                InlineKeyboardButton('Support •', url='https://t.me/sineur_x_bot')
            ],
            [
                InlineKeyboardButton('• About', callback_data='about'), 
                InlineKeyboardButton('Source •', callback_data='source')
            ]
        ]
        return {
            'caption': Txt.START_TXT.format(query.from_user.mention),
            'reply_markup': InlineKeyboardMarkup(buttons)
        }

    @staticmethod
    async def handle_help(client, query, user_id):
        sequential_status = await get_database.get_sequential_mode(user_id)
        btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
        
        src_info = await get_database.get_src_info(user_id)
        src_txt = "File name" if src_info == "file_name" else "File caption"

        buttons = [
            [InlineKeyboardButton("• Automatic Renaming Format •", callback_data='file_names')],
            [
                InlineKeyboardButton('• Thumbnail', callback_data='thumbnail'), 
                InlineKeyboardButton('Caption •', callback_data='caption')
            ],
            [InlineKeyboardButton('• Metadata', callback_data='meta')],
            [
                InlineKeyboardButton(f'• {btn_sec_text}', callback_data='sequential'), 
                InlineKeyboardButton('Premium •', callback_data='premiumx')
            ],
            [InlineKeyboardButton(f'• Extract from: {src_txt}', callback_data='toggle_src')],
            [InlineKeyboardButton('• Home', callback_data='home')]
        ]
        return {
            'caption': Txt.HELP_TXT.format(client.mention),
            'reply_markup': InlineKeyboardMarkup(buttons)
        }

    @staticmethod
    async def handle_stats(client, query, user_id):
        stats = await get_database.get_user_file_stats(user_id)
        points = await get_database.get_points(user_id)
        premium_status = await get_database.check_premium_status(user_id)
        referral_stats = await get_database.users.find_one(
            {"_id": user_id},
            {"referral.referred_count": 1, "referral.referral_earnings": 1}
        )
        
        text = (
            f"📊 <b>Your Statistics</b>\n\n"
            f"✨ <b>Points Balance:</b> {points}\n"
            f"⭐ <b>Premium Status:</b> {'Active ✅' if premium_status['is_premium'] else 'Inactive ❌'}\n"
            f"👥 <b>Referrals:</b> {referral_stats.get('referral', {}).get('referred_count', 0)} "
            f"(Earned {referral_stats.get('referral', {}).get('referral_earnings', 0)} ✨)\n\n"
            f"📝 <b>Files Renamed</b>\n"
            f"• Total: {stats['total_renamed']}\n"
            f"• Today: {stats['today']}\n"
            f"• This Week: {stats['this_week']}\n"
            f"• This Month: {stats['this_month']}\n"
        )
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")],
            [InlineKeyboardButton("👥 Invite Friends", callback_data="invite")],
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ])
        
        return {
            'caption': text,
            'reply_markup': buttons
        }

    @staticmethod
    async def handle_leaderboard(client, query, period="weekly", type="points"):
        leaders = await get_database.get_leaderboard(period, type)
        type_display = {
            "points": "Points",
            "renames": "Files Renamed",
            "referrals": "Referrals"
        }.get(type, "Points")
        
        period_display = {
            "daily": "Daily",
            "weekly": "Weekly",
            "monthly": "Monthly",
            "alltime": "All-Time"
        }.get(period, "Weekly")
        
        text = f"🏆 {period_display} {type_display} Leaderboard:\n\n"
        for i, user in enumerate(leaders[:10], 1):
            text += (
                f"{i}. {user['username'] or user['_id']} - "
                f"{user['value']} {type_display} "
                f"{'⭐' if user.get('is_premium') else ''}\n"
            )
        
        return {
            'caption': text,
            'reply_markup': get_leaderboard_keyboard(period, type)
        }

    @staticmethod
    async def handle_metadata_toggle(client, query, user_id, data):
        if data.startswith("metadata_"):
            is_enabled = data.split("_")[1] == '1'
            user_metadata = await get_database.get_metadata_code(user_id)
            
            await get_database.set_metadata(user_id, bool_meta=is_enabled)
            
            ON = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('Metadata Enabled', callback_data='metadata_1'), 
                    InlineKeyboardButton('✅', callback_data='metadata_1')
                ],
                [InlineKeyboardButton('Set Custom Metadata', callback_data='custom_metadata')]
            ])
            
            OFF = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton('Metadata Disabled', callback_data='metadata_0'), 
                    InlineKeyboardButton('❌', callback_data='metadata_0')
                ],
                [InlineKeyboardButton('Set Custom Metadata', callback_data='custom_metadata')]
            ])
            
            return {
                'caption': f"<b>Your Current Metadata:</b>\n\n➜ {user_metadata}",
                'reply_markup': ON if is_enabled else OFF
            }
        
        elif data == "custom_metadata":
            await query.message.delete()
            try:
                user_metadata = await get_database.get_metadata_code(user_id)
                metadata_message = f"""
<b>--Metadata Settings--</b>

➜ <b>Current Metadata:</b> {user_metadata}

<b>Description</b>: Metadata will modify MKV video files, including all audio titles, streams and subtitles.

<b>➲ Send the metadata title. Timeout: {METADATA_TIMEOUT} sec</b>
"""
                metadata = await client.ask(
                    text=metadata_message,
                    chat_id=user_id,
                    filters=filters.text,
                    timeout=METADATA_TIMEOUT,
                    disable_web_page_preview=True,
                )
                
                await get_database.set_metadata_code(user_id, metadata_code=metadata.text)
                await client.send_message(
                    chat_id=user_id,
                    text="**Your metadata code has been set successfully ✅**"
                )
            except asyncio.TimeoutError:
                await client.send_message(
                    chat_id=user_id,
                    text="⚠️ Error!!\n\n**Request has expired.**\nRestart using /metadata",
                )
            return None

    @staticmethod
    async def handle_free_points(client, query, user_id):
        me = await client.get_me()
        unique_code = str(uuid.uuid4())[:8]
        invite_link = f"https://t.me/{me.username}?start=refer_{user_id}"
        points_link = f"https://t.me/{me.username}?start=adds_{unique_code}"
        
        shortlink = await get_shortlink(
            settings.SHORTED_LINK, 
            settings.SHORTED_LINK_API, 
            points_link
        )
        
        points = random.choice(POINT_RANGE)
        await get_database.set_expend_points(user_id, points, unique_code)
        
        share_msg_encoded = f"https://t.me/share/url?url={quote(invite_link)}&text={quote(SHARE_MESSAGE.format(invite_link=invite_link))}"
        
        buttons = [
            [InlineKeyboardButton("🔗 Share Bot", url=share_msg_encoded)],
            [InlineKeyboardButton("💰 Watch Ad", url=shortlink)],
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ]
        
        caption = (
            "**✨ Free Points System**\n\n"
            "Earn points by helping grow our community:\n\n"
            "🔹 **Share Bot**: Get 5-20 points for each friend who joins\n"
            "🔹 **Watch Ads**: Earn instant points by viewing sponsored content\n\n"
            "💎 Premium members earn DOUBLE points!"
        )
        
        return {
            'caption': caption,
            'reply_markup': InlineKeyboardMarkup(buttons)
        }

@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    try:
        # Get common resources
        img = await get_random_photo()
        thumb = await get_database.get_thumbnail(user_id)
        
        # Handle different callback actions
        if data == "home":
            response = await CallbackActions.handle_home(client, query)
        
        elif data == "help":
            response = await CallbackActions.handle_help(client, query, user_id)
        
        elif data == "mystats":
            response = await CallbackActions.handle_stats(client, query, user_id)
        
        elif data == "leaderboard":
            response = await CallbackActions.handle_leaderboard(client, query)
        
        elif data.startswith("lb_"):
            parts = data.split("_")
            if len(parts) == 3:
                period = await get_database.get_leaderboard_period(user_id)
                type = await get_database.get_leaderboard_type(user_id)
                
                if parts[1] == "period":
                    period = parts[2]
                    await get_database.set_leaderboard_period(user_id, period)
                elif parts[1] == "type":
                    type = parts[2]
                    await get_database.set_leaderboard_type(user_id, type)
                
                response = await CallbackActions.handle_leaderboard(client, query, period, type)
        
        elif data in ["metadata_1", "metadata_0", "custom_metadata"]:
            response = await CallbackActions.handle_metadata_toggle(client, query, user_id, data)
            if not response:  # For custom_metadata which handles its own response
                return
        
        elif data == "free_points":
            response = await CallbackActions.handle_free_points(client, query, user_id)
        
        elif data == "caption":
            buttons = [
                [InlineKeyboardButton("• Support", url='https://t.me/REQUETE_ANIME_30sbot'), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': Txt.CAPTION_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "meta":
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': Txt.SEND_METADATA,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "file_names":
            format_template = await get_database.get_format_template(user_id)
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': Txt.FILE_NAME_TXT.format(format_template=format_template),
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "thumbnail":
            buttons = [
                [InlineKeyboardButton("• View Thumbnail", callback_data="showThumb")],
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': Txt.THUMBNAIL_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "showThumb":
            caption = "Here is your current thumbnail" if thumb else "No current thumbnail"
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': caption,
                'reply_markup': InlineKeyboardMarkup(buttons),
                'thumb': thumb if thumb else img
            }
        
        elif data == "source":
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="home")]
            ]
            response = {
                'caption': Txt.SOURCE_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "premiumx":
            buttons = [
                [InlineKeyboardButton("• Free Points", callback_data="free_points")],
                [InlineKeyboardButton("• Back", callback_data="help")]
            ]
            response = {
                'caption': Txt.PREMIUM_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "plans":
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close")]
            ]
            response = {
                'caption': Txt.PREPLANS_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "about":
            buttons = [
                [
                    InlineKeyboardButton("• Support", url='https://t.me/tout_manga_confondu'), 
                    InlineKeyboardButton("Commands •", callback_data="help")
                ],
                [
                    InlineKeyboardButton("• Developer", url='https://t.me/hyoshassistantbot'), 
                    InlineKeyboardButton("Network •", url='https://t.me/tout_manga_confondu')
                ],
                [InlineKeyboardButton("• Back •", callback_data="home")]
            ]
            response = {
                'caption': Txt.ABOUT_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons),
                'disable_web_page_preview': True
            }
        
        elif data.startswith("setmedia_"):
            media_type = data.split("_")[1]
            await get_database.set_media_preference(user_id, media_type)
            buttons = [
                [InlineKeyboardButton("Back •", callback_data='help')]
            ]
            response = {
                'caption': f"**Media preference set to:** {media_type} ✅",
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "sequential":
            await get_database.toggle_sequential_mode(user_id)
            response = await CallbackActions.handle_help(client, query, user_id)
        
        elif data == "toggle_src":
            await get_database.toggle_src_info(user_id)
            response = await CallbackActions.handle_help(client, query, user_id)
        
        elif data == "close":
            try:
                await query.message.delete()
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
            except:
                pass
            return
        
        else:
            return

        # Send the response
        if 'thumb' in response:
            media = InputMediaPhoto(
                media=response['thumb'], 
                caption=response['caption']
            )
            await query.message.edit_media(
                media=media,
                reply_markup=response['reply_markup']
            )
        else:
            await query.message.edit_text(
                text=response['caption'],
                reply_markup=response['reply_markup'],
                disable_web_page_preview=response.get('disable_web_page_preview', False)
            )
            
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await cb_handler(client, query)
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        try:
            await query.answer("❌ An error occurred. Please try again.", show_alert=True)
        except:
            pass
