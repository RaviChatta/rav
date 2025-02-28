from database.data import hyoshcoder
from pyrogram.types import Message
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
import os, sys, time, asyncio, logging, traceback
from datetime import datetime, timedelta
from config import settings
from helpers.utils import get_random_photo

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = settings.ADMIN

is_restarting = False

@Client.on_message(filters.private & filters.command(["restart", "ban", "unban", "banned_users", "broadcast", "stats", "status", "users"]) & filters.user(ADMIN_USER_ID))
async def admin_commands(b: Client, m: Message):
    global is_restarting
    user = m.from_user
    command = m.command[0]
    img = await get_random_photo()  

    if command == "restart":
        if not is_restarting:
            is_restarting = True
            caption = ("**ᴘʀᴏᴄᴇssᴇs sᴛᴏᴘᴘᴇᴅ. ʙᴏᴛ ɪs ʀᴇsᴛᴀʀᴛɪɴɢ.....**")
            if img:
                await m.reply_photo(photo=img, caption=caption)
            else:
                await m.reply_text(text=caption)
            await b.stop()
            time.sleep(2)
            os.execl(sys.executable, sys.executable, *sys.argv)

    elif command == "ban":
        if len(m.command) < 4:
            caption =(
                "Utilisez cette commande pour bannir un utilisateur du bot.\n\n"
                "Usage :\n\n"
                "`/ban user_id ban_duration ban_reason`\n\n"
                "Exemple : `/ban 1234567 28 Vous m'avez mal utilisé.`\n"
                "Cela bannira l'utilisateur avec l'ID `1234567` pendant `28` jours pour la raison `Vous m'avez mal utilisé`."
                )
            if img:
                await m.reply_photo(photo=img, caption=caption, quote=True)
            else:
                await m.reply_text(text=caption, quote=True)
            return

        try:
            user_id = int(m.command[1])
            ban_duration = int(m.command[2])
            ban_reason = ' '.join(m.command[3:])
            ban_log_text = f"Banning user {user_id} for {ban_duration} days for the reason {ban_reason}."

            try:
                caption(
                    f"Vous êtes banni de l'utilisation de ce bot pendant **{ban_duration}** jour(s) pour la raison __{ban_reason}__.\n\n**Message de l'admin**"
                )
                if img:
                    await b.send_photo(chat_id=user_id, photo=img, caption=caption, quote=True)
                else:
                    await b.send_message(chat_id=user_id, text=caption, quote=True)
                
                ban_log_text += '\n\nUser notified successfully!'
            except Exception:
                traceback.print_exc()
                ban_log_text += f"\n\nUser notification failed! \n\n`{traceback.format_exc()}`"

            await hyoshcoder.ban_user(user_id, ban_duration, ban_reason)
            logger.info(ban_log_text)
            await m.reply_text(ban_log_text, quote=True)
        except Exception:
            traceback.print_exc()
            await m.reply_text(
                f"Error occurred! Traceback given below\n\n`{traceback.format_exc()}`",
                quote=True
            )

    elif command == "unban":
        if len(m.command) != 2:
            await m.reply_text(
                f"Utilisez cette commande pour débannir un utilisateur.\n\n"
                f"Usage:\n\n`/unban user_id`\n\n"
                f"Exemple : `/unban 1234567`\n"
                f"Cela débannira l'utilisateur avec l'ID `1234567`.",
                quote=True
            )
            return

        try:
            user_id = int(m.command[1])
            unban_log_text = f"Unbanning user {user_id}"

            try:
                await b.send_message(
                    user_id,
                    "Your ban was lifted!"
                )
                unban_log_text += '\n\nUser notified successfully!'
            except Exception:
                traceback.print_exc()
                unban_log_text += f"\n\nUser notification failed! \n\n`{traceback.format_exc()}`"

            await hyoshcoder.remove_ban(user_id)
            logger.info(unban_log_text)
            await m.reply_text(unban_log_text, quote=True)
        except Exception:
            traceback.print_exc()
            await m.reply_text(
                f"Error occurred! Traceback given below\n\n`{traceback.format_exc()}`",
                quote=True
            )

    elif command == "banned_users":
        all_banned_users = await hyoshcoder.get_all_banned_users()
        banned_usr_count = 0
        text = ''

        async for banned_user in all_banned_users:
            user_id = banned_user['id']
            ban_duration = banned_user['ban_status']['ban_duration']
            banned_on = banned_user['ban_status']['banned_on']
            ban_reason = banned_user['ban_status']['ban_reason']
            banned_usr_count += 1
            text += f"> **user_id**: `{user_id}`, **Ban Duration**: `{ban_duration}`, " \
                    f"**Banned on**: `{banned_on}`, **Reason**: `{ban_reason}`\n\n"

        reply_text = f"Total banned user(s): `{banned_usr_count}`\n\n{text}"
        if len(reply_text) > 4096:
            with open('banned-users.txt', 'w') as f:
                f.write(reply_text)
            await m.reply_document('banned-users.txt', caption="Banned users list")
            os.remove('banned-users.txt')
        else:
            await m.reply_text(reply_text, quote=True)

    elif command == "broadcast":
        if not m.reply_to_message:
            return await m.reply_text("Vous devez répondre à un message pour le diffuser.")

        await b.send_message(settings.LOG_CHANNEL, f"{m.from_user.mention} or {m.from_user.id} Started the Broadcast.")
        all_users = await hyoshcoder.get_all_users()
        broadcast_msg = m.reply_to_message
        sts_msg = await m.reply_text("Broadcast Started..!")
        done = 0
        failed = 0
        success = 0
        start_time = time.time()
        total_users = await hyoshcoder.total_users_count()

        async for user in all_users:
            sts = await send_msg(user['_id'], broadcast_msg)
            if sts == 200:
                success += 1
            elif sts == 400:
                await hyoshcoder.delete_user(user['_id'])
            else:
                failed += 1
            done += 1
            if not done % 20:
                await sts_msg.edit_text(f"Broadcast In Progress: \n\nTotal Users: {total_users} \nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")

        completed_in = timedelta(seconds=int(time.time() - start_time))
        await sts_msg.edit_text(f"Broadcast Completed: \nCompleted in `{completed_in}`.\n\nTotal Users: {total_users}\nCompleted: {done} / {total_users}\nSuccess: {success}\nFailed: {failed}")


    elif command in ["status", "stats"]:
        if not hasattr(b, 'uptime'):
            b.uptime = time.time()
        total_users = await hyoshcoder.total_users_count()
        uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - b.uptime))
        start_t = time.time()
        st = await m.reply('**Accessing The Details.....**')
        end_t = time.time()
        time_taken_s = (end_t - start_t) * 1000
        await st.edit_text(
            f"**--Bot Status--** \n\n"
            f"**⌚️ Bot Uptime :** {uptime} \n"
            f"**🐌 Current Ping :** `{time_taken_s:.3f} ms` \n"
            f"**👭 Total Users :** `{total_users}`"
        )

    elif command == "users":
        all_users = await hyoshcoder.get_all_users()
        user_count = 0
        text = ''
        async for user in all_users:
            user_count += 1
            text += f"> **user_id**: `{user['_id']}`\n\n"

        reply_text = f"Total Users: `{user_count}`\n\n{text}"
        if len(reply_text) > 4096:
            with open('users.txt', 'w') as f:
                f.write(reply_text)
            await m.reply_document('users.txt', caption="Users list")
            os.remove('users.txt')
        else:
            await m.reply_text(reply_text, quote=True)


async def send_msg(user_id: int, message: Message):
    try:
        await message.copy(chat_id=user_id)
        return 200
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await send_msg(user_id, message)
    except InputUserDeactivated:
        logger.info(f"{user_id} : Deactivated")
        return 400
    except UserIsBlocked:
        logger.info(f"{user_id} : Blocked The Bot")
        return 400
    except PeerIdInvalid:
        logger.info(f"{user_id} : User ID Invalid")
        return 400
    except Exception as e:
        logger.error(f"{user_id} : {e}")
        return 500