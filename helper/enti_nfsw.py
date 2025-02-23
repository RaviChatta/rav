nsfw_keywords = {
    "general": [
        "porn", "sex", "nude", "naked", "boobs", "tits", "pussy", "dick", "cock", "ass",
        "fuck", "blowjob", "cum", "orgasm", "shemale", "erotic", "masturbate", "anal",
        "hardcore", "bdsm", "fetish", "lingerie", "xxx", "milf", "gay", "lesbian",
        "threesome", "squirting", "butt plug", "dildo", "vibrator", "escort", "handjob",
        "striptease", "kinky", "pornstar", "sex tape", "spank", "swinger", "taboo", "cumshot",
        "deepthroat", "domination", "submission", "handcuffs", "orgy", "roleplay", "sex toy",
        "voyeur", "cosplay", "adult", "culture", "pornhwa",
        "netorare", "netori", "netorase", "eromanga", "incest", "stepmom", "stepdad",
        "stepsister", "stepbrother", "stepson", "stepdaughter", "ntr", "gangbang",
        "facial", "golden shower", "pegging", "rimming", "rough sex", "dirty talk",
        "sex chat", "nude pic", "lewd", "titty", "twerk", "breasts", "penis", "vagina",
        "clitoris", "genitals", "sexual", "kamasutra", "incest", "pedo", "rape", "bondage",
        "cum inside", "creampie", "sex slave", "sex doll", "sex machine", "latex", "oral sex",
        "butt", "slut", "whore", "tramp", "skank", "cumdumpster", "cultured", "ecchi", "doujin",
        "hentai", "smut", "lewd", "waifu", "futanari", "tentacle"
    ],
    "hentai": [
        "hentai", "doujinshi", "ecchi", "yaoi", "shota", "loli", "tentacle", "futanari",
        "bishoujo", "bishounen", "mecha hentai", "hentai manga", "hentai anime", "smut",
        "eroge", "visual novel", "h-manga", "h-anime", "adult manga", "18+ anime", "18+ manga",
        "lewd anime", "lewd manga", "animated porn", "animated sex", "hentai game", "hentai art",
        "hentai drawing", "hentai doujin", "yaoi hentai", "hentai comic",
        "hentai picture", "hentai scene", "hentai story", "hentai video", "hentai movie",
        "hentai episode", "hentai series"
    ],
    "abbreviations": [
        "pr0n", "s3x", "n00d", "fck", "bj", "hj", "l33t", "p0rn", "h3ntai", "h-ntai", "pnwh",
        "p0rnhwa", "l33tsp34k", "l3wd", "cultur3d", "s3xual"
    ],
    "offensive_slang": [
        "slut", "whore", "tramp", "skank", "cumdumpster", "gangbang", "facial", "golden shower",
        "pegging", "rimming", "rough sex", "dirty talk", "sex chat", "nude pic", "lewd", "titty",
        "twerk", "breasts", "penis", "vagina", "clitoris", "genitals", "sexual", "kamasutra",
        "incest", "pedo", "rape", "sex slave", "bondage", "creampie", "cum inside", "sex doll",
        "sex machine", "latex", "oral sex", "cumshot", "deepthroat", "domination", "submission",
        "handcuffs", "orgy", "roleplay", "sex toy", "voyeur", "cosplay", "adult", "culture",
        "anal", "erotic", "masturbate", "hardcore", "bdsm", "fetish", "lingerie", "milf", "taboo"
    ]
}

exception_keywords = ["nxivm", "classroom", "assassination", "geass"]

async def check_anti_nsfw(new_name: str, message) -> bool:
    """
    Vérifie si un nom de fichier contient du contenu NSFW en utilisant une liste de mots-clés.
    Si un mot-clé NSFW est trouvé, envoie un message d'avertissement.

    :param new_name: Le nom de fichier à vérifier.
    :param message: L'objet message pour répondre à l'utilisateur.
    :return: True si du contenu NSFW est détecté, False sinon.
    """
    try:
        lower_name = new_name.lower()

        for keyword in exception_keywords:
            if keyword.lower() in lower_name:
                return False  

        for category, keywords in nsfw_keywords.items():
            for keyword in keywords:
                if keyword.lower() in lower_name:
                    await message.reply_text(
                        f"⚠️ **Du contenue NSFW Detecté**\n"
                        f"Votre fichier contient du contenue pour adulte.\n"
                        f"Ce contenue sont interdit sur ce bot.\n"
                    )
                    return True 

        return False  

    except Exception as e:
        print(f"Error in check_anti_nsfw: {e}")
        return False  