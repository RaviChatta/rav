import re
from typing import Optional, Tuple, Dict

# Patterns for extracting season and episode numbers
SEASON_EPISODE_PATTERNS = [
    # Pattern 1: S01E02 or S01EP02
    re.compile(r'S(\d+)(?:E|EP)(\d+)', re.IGNORECASE),
    # Pattern 2: S01 E02 or S01 EP02 or S01 - E01 or S01 - EP02
    re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)', re.IGNORECASE),
    # Pattern 3: Episode Number After "E" or "EP"
    re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)', re.IGNORECASE),
    # Pattern 3_2: Episode number after - [hyphen]
    re.compile(r'(?:\s*-\s*(\d+)\s*)', re.IGNORECASE),
    # Pattern 4: S2 09 ex.
    re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE),
    # Pattern 17: Episode number in "épisode X" or "saison X épisode Y"
    re.compile(r'(?:saison\s*(\d+)\s*)?épisode\s*(\d+)', re.IGNORECASE),
    # Pattern X: Standalone Episode Number
    re.compile(r'(\d+)', re.IGNORECASE),
    # Nouveau Pattern: S01 - E02
    re.compile(r'S(\d+)\s*-\s*E(\d+)', re.IGNORECASE),
]

# Patterns for extracting quality
QUALITY_PATTERNS = {
    # Pattern 5: 3-4 digits before 'p' as quality
    re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE): lambda match: match.group(1) or match.group(2),
    # Pattern 6: Find 4k in brackets or parentheses
    re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE): lambda _: "4k",
    # Pattern 7: Find 2k in brackets or parentheses
    re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE): lambda _: "2k",
    # Pattern 8: Find HdRip without spaces
    re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE): lambda _: "HdRip",
    # Pattern 9: Find 4kX264 in brackets or parentheses
    re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE): lambda _: "4kX264",
    # Pattern 10: Find 4kx265 in brackets or parentheses
    re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE): lambda _: "4kx265",
    # Pattern 11: Find UHD in brackets or parentheses
    re.compile(r'[([<{]?\s*UHD\s*[)\]>}]?', re.IGNORECASE): lambda _: "UHD",
    # Pattern 12: Find HD in brackets or parentheses
    re.compile(r'[([<{]?\s*HD\s*[)\]>}]?', re.IGNORECASE): lambda _: "HD",
    # Pattern 13: Find SD in brackets or parentheses
    re.compile(r'[([<{]?\s*SD\s*[)\]>}]?', re.IGNORECASE): lambda _: "SD",
    # Patterns 14-16: Find "convertie", "converti", or "convertis"
    re.compile(r'[([<{]?\s*convertie\s*[)\]>}]?', re.IGNORECASE): lambda _: "convertie",
    re.compile(r'[([<{]?\s*converti\s*[)\]>}]?', re.IGNORECASE): lambda _: "convertie",
    re.compile(r'[([<{]?\s*convertis\s*[)\]>}]?', re.IGNORECASE): lambda _: "convertie",
}

async def extract_season_episode(filename: str) -> Optional[Tuple[int, int]]:
    """
    Extracts the season and episode numbers from a filename asynchronously.
    Returns a tuple (season, episode) if found, otherwise None.
    """
    for pattern in SEASON_EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            print(f"Matched Pattern: {pattern.pattern}")
            # Default season to 1 if not captured
            season = int(match.group(1)) if match.group(1) else 1
            # Extract episode (group 2 or group 1 if only one group exists)
            episode = int(match.group(2)) if match.lastindex >= 2 else int(match.group(1))
            return season, episode
    return None

async def extract_quality(filename: str) -> str:
    """
    Extracts the quality from a filename asynchronously.
    Returns the quality as a string, or "Unknown" if no match is found.
    """
    for pattern, extractor in QUALITY_PATTERNS.items():
        match = pattern.search(filename)
        if match:
            print(f"Matched Pattern: {pattern.pattern}")
            return extractor(match)
    return "Unknown"


# # Example usage
# import asyncio

# async def main():
#     filename = "Naruto Shippuden S01 - EP07 - convertie [Dual Audio] @hyoshassistantbot.mkv"
#     season_episode = await extract_season_episode(filename)
#     quality = await extract_quality(filename)

#     if season_episode:
#         season, episode = season_episode
#         print(f"Season: {season}, Episode: {episode}")
#     else:
#         print("No season or episode found.")

#     print(f"Quality: {quality}")

# # Run the async main function
# asyncio.run(main())