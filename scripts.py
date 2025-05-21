class Scripts():
    
    PROGRESS_BAR = """\n
<b>» Size</b> : {1} | {2}  
<b>» Done</b> : {0}%  
<b>» Speed</b> : {3}/s  
<b>» ETA</b> : {4}"""

    START_TXT = """
<b>Hello! {}  

I am a bot designed to help you automate your file renaming tasks with precision.

» I ensure your files are renamed accurately and stylishly.  
» Add a personalized caption, an elegant thumbnail, and let me sequence your files perfectly.  
</b>
"""

    FILE_NAME_TXT = """<b>» <u>Configure Auto-Rename Format</u></b>

<b>Variables:</b>
➲ episode - To replace the episode number  
➲ season - To replace the season number
➲ quality - To replace the quality  

<b>‣ Example :- </b> <code> /autorename one punch man [Sseason - EPepisode - [Quality] [Dual]  </code>

<b>‣ /autorename : Rename your multimedia files including 'episode' and 'quality' variables in your text, to extract the episode and quality present in the original filename.</b>"""

    ABOUT_TXT = f"""<b>❍ My Name : <a href="https://t.me/REQUETE_ANIME_30sbot">Auto Rename Bot</a>  
🧑‍💼Developer : <a href="https://t.me/altof2">Partner</a>  
💫 GitHub : <a href="https://github.com/sineur_x_bot">Private Bot</a>  
⚡️ Language : <a href="https://www.python.org/">Python</a>  
📁 Database : <a href="https://t.me/REQUETE_ANIME_30sbot/">Sineur Cloud</a>  
🔺 Hosted On : <a href="https://t.me/REQUETE_ANIME_30sbot">Box Cloud</a>  
🎞️ Bot Channel : <a href="https://t.me/sineur_x_bot">Bug Channel</a>  

➻ Click on the buttons below to get help and basic information about me.</b>"""

    THUMBNAIL_TXT = """<b><u>» To Set a Custom Thumbnail</u></b>
    
➲ /start : Send any photo to automatically set it as your thumbnail.
➲ /del_thumb : Use this command to delete your old thumbnail.
➲ /view_thumb : Use this command to view your current thumbnail.

Note: If no thumbnail is registered in the bot, the original file's thumbnail will be used for the renamed file."""

    CAPTION_TXT = """<b><u>» To Set a Custom Caption and Media Type</u></b>
    
<b>Variables:</b>         
Size: <code>{filesize}</code>  
Duration: <code>{duration}</code>  
Filename: <code>{filename}</code>

➲ /set_caption : To set a custom caption.  
➲ /see_caption : To view your custom caption.  
➲ /del_caption : To delete your custom caption.

» Example :- /set_caption File Name: {filename}"""

    DONATE_TXT = """<blockquote>Thank you for showing interest in donations</blockquote>

<b><i>💞 If you love our bot, don't hesitate to make a donation of any amount 10⭐️, $20⭐️, $50, $100, etc.</i></b>

Donations are truly appreciated and help with bot development.

<u>You can make a donation </u>

Pay here - <code> @altof2 </code>

If you do, you can send us screenshots
to - @REQUETE_ANIME_30sbot"""

    PREMIUM_TXT = """<b>Upgrade to our Premium service and enjoy exclusive features:
○ Unlimited Renaming: Rename as many files as you want without restrictions.
○ Early Access: Be the first to test and use our advanced features before everyone else.

• Use /plan to see all our plans at a glance.

➲ First Step: Pay the amount corresponding to your preferred plan to 

➲ Second Step: Take a screenshot of your payment and share it directly here: @REQUETE_ANIME_30sbot 

➲ Alternative: Or upload the screenshot here and reply with the command /bought.

Your premium plan will be activated after verification.</b>"""

    PREPLANS_TXT = """<b>👋 Hello,

🎖️ <u>Available Plans</u> :

Pricing:
➜ Monthly Premium: $3.99/month
➜ Daily Premium: $0.99/day
➜ For bot hosting: contact @altof2

➲ Pay here - <code> @REQUETE_ANIME_30sbot </code>

‼️Upload the payment screenshot here and reply with the command /bought.</b>"""

    HELP_TXT = """<b>Here is the help menu with important commands:

Impressive Features🫧

The rename bot is a practical tool that helps you easily rename and manage your files.

➲ /autorename : Automatically rename your files.
➲ /metadata : Commands to enable/disable metadata.
➲ /help : Get quick help.
➲ /set_dump : To set the dump channel (where your files will be sent once renamed)

Note: Make sure to activate sequential mode so the bot can sort and send files in the correct order."""

    SEND_METADATA = """
<b>--Metadata Parameters--</b>

➜ /metadata : Enable or remove metadata.

<b>Description</b>: Metadata will modify MKV video files, including all audio titles, streams and subtitles.""" 

    SOURCE_TXT = """
<b>Hello,
  I am an automatic rename bot,
a Telegram bot for automatic renaming.</b>
""" 

Txt = Scripts()
