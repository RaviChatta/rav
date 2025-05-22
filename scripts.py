class Scripts():
    
    PROGRESS_BAR = """⚡ <b>File Processing Progress</b> ⚡

▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
<b>📊 Progress:</b> {0}%
<b>📦 Size:</b> {1} / {2}
<b>🚀 Speed:</b> {3}/s
<b>⏳ Time Left:</b> {4}

<b>🔹 Status:</b> Renaming in progress..."""

    START_TXT = """
✨ <b>WELCOME TO THE FUTURE OF FILE MANAGEMENT</b> ✨

<b>Hello {}!</b>

I'm <b>AutoRename Pro</b>, your ultimate file transformation assistant. Here's why I'm different:

⚡ <b>Lightning-Fast Processing</b> - Rename 1000s of files in seconds
🎨 <b>Smart Formatting</b> - Automatic episode/season detection
🔒 <b>Military-Grade Security</b> - Your files stay private
💎 <b>Premium Features</b> - Unlimited capabilities for power users

<b>🚀 Ready to experience file management like never before?</b>"""

    FILE_NAME_TXT = """
🔮 <b>SMART RENAMING WIZARD</b> 🔮

<b>Available Magic Variables:</b>
✨ <code>[episode]</code> - Auto-detects episode numbers
✨ <code>[season]</code> - Identifies season information
✨ <code>[quality]</code> - Extracts quality (1080p, 4K, etc.)
✨ <code>[date]</code> - Adds current date
✨ <code>[time]</code> - Includes processing time

<b>🔥 Example Power Formats:</b>
<code>/autorename [Anime] S[season]E[episode] [quality]</code>
<code>/autorename [Movie] [year] [quality] Dual Audio</code>
<code>/autorename [Series] S[season] EP[episode] [resolution]</code>

<b>💡 Pro Tip:</b> Combine variables for ultimate customization!"""

    ABOUT_TXT = f"""
🌌 <b>ABOUT THIS COSMIC TECHNOLOGY</b> 🌌

<b>⚡ Power Core:</b> <a href="https://www.python.org/">Python 3.11</a>
<b>🧠 Neural Network:</b> <a href="https://pyrogram.org/">Pyrogram</a>
<b>🚀 Host Platform:</b> <a href="https://t.me/REQUETE_ANIME_30sbot">Quantum Cloud</a>

<b>👨‍💻 Master Architect:</b> <a href="https://t.me/altof2">Dr. Al Tofu</a>
<b>🔮 Version:</b> 7.1.3 (Stable)
<b>📅 Last Updated:</b> Yesterday at 23:61

<b>💫 Special Thanks:</b> To all cosmic entities who made this possible"""

    THUMBNAIL_TXT = """
🎨 <b>THUMBNAIL CUSTOMIZATION CENTER</b> 🎨

<b>Transform your files with stunning visuals:</b>

🖼️ <b>Set Thumbnail:</b> Just send any image
🗑️ <b>Remove:</b> <code>/del_thumb</code>
👀 <b>Preview:</b> <code>/view_thumb</code>

<b>🌈 Pro Features:</b>
• Auto-cropping to perfect aspect ratio
• Smart contrast enhancement
• Batch thumbnail application

<b>Note:</b> Thumbnails are stored in our quantum encrypted servers"""

    CAPTION_TXT = """
📝 <b>CAPTION MASTER CONTROL</b> 📝

<b>Available Smart Tags:</b>
<code>{filesize}</code> - Auto-formatted file size
<code>{duration}</code> - Clever duration display
<code>{filename}</code> - Original file name
<code>{date}</code> - Processing date stamp

<b>🎯 Example Captions:</b>
<code>/set_caption 🎬 {filename} | ⏱️ {duration}</code>
<code>/set_caption 📦 {filesize} | 🗓️ {date}</code>

<b>💎 Premium Feature:</b> Dynamic caption templates"""

    DONATE_TXT = """
💖 <b>SUPPORT OUR COSMIC MISSION</b> 💖

<b>Your support fuels our innovation:</b>

💰 <b>Donation Tiers:</b>
• 🌟 Stellar Supporter: $10
• 🚀 Galactic Patron: $25
• 🌌 Cosmic Benefactor: $50+

<b>Payment Options:</b>
• Cryptocurrency (BTC/ETH)
• PayPal
• Direct Transfer

<b>📩 Contact:</b> @REQUETE_ANIME_30sbot for details

<b>All donors receive:</b>
• Priority support
• Beta feature access
• Cosmic gratitude"""

    PREMIUM_TXT = """
💎 <b>UNLOCK THE COSMIC EDITION</b> 💎

<b>Premium Features Include:</b>
⚡ Unlimited parallel processing
🌌 Advanced metadata editing
🔮 AI-powered smart renaming
🚀 Priority queue access
💎 Exclusive variable tags

<b>Activation Process:</b>
1. Choose your plan with /plan
2. Make payment to @altof2
3. Send receipt with /bought

<b>⚡ Instant activation guaranteed!</b>"""

    PREPLANS_TXT = """
💰 <b>COSMIC PREMIUM PLANS</b> 💰

<b>🚀 BASIC</b> ($3.99/month)
• 1000 renames/day
• Standard support

<b>💎 PRO</b> ($9.99/month)
• 5000 renames/day
• Priority support
• Advanced variables

<b>🌌 ULTIMATE</b> ($19.99/month)
• Unlimited renames
• 24/7 VIP support
• AI SmartNaming™
• Beta features

<b>Payment:</b> @REQUETE_ANIME_30sbot
<b>Questions?</b> @altof2"""

    HELP_TXT = """
🛠️ <b>COMMAND CONTROL CENTER</b> 🛠️

<b>Core Commands:</b>
• /autorename - Smart file transformer
• /metadata - MKV magic editor
• /set_dump - Configure output channel
• /profile - View your stats

<b>⚙️ Settings:</b>
• /thumbnail - Visual customization
• /caption - Text formatting
• /sequential - File ordering

<b>💎 Premium:</b>
• /premium - Upgrade options
• /bought - Submit payment

<b>Need help?</b> @REQUETE_ANIME_30sbot"""

    SEND_METADATA = """
🔮 <b>METADATA MASTERY</b> 🔮

<b>Advanced MKV Control:</b>
• Edit all stream titles
• Modify audio/subtitle tracks
• Add custom chapters
• Embed cover art

<b>Usage:</b>
<code>/metadata on</code> - Enable magic
<code>/metadata off</code> - Disable

<b>Note:</b> Works with all MKV/MP4 files"""

    SOURCE_TXT = """
🌠 <b>THE TECHNOLOGY BEHIND THE MAGIC</b> 🌠

<b>Powered by:</b>
• Quantum Python Core
• Neural Renaming Algorithms
• Cloud Processing Matrix

<b>Developed with:</b> 
• 97% Pure Python
• 2% Dark Matter
• 1% Cosmic Energy

<b>⚡ Performance:</b>
• 0.001ms average response
• 99.9999% uptime
• Infinite scalability"""

Txt = Scripts()
