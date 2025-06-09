import motor.motor_asyncio
import datetime
import pytz
import secrets
import asyncio
from config import settings
from pyrogram import Client
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any
from bson.objectid import ObjectId
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError, ConnectionFailure
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)
Config = settings

class Database:
def __init__(self, uri: str, database_name: str):
"""Initialize database connection with enhanced settings."""
self._uri = uri
self._database_name = database_name
self._client = None
self._pyrogram_client = None
self.db = None
self._is_connected = False
# Initialize collection references
self.users = None
self.premium_codes = None
self.transactions = None
self.rewards = None
self.point_links = None
self.leaderboards = None
self.file_stats = None
self.config = None
self.campaigns = None
async def connect(self, max_pool_size: int = 100, min_pool_size: int = 10, max_idle_time_ms: int = 30000):
"""Establish database connection with enhanced settings and error handling."""
try:
self._client = motor.motor_asyncio.AsyncIOMotorClient(
self._uri,
serverSelectionTimeoutMS=5000,
connectTimeoutMS=30000,
socketTimeoutMS=30000,
maxPoolSize=max_pool_size,
minPoolSize=min_pool_size,
maxIdleTimeMS=max_idle_time_ms,
retryWrites=True,
retryReads=True
)

# Test connection
await self._client.admin.command('ping')
logger.info("✅ Successfully connected to MongoDB")

# Initialize database and collections
self.db = self._client[self._database_name]
self.users = self.db.users
self.premium_codes = self.db.premium_codes
self.transactions = self.db.transactions
self.rewards = self.db.rewards
self.point_links = self.db.point_links
self.leaderboards = self.db.leaderboards
self.file_stats = self.db.file_stats
self.config = self.db.config
self.campaigns = self.db.campaigns
self._is_connected = True

# Create indexes
await self._create_indexes()
return True

except (ServerSelectionTimeoutError, ConnectionFailure) as e:
logger.error(f"❌ Failed to connect to MongoDB: {e}")
raise ConnectionError(f"Database connection failed: {e}") from e
except PyMongoError as e:
logger.error(f"❌ MongoDB error: {e}")
raise
except Exception as e:
logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
raise

@asynccontextmanager
async def session(self):
"""Provide a transactional scope around a series of operations."""
async with await self._client.start_session() as session:
async with session.start_transaction():
try:
yield session
except Exception as e:
await session.abort_transaction()
raise e

async def _create_indexes(self):
"""Create optimized indexes for all collections with campaign support."""
indexes = [
# Users collection (enhanced for campaigns)
("users", [("referrer_id", 1)]),
("users", [("ban_status.is_banned", 1)]),
("users", [("points.balance", -1)]),
("users", [("activity.total_files_renamed", -1)]),
("users", [("premium.is_premium", 1)]),
("users", [("activity.last_ad_view", -1)]),  # New for ad rate limiting

# Point links (enhanced for campaigns)
("point_links", [("code", 1)], {
"unique": True,
"partialFilterExpression": {"used": False}
}),
("point_links", [("expires_at", 1)]),
("point_links", [("user_id", 1), ("expires_at", 1)]),
("point_links", [("campaign_id", 1)]),  # New for campaign tracking

# New campaigns collection indexes
("campaigns", [("code", 1)], {"unique": True}),
("campaigns", [("owner_id", 1)]),
("campaigns", [("expires_at", 1)]),
("campaigns", [("active", 1), ("expires_at", 1)]),
("campaigns", [("used_views", 1), ("total_views", 1)]),

# Transactions (enhanced for ad tracking)
("transactions", [("user_id", 1), ("timestamp", -1)]),
("transactions", [("type", 1), ("timestamp", -1)]),
("transactions", [("campaign_id", 1)]),  # New for ad analytics
("transactions", [("reference_id", 1)], {"unique": True, "sparse": True}),

# Leaderboards (unchanged)
("leaderboards", [("period", 1), ("type", 1), ("updated_at", -1)]),

# File stats (unchanged)
("file_stats", [("user_id", 1)]),
("file_stats", [("date", 1)]),
("file_stats", [("timestamp", -1)]),

# Config (unchanged)
("config", [("key", 1)], {"unique": True})
]

for entry in indexes:
collection, keys, *options = entry if len(entry) > 2 else [*entry, {}]
opts = options[0] if options else {}
try:
await self.db[collection].create_index(keys, **opts)
logger.debug(f"Created index on {collection} for {keys}")
except Exception as e:
logger.error(f"Failed to create index on {collection}: {e}")
# For critical indexes, you might want to raise the exception
if collection == "campaigns" and "code" in keys:
raise

def set_client(self, client: Client):
"""Store the Pyrogram client for Telegram API calls"""
self._pyrogram_client = client
logger.info("Pyrogram client set for database operations")

def new_user(self, id: int) -> Dict[str, Any]:
"""Create a new user document with ad campaign support."""
now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
return {
"_id": int(id),
"username": None,
"join_date": now.isoformat(),
# Media settings
"file_id": None,
"caption": None,
"metadata": True,
"metadata_code": None,
"format_template": None,

# Ban status
"ban_status": {
"is_banned": False,
"ban_duration": 0,
"banned_on": None,
"ban_reason": '',
"unbanned_by": None,
"unban_reason": None
},

# Points system (enhanced for ad campaigns)
"points": {
"balance": 70,
"total_earned": 70,
"total_spent": 0,
"last_earned": now.isoformat(),
"sources": {
"ads": 0,
"referrals": 0,
"uploads": 0,
"bonuses": 0
}
},

# Premium features
"premium": {
"is_premium": False,
"since": None,
"until": None,
"plan": None,
"payment_method": None,
"ad_multiplier": 1.0  # New field for ad point multipliers
},

# Referral system (compatible with ad campaigns)
"referral": {
"referrer_id": None,
"referred_count": 0,
"referral_earnings": 0,
"referred_users": [],
"ad_codes": []  # New field for tracking shared ad links
},

# User settings
"settings": {
"sequential_mode": False,
"user_channel": None,
"src_info": "file_name",
"language": "en",
"notifications": True,
"leaderboard_period": "weekly",
"leaderboard_type": "points",
"ad_notifications": True  # New field for ad notifications
},

# Activity tracking (enhanced for ads)
"activity": {
"last_active": now.isoformat(),
"total_files_renamed": 0,
"daily_usage": 0,
"last_usage_date": None,
"ad_views": 0,  # New field
"ad_earnings": 0,  # New field
"last_ad_view": None  # New field
},

# Security
"security": {
"two_factor": False,
"last_login": None,
"login_history": [],
"ad_ratelimit": None  # New field for rate limiting ads
},

# Ad campaign management (new section)
"campaigns": {
"created": 0,
"active": [],
"total_spent": 0,
"total_views": 0
},

# System flags
"deleted": False,
"deleted_at": None,
"flags": {
"ad_verified": False,  # New field for ad verification status
"ad_ban": False  # New field for ad abuse prevention
}
}
async def add_user(self, id: int) -> bool:
"""Add a new user with comprehensive initialization."""
try:
if await self.is_user_exist(id):
return False

user_data = self.new_user(id)
await self.users.insert_one(user_data)
logger.info(f"Added new user: {id}")
return True
except PyMongoError as e:
logger.error(f"Error adding user {id}: {e}")
return False

async def is_user_exist(self, id: int) -> bool:
"""Check if user exists in database."""
try:
user = await self.users.find_one({"_id": int(id)})
return bool(user)
except Exception as e:
logger.error(f"Error checking if user {id} exists: {e}")
return False

async def get_user(self, id: int) -> Optional[Dict[str, Any]]:
"""Get user document by ID with proper error handling."""
try:
return await self.users.find_one({"_id": int(id)})
except PyMongoError as e:
logger.error(f"Error getting user {id}: {e}")
return None
    async def create_campaign(self, owner_id: int, name: str, points_per_view: int, total_views: int):
        """Create a new ad campaign"""
        campaign_id = str(uuid.uuid4())
        code = str(uuid.uuid4())[:8]
        
    async def create_campaign(self, owner_id: int, name: str, points: int, max_views: int):
        """Create a new campaign with proper datetime handling"""
campaign = {
            "_id": campaign_id,
            "_id": str(uuid.uuid4()),
            "code": str(uuid.uuid4())[:8],
"owner_id": owner_id,
"name": name,
            "points_per_view": points_per_view,
            "total_views": total_views,
            "points_per_view": points,
            "max_views": max_views,
"used_views": 0,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=7),
            "code": code,
            "created_at": datetime.now(pytz.UTC),
            "expires_at": datetime.now(pytz.UTC) + timedelta(days=7),
"active": True
}
        
await self.campaigns.insert_one(campaign)
        return code
        return campaign["code"]

async def get_campaign_by_code(self, code: str):
"""Get campaign by its redemption code"""
return await self.campaigns.find_one({"code": code, "active": True})
async def get_user_by_code(self, unique_code: str) -> Optional[Dict]:
"""Find user by their unique referral/ad code if it's not already used."""
user = await self.users.find_one({
"unique_code": unique_code,
"$or": [
{"code_used": {"$exists": False}},  # code_used not set
{"code_used": False}                # code_used is False
]
})
return user

async def mark_ad_code_used(self, code: str) -> None:
"""Mark an ad code as used"""
await self.users.update_one(
{"ad_code": code},
{"$set": {"ad_code_used": True}}
)

async def update_user_activity(self, user_id: int) -> bool:
"""Update user's last active timestamp."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"activity.last_active": datetime.datetime.now()}}
)
return True
except PyMongoError as e:
logger.error(f"Error updating activity for {user_id}: {e}")
return False

async def get_all_users(self, filter_banned: bool = False) -> AsyncGenerator[Dict[str, Any], None]:
"""Async generator to get all users with optional banned filter."""
query = {"deleted": False}
if filter_banned:
query["ban_status.is_banned"] = False

try:
async for user in self.users.find(query):
yield user
except PyMongoError as e:
logger.error(f"Error getting users: {e}")
raise

async def close(self):
"""Close the database connection."""
try:
if self._client:
self._client.close()
logger.info("Database connection closed")
except Exception as e:
logger.error(f"Error closing database connection: {e}")

async def total_users_count(self) -> int:
"""Get total number of users."""
try:
return await self.users.count_documents({})
except Exception as e:
logger.error(f"Error counting users: {e}")
return 0

async def total_banned_users_count(self) -> int:
"""Get total number of banned users."""
try:
return await self.users.count_documents({"ban_status.is_banned": True})
except Exception as e:
logger.error(f"Error counting banned users: {e}")
return 0

async def total_premium_users_count(self) -> int:
"""Get total number of premium users."""
try:
return await self.users.count_documents({"premium.is_premium": True})
except Exception as e:
logger.error(f"Error counting premium users: {e}")
return 0

async def get_daily_active_users(self) -> int:
"""Get count of daily active users."""
try:
today = datetime.datetime.now().date()
return await self.users.count_documents({
"activity.last_active": {
"$gte": datetime.datetime.combine(today, datetime.time.min)
}
})
except Exception as e:
logger.error(f"Error counting daily active users: {e}")
return 0

async def read_user(self, id: int) -> Optional[Dict]:
"""Get user document by ID."""
try:
return await self.users.find_one({"_id": int(id)})
except Exception as e:
logger.error(f"Error reading user {id}: {e}")
return None

async def delete_user(self, user_id: int) -> bool:
"""Delete user data (soft delete)."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"deleted": True, "deleted_at": datetime.datetime.now()}}
)
return True
except Exception as e:
logger.error(f"Error deleting user {user_id}: {e}")
return False

async def set_thumbnail(self, user_id: int, file_id: str) -> bool:
"""Set user's thumbnail."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"file_id": file_id}}
)
return True
except Exception as e:
logger.error(f"Error setting thumbnail for {user_id}: {e}")
return False

async def get_thumbnail(self, user_id: int) -> Optional[str]:
"""Get user's thumbnail."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("file_id") if user else None
except Exception as e:
logger.error(f"Error getting thumbnail for {user_id}: {e}")
return None

async def set_caption(self, user_id: int, caption: str) -> bool:
"""Set user's default caption."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"caption": caption}}
)
return True
except Exception as e:
logger.error(f"Error setting caption for {user_id}: {e}")
return False

async def get_caption(self, user_id: int) -> Optional[str]:
"""Get user's default caption."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("caption") if user else None
except Exception as e:
logger.error(f"Error getting caption for {user_id}: {e}")
return None

async def set_metadata_code(self, user_id: int, metadata_code: str) -> bool:
"""Set user's metadata code."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"metadata_code": metadata_code}}
)
return True
except Exception as e:
logger.error(f"Error setting metadata code for {user_id}: {e}")
return False

async def get_metadata_code(self, user_id: int) -> Optional[str]:
try:
if not self._is_connected:
return None
user = await self.users.find_one({"_id": user_id})
return user.get("metadata_code") if user else None
except Exception as e:
logger.error(f"Error getting metadata code: {e}")
return None

async def set_format_template(self, user_id: int, format_template: str) -> bool:
"""Set user's format template."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"format_template": format_template}}
)
return True
except Exception as e:
logger.error(f"Error setting format template for user {user_id}: {e}")
return False

async def get_format_template(self, user_id: int) -> Optional[str]:
"""Get user's format template."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("format_template") if user else None
except Exception as e:
logger.error(f"Error getting format template for user {user_id}: {e}")
return None

async def set_media_preference(self, user_id: int, media_type: str) -> bool:
"""Set user's media preference."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"media_type": media_type}}
)
return True
except Exception as e:
logger.error(f"Error setting media preference for user {user_id}: {e}")
return False

async def get_media_preference(self, user_id: int) -> Optional[str]:
"""Get user's media preference."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("media_type") if user else None
except Exception as e:
logger.error(f"Error getting media preference for user {user_id}: {e}")
return None

async def set_metadata(self, user_id: int, bool_meta: bool) -> bool:
"""Set user's metadata setting."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"metadata": bool_meta}}
)
return True
except Exception as e:
logger.error(f"Error setting metadata for user {user_id}: {e}")
return False

async def get_metadata(self, user_id: int) -> bool:
"""Get user's metadata setting."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("metadata", True) if user else True
except Exception as e:
logger.error(f"Error getting metadata for user {user_id}: {e}")
return True

async def set_src_info(self, user_id: int, src_info: str) -> bool:
"""Set user's source info preference."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"settings.src_info": src_info}}
)
return True
except Exception as e:
logger.error(f"Error setting src_info for {user_id}: {e}")
return False

async def toggle_src_info(self, user_id: int) -> str:
"""Toggle source info preference for a user."""
current_setting = await self.get_src_info(user_id) or "file_name"
new_setting = "file_caption" if current_setting == "file_name" else "file_name"
await self.set_src_info(user_id, new_setting)
return new_setting

async def get_src_info(self, user_id: int) -> Optional[str]:
"""Get user's source info preference."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("settings", {}).get("src_info") if user else None
except Exception as e:
logger.error(f"Error getting src_info for {user_id}: {e}")
return None

async def track_file_rename(self, user_id: int, file_name: str, new_name: str) -> bool:
"""Track a file rename operation."""
try:
# Insert the rename record
result = await self.file_stats.insert_one({
"user_id": user_id,
"original_name": file_name,
"new_name": new_name,
"timestamp": datetime.datetime.now(),
"date": datetime.datetime.now().date().isoformat()
})

# Also update the user's total rename count
await self.users.update_one(
{"_id": user_id},
{"$inc": {"activity.total_files_renamed": 1}}
)

return result.inserted_id is not None

except Exception as e:
logger.error(f"Error tracking file rename for user {user_id}: {e}")
return False

async def get_user_rename_stats(self, user_id: int) -> Dict:
"""Get comprehensive rename statistics for a user"""
stats = {
"total": 0,
"today": 0,
"this_week": 0,
"this_month": 0,
"daily_usage": 0
}

try:
# Get basic user stats
user = await self.users.find_one({"_id": user_id})
if not user:
return stats

stats["total"] = user["activity"].get("total_files_renamed", 0)
stats["daily_usage"] = user["activity"].get("daily_usage", 0)

# Calculate time-based stats
today = datetime.datetime.now().date()
start_of_week = today - datetime.timedelta(days=today.weekday())
start_of_month = datetime.date(today.year, today.month, 1)

stats["today"] = await self.file_stats.count_documents({
"user_id": user_id,
"date": today.isoformat()
})

stats["this_week"] = await self.file_stats.count_documents({
"user_id": user_id,
"date": {"$gte": start_of_week.isoformat()}
})

stats["this_month"] = await self.file_stats.count_documents({
"user_id": user_id,
"date": {"$gte": start_of_month.isoformat()}
})

return stats

except Exception as e:
logger.error(f"Error getting rename stats: {e}")
return stats

async def reset_daily_usage(self):
"""Reset daily usage counters for all users (run as a daily job)"""
try:
await self.users.update_many(
{},
{"$set": {"activity.daily_usage": 0}}
)
logger.info("Reset daily usage counters for all users")
return True
except Exception as e:
logger.error(f"Error resetting daily usage: {e}")
return False

async def get_user_file_stats(self, user_id: int) -> Dict:
"""Get user's file rename statistics."""
stats = {
"total_renamed": 0,
"today": 0,
"this_week": 0,
"this_month": 0
}

try:
user = await self.users.find_one({"_id": user_id})
if not user:
return stats

stats["total_renamed"] = user["activity"].get("total_files_renamed", 0)

today = datetime.datetime.now().date()
start_of_week = today - datetime.timedelta(days=today.weekday())
start_of_month = datetime.date(today.year, today.month, 1)

stats["today"] = await self.file_stats.count_documents({
"user_id": user_id,
"date": today.isoformat()
})

stats["this_week"] = await self.file_stats.count_documents({
"user_id": user_id,
"date": {"$gte": start_of_week.isoformat()}
})

stats["this_month"] = await self.file_stats.count_documents({
"user_id": user_id,
"date": {"$gte": start_of_month.isoformat()}
})

return stats
except Exception as e:
logger.error(f"Error getting file stats for {user_id}: {e}")
return stats

async def add_points(self, user_id: int, points: int, source: str = "system", 
description: str = None) -> bool:
"""Add points to user's balance with transaction tracking."""
try:
await self.users.update_one(
{"_id": user_id},
{
"$inc": {
"points.balance": points,
"points.total_earned": points
},
"$set": {"points.last_earned": datetime.datetime.now()}
}
)

await self.transactions.insert_one({
"user_id": user_id,
"type": "credit",
"amount": points,
"source": source,
"description": description or f"Added {points} points",
"timestamp": datetime.datetime.now(),
"balance_after": (await self.get_points(user_id)) + points
})

return True
except Exception as e:
logger.error(f"Error adding points to {user_id}: {e}")
return False

async def deduct_points(self, user_id: int, points: int, reason: str = "system") -> bool:
"""Deduct points from user's balance with validation."""
try:
current_points = await self.get_points(user_id)
if current_points < points:
return False

await self.users.update_one(
{"_id": user_id},
{
"$inc": {
"points.balance": -points,
"points.total_spent": points
}
}
)

await self.transactions.insert_one({
"user_id": user_id,
"type": "debit",
"amount": points,
"source": reason,
"description": f"Deducted {points} points",
"timestamp": datetime.datetime.now(),
"balance_after": current_points - points
})

return True
except Exception as e:
logger.error(f"Error deducting points from {user_id}: {e}")
return False

async def get_points(self, user_id: int) -> int:
"""Get user's current points balance."""
try:
user = await self.users.find_one({"_id": user_id})
return user["points"]["balance"] if user else 0
except Exception as e:
logger.error(f"Error getting points for {user_id}: {e}")
return 0

async def get_points_history(self, user_id: int, limit: int = 10) -> List[Dict]:
"""Get user's points transaction history."""
try:
cursor = self.transactions.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
return await cursor.to_list(length=limit)
except Exception as e:
logger.error(f"Error getting points history for {user_id}: {e}")
return []

async def activate_premium(self, user_id: int, plan: str, duration_days: int, 
payment_method: str = "manual") -> bool:
"""Activate premium subscription for a user."""
try:
now = datetime.datetime.now()
until = now + datetime.timedelta(days=duration_days)

await self.users.update_one(
{"_id": user_id},
{"$set": {
"premium.is_premium": True,
"premium.since": now.isoformat(),
"premium.until": until.isoformat(),
"premium.plan": plan,
"premium.payment_method": payment_method
}}
)
return True
except Exception as e:
logger.error(f"Error activating premium for {user_id}: {e}")
return False

async def check_premium_status(self, user_id: int) -> Dict:
"""Check user's premium status with auto-expiration."""
try:
user = await self.users.find_one({"_id": user_id})
if not user:
return {"is_premium": False, "reason": "User not found"}

if user["premium"]["is_premium"]:
if user["premium"]["until"] and \
datetime.datetime.fromisoformat(user["premium"]["until"]) < datetime.datetime.now():
await self.deactivate_premium(user_id)
return {"is_premium": False, "reason": "Subscription expired"}
return {"is_premium": True, "until": user["premium"]["until"], "plan": user["premium"]["plan"]}
return {"is_premium": False, "reason": "No active subscription"}
except Exception as e:
logger.error(f"Error checking premium status for {user_id}: {e}")
return {"is_premium": False, "reason": "Error checking status"}

async def deactivate_premium(self, user_id: int) -> bool:
"""Deactivate premium subscription for a user."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {
"premium.is_premium": False,
"premium.until": None,
"premium.plan": None
}}
)
return True
except Exception as e:
logger.error(f"Error deactivating premium for {user_id}: {e}")
return False

async def create_points_link(self, admin_id: int, points: int, 
max_claims: int = 1, 
expires_in_hours: int = 24,
note: str = None) -> Tuple[Optional[str], Optional[str]]:
"""Create a shareable points link with expiration and claim limits."""
try:
code = secrets.token_urlsafe(12)
expires_at = datetime.datetime.now() + datetime.timedelta(hours=expires_in_hours)

link_data = {
"code": code,
"points": points,
"max_claims": max_claims,
"claims_remaining": max_claims,
"created_by": admin_id,
"created_at": datetime.datetime.now(),
"expires_at": expires_at.isoformat(),
"is_active": True,
"note": note,
"claimed_by": []
}

await self.point_links.insert_one(link_data)

base_url = "https://t.me/Forwardmsgremoverbot?start=points_"  # Change to your bot's URL
full_url = f"{base_url}{code}"

return code, full_url
except Exception as e:
logger.error(f"Error creating points link: {e}")
return None, None

async def claim_points_link(self, user_id: int, code: str) -> Dict:
"""Claim points from a shareable link."""
try:
link = await self.point_links.find_one({
"code": code,
"is_active": True,
"expires_at": {"$gt": datetime.datetime.now()}
})

if not link:
return {"success": False, "reason": "Invalid or expired link"}

if user_id in link["claimed_by"]:
return {"success": False, "reason": "Already claimed"}

if link["claims_remaining"] <= 0:
return {"success": False, "reason": "No claims remaining"}

await self.add_points(
user_id,
link["points"],
source="point_link",
description=f"Claimed from link {code}"
)

await self.point_links.update_one(
{"code": code},
{
"$inc": {"claims_remaining": -1},
"$push": {"claimed_by": user_id}
}
)

await self.transactions.insert_one({
"user_id": user_id,
"type": "point_link_claim",
"amount": link["points"],
"timestamp": datetime.datetime.now(),
"details": {
"link_code": code,
"created_by": link["created_by"],
"remaining_claims": link["claims_remaining"] - 1
}
})

return {
"success": True,
"points": link["points"],
"remaining_claims": link["claims_remaining"] - 1
}
except Exception as e:
logger.error(f"Error claiming points link {code} by {user_id}: {e}")
return {"success": False, "reason": "Internal error"}

async def set_expend_points(self, user_id: int, points: int, code: str = None) -> Dict:
"""
       Track points expenditure and create claimable reward
       
       Args:
           user_id: User ID creating the reward link
           points: Points amount to reward
           code: Unique code for claiming (auto-generated if None)
       
       Returns:
           Dict: {
               'success': bool,
               'code': str (if successful),
               'error': str (if failed)
           }
       """
try:
# Validate user exists
if not await self.is_user_exist(user_id):
return {'success': False, 'error': 'User does not exist'}

# Generate code if not provided
if not code:
code = secrets.token_urlsafe(8)

# Record the expenditure
result = await self.transactions.insert_one({
"user_id": user_id,
"type": "points_expenditure",
"amount": points,
"code": code,
"status": "pending",
"created_at": datetime.datetime.now(),
"claimed_by": [],
"expires_at": datetime.datetime.now() + datetime.timedelta(hours=24)
})

if not result.inserted_id:
return {'success': False, 'error': 'Failed to record transaction'}

return {'success': True, 'code': code}

except Exception as e:
logger.error(f"Error setting expend points: {e}")
return {'success': False, 'error': str(e)}

async def claim_expend_points(self, claimer_id: int, code: str) -> Dict:
"""
       Claim points from an expenditure record
       
       Args:
           claimer_id: User ID claiming the points
           code: Unique claim code
       
       Returns:
           Dict: {
               'success': bool,
               'points': int (if successful),
               'error': str (if failed)
           }
       """
try:
# Find the expenditure record
record = await self.transactions.find_one({
"code": code,
"status": "pending",
"expires_at": {"$gt": datetime.datetime.now()}
})

if not record:
return {'success': False, 'error': 'Invalid or expired code'}

# Check if already claimed by this user
if claimer_id in record.get('claimed_by', []):
return {'success': False, 'error': 'Already claimed'}

# Add points to claimer
await self.add_points(
claimer_id,
record['amount'],
source="ad_reward",
description=f"Claimed from code {code}"
)

# Add bonus to creator
creator_bonus = record['amount'] // 2
if creator_bonus > 0:
await self.add_points(
record['user_id'],
creator_bonus,
source="referral_ad",
description=f"Bonus for ad claim by {claimer_id}"
)

# Update the record
await self.transactions.update_one(
{"_id": record['_id']},
{
"$push": {"claimed_by": claimer_id},
"$set": {"status": "claimed"}
}
)

return {'success': True, 'points': record['amount']}

except Exception as e:
logger.error(f"Error claiming expend points: {e}")
return {'success': False, 'error': str(e)}
async def create_ad_campaign(self, user_id: int, name: str, points: int, max_views: int):
"""Create a new ad campaign for a user"""
campaign_id = str(uuid.uuid4())
code = str(uuid.uuid4())[:8]

campaign = {
"_id": campaign_id,
"owner_id": user_id,
"name": name,
"points_per_view": points,
"max_views": max_views,
"views": 0,
"created_at": datetime.now(),
"expires_at": datetime.now() + timedelta(days=7),
"code": code,
"active": True
}

# Deduct points from user
await self.users.update_one(
{"_id": user_id},
{"$inc": {
"points.balance": -points * max_views,
"points.total_spent": points * max_views,
"campaigns.created": 1
}}
)

# Store campaign
await self.campaigns.insert_one(campaign)
return code

async def process_ad_view(self, code: str, viewer_id: int):
"""Process when a user views an ad"""
async with await self._client.start_session() as session:
async with session.start_transaction():
# Get campaign
campaign = await self.campaigns.find_one(
{"code": code, "active": True},
session=session
)

if not campaign or campaign['views'] >= campaign['max_views']:
await session.abort_transaction()
return False

# Calculate points with premium multiplier
user = await self.users.find_one(
{"_id": viewer_id},
{"premium.ad_multiplier": 1},
session=session
)
multiplier = user.get('premium', {}).get('ad_multiplier', 1.0)
points = int(campaign['points_per_view'] * multiplier)

# Update user stats
await self.users.update_one(
{"_id": viewer_id},
{"$inc": {
"points.balance": points,
"points.total_earned": points,
"points.sources.ads": points,
"activity.ad_views": 1,
"activity.ad_earnings": points
}},
session=session
)

# Update campaign
await self.campaigns.update_one(
{"_id": campaign['_id']},
{"$inc": {"views": 1}},
session=session
)

# Record transaction
await self.transactions.insert_one({
"user_id": viewer_id,
"type": "ad_view",
"amount": points,
"campaign_id": campaign['_id'],
"timestamp": datetime.now()
}, session=session)

return points
async def get_campaign_by_code(self, code: str, session=None) -> Optional[Dict]:
"""Get campaign details by redemption code"""
return await self.campaigns.find_one(
{"codes.code": code},
{
"_id": 1,
"name": 1,
"reward": 1,
"owner_id": 1,
"expires_at": 1,
"codes.$": 1,
"remaining_budget": 1
},
session=session
)

async def mark_campaign_used(self, campaign_id: str, user_id: int, session=None):
"""Mark a campaign code as used"""
await self.campaigns.update_one(
{"_id": campaign_id, "codes.code": code},
{
"$set": {"codes.$.used": True, "codes.$.used_by": user_id, "codes.$.used_at": datetime.now()},
"$inc": {"remaining_budget": -reward}
},
session=session
)
async def update_leaderboards(self):
"""Update all leaderboard periods (daily/weekly/monthly/alltime)"""
try:
# Update daily leaderboard
await self._update_leaderboard_period("daily")

# Update weekly leaderboard (only on Sundays)
if datetime.datetime.now().weekday() == 6:  # Sunday
await self._update_leaderboard_period("weekly")

# Update monthly leaderboard (on 1st of month)
if datetime.datetime.now().day == 1:
await self._update_leaderboard_period("monthly")

# Always update all-time leaderboard
await self._update_leaderboard_period("alltime")

logger.info("Leaderboards updated successfully")
return True
except Exception as e:
logger.error(f"Failed to update leaderboards: {e}")
return False

async def _update_leaderboard_period(self, period: str):
"""Update a specific leaderboard period"""
try:
leaders = await self._get_leaderboard_data(period)
await self.leaderboards.update_one(
{"period": period},
{"$set": {"data": leaders, "updated_at": datetime.datetime.now()}},
upsert=True
)
except Exception as e:
logger.error(f"Error updating {period} leaderboard: {e}")

async def _get_leaderboard_data(self, period: str) -> List[Dict]:
"""Get leaderboard data for a specific period"""
try:
if period == "alltime":
pipeline = [
{"$sort": {"points.balance": -1}},
{"$limit": 100},
{"$project": {
"_id": 1,
"username": 1,
"points": "$points.balance",
"is_premium": "$premium.is_premium"
}}
]
else:
days = 1 if period == "daily" else 7 if period == "weekly" else 30
start_date = datetime.datetime.now() - datetime.timedelta(days=days)

pipeline = [
{"$match": {"activity.last_active": {"$gte": start_date}}},
{"$sort": {"points.balance": -1}},
{"$limit": 100},
{"$project": {
"_id": 1,
"username": 1,
"points": "$points.balance",
"is_premium": "$premium.is_premium"
}}
]

return await self.users.aggregate(pipeline).to_list(length=100)
except Exception as e:
logger.error(f"Error getting {period} leaderboard data: {e}")
return []


async def get_leaderboard(self, period: str = "weekly", lb_type: str = "points", limit: int = 10) -> List[Dict]:
"""Get leaderboard data with proper aggregation"""
try:
# Determine date range
now = datetime.datetime.utcnow()
date_filter = {}

if period == "daily":
start_date = now - datetime.timedelta(days=1)
date_filter = {"timestamp": {"$gte": start_date}}
elif period == "weekly":
start_date = now - datetime.timedelta(weeks=1)
date_filter = {"timestamp": {"$gte": start_date}}
elif period == "monthly":
start_date = now - datetime.timedelta(days=30)
date_filter = {"timestamp": {"$gte": start_date}}

pipeline = []

if lb_type == "points":
# Points leaderboard - sum of all points transactions
pipeline = [
{"$match": {"type": "credit", **date_filter}},
{"$group": {
"_id": "$user_id",
"total_points": {"$sum": "$amount"}
}},
{"$sort": {"total_points": -1}},
{"$limit": limit},
{"$lookup": {
"from": "users",
"localField": "_id",
"foreignField": "_id",
"as": "user"
}},
{"$unwind": "$user"},
{"$project": {
"_id": 1,
"username": "$user.username",
"value": "$total_points",
"is_premium": "$user.premium.is_premium"
}}
]

elif lb_type == "renames":
# Renames leaderboard - count of file rename operations
pipeline = [
{"$match": date_filter},
{"$group": {
"_id": "$user_id",
"total_renames": {"$sum": 1}
}},
{"$sort": {"total_renames": -1}},
{"$limit": limit},
{"$lookup": {
"from": "users",
"localField": "_id",
"foreignField": "_id",
"as": "user"
}},
{"$unwind": "$user"},
{"$project": {
"_id": 1,
"username": "$user.username",
"value": "$total_renames",
"is_premium": "$user.premium.is_premium"
}}
]

elif lb_type == "referrals":
# Referrals leaderboard - count of referrals
pipeline = [
{"$match": {"referral.referred_count": {"$gt": 0}}},
{"$project": {
"_id": 1,
"username": 1,
"value": "$referral.referred_count",
"is_premium": "$premium.is_premium"
}},
{"$sort": {"value": -1}},
{"$limit": limit}
]

if not pipeline:
return []

collection = self.transactions if lb_type == "points" else self.file_stats if lb_type == "renames" else self.users
results = await collection.aggregate(pipeline).to_list(length=limit)

# Add ranking
for i, user in enumerate(results, 1):
user["rank"] = i
if not user.get("username"):
user["username"] = f"User {user['_id']}"

return results

except Exception as e:
logger.error(f"Error getting {period} {lb_type} leaderboard: {e}")
return []

async def update_leaderboard_cache(self):
"""Update all cached leaderboard data"""
try:
periods = ["daily", "weekly", "monthly", "alltime"]
types = ["points", "renames", "referrals"]

for period in periods:
for lb_type in types:
data = await self.get_leaderboard(period, lb_type, limit=100)
await self.leaderboards.update_one(
{"period": period, "type": lb_type},
{"$set": {"data": data, "updated_at": datetime.datetime.utcnow()}},
upsert=True
)

logger.info("Successfully updated all leaderboard caches")
return True
except Exception as e:
logger.error(f"Error updating leaderboard caches: {e}")
return False

async def get_cached_leaderboard(self, period: str, lb_type: str) -> List[Dict]:
"""Get cached leaderboard data if recent, otherwise generate fresh"""
try:
# Check if cache exists and is recent (within 1 hour)
cache = await self.leaderboards.find_one(
{"period": period, "type": lb_type}
)

if cache and (datetime.datetime.utcnow() - cache["updated_at"]).total_seconds() < 3600:
return cache["data"]

# If cache is stale or missing, generate fresh data
fresh_data = await self.get_leaderboard(period, lb_type)
await self.leaderboards.update_one(
{"period": period, "type": lb_type},
{"$set": {"data": fresh_data, "updated_at": datetime.datetime.utcnow()}},
upsert=True
)
return fresh_data

except Exception as e:
logger.error(f"Error getting cached leaderboard: {e}")
return await self.get_leaderboard(period, lb_type)

async def set_leaderboard_period(self, user_id: int, period: str) -> bool:
"""Set user's preferred leaderboard period"""
valid_periods = ["daily", "weekly", "monthly", "alltime"]
if period not in valid_periods:
logger.warning(f"Invalid period requested: {period}")
return False

try:
result = await self.users.update_one(
{"_id": user_id},
{"$set": {"settings.leaderboard_period": period}},
upsert=True
)
return result.acknowledged
except Exception as e:
logger.error(f"Error setting leaderboard period: {e}")
return False

async def get_leaderboard_period(self, user_id: int) -> str:
"""Get user's preferred leaderboard period"""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("settings", {}).get("leaderboard_period", "weekly")
except Exception as e:
logger.error(f"Error getting leaderboard period: {e}")
return "weekly"

async def set_leaderboard_type(self, user_id: int, lb_type: str) -> bool:
"""Set user's preferred leaderboard type"""
valid_types = ["points", "renames", "referrals"]
if lb_type not in valid_types:
logger.warning(f"Invalid leaderboard type: {lb_type}")
return False

try:
result = await self.users.update_one(
{"_id": user_id},
{"$set": {"settings.leaderboard_type": lb_type}},
upsert=True
)
return result.acknowledged
except Exception as e:
logger.error(f"Error setting leaderboard type: {e}")
return False

async def get_leaderboard_type(self, user_id: int) -> str:
"""Get user's preferred leaderboard type"""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("settings", {}).get("leaderboard_type", "points")
except Exception as e:
logger.error(f"Error getting leaderboard type: {e}")
return "points"

async def get_points_links_stats(self, admin_id: int = None) -> Dict:
"""Get statistics about points links."""
try:
match = {"is_active": True} if not admin_id else {"created_by": admin_id}

stats = await self.point_links.aggregate([
{"$match": match},
{"$group": {
"_id": None,
"total_links": {"$sum": 1},
"active_links": {
"$sum": {
"$cond": [
{"$and": [
{"$gt": ["$expires_at", datetime.datetime.now()]},
{"$gt": ["$claims_remaining", 0]}
]},
1, 0
]
}
},
"total_points": {"$sum": {"$multiply": ["$points", "$max_claims"]}},
"claimed_points": {"$sum": {"$multiply": ["$points", {"$subtract": ["$max_claims", "$claims_remaining"]}]}}
}}
]).to_list(length=1)

return stats[0] if stats else {
"total_links": 0,
"active_links": 0,
"total_points": 0,
"claimed_points": 0
}
except Exception as e:
logger.error(f"Error getting points links stats: {e}")
return {
"total_links": 0,
"active_links": 0,
"total_points": 0,
"claimed_points": 0
}

async def generate_points_report(self, days: int = 7) -> Dict:
"""Generate a points activity report for admins."""
try:
end_date = datetime.datetime.now()
start_date = end_date - datetime.timedelta(days=days)

report = await self.transactions.aggregate([
{
"$match": {
"type": "credit",
"timestamp": {
"$gte": start_date,
"$lte": end_date
}
}
},
{
"$group": {
"_id": "$source",
"total_points": {"$sum": "$amount"},
"count": {"$sum": 1}
}
}
]).to_list(length=None)

top_earners = await self.transactions.aggregate([
{
"$match": {
"type": "credit",
"timestamp": {
"$gte": start_date,
"$lte": end_date
}
}
},
{
"$group": {
"_id": "$user_id",
"total_points": {"$sum": "$amount"}
}
},
{"$sort": {"total_points": -1}},
{"$limit": 10},
{"$lookup": {
"from": "users",
"localField": "_id",
"foreignField": "_id",
"as": "user"
}},
{"$unwind": "$user"},
{"$project": {
"user_id": "$_id",
"username": "$user.username",
"points": "$total_points"
}}
]).to_list(length=10)

return {
"period": {
"start": start_date.isoformat(),
"end": end_date.isoformat()
},
"total_points_distributed": sum(d["total_points"] for d in report),
"distribution": report,
"top_earners": top_earners
}
except Exception as e:
logger.error(f"Error generating points report: {e}")
return {
"period": {
"start": (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat(),
"end": datetime.datetime.now().isoformat()
},
"total_points_distributed": 0,
"distribution": [],
"top_earners": []
}

async def get_all_banned_users(self) -> List[Dict]:
"""Get all banned users."""
try:
cursor = self.users.find({"ban_status.is_banned": True})
return await cursor.to_list(length=None)
except Exception as e:
logger.error(f"Error getting banned users: {e}")
return []

async def get_sequential_mode(self, user_id: int) -> bool:
"""Get user's sequential mode setting."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("settings", {}).get("sequential_mode", False) if user else False
except Exception as e:
logger.error(f"Error getting sequential mode for {user_id}: {e}")
return False

async def toggle_sequential_mode(self, user_id: int) -> bool:
"""Toggle user's sequential mode setting."""
try:
current = await self.get_sequential_mode(user_id)
await self.users.update_one(
{"_id": user_id},
{"$set": {"settings.sequential_mode": not current}}
)
return not current
except Exception as e:
logger.error(f"Error toggling sequential mode for {user_id}: {e}")
return False

async def get_user_channel(self, user_id: int) -> Optional[str]:
"""Get user's dump channel ID."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("settings", {}).get("user_channel") if user else None
except Exception as e:
logger.error(f"Error getting user channel for {user_id}: {e}")
return None

async def set_user_channel(self, user_id: int, channel_id: str) -> bool:
"""Set user's dump channel ID."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"settings.user_channel": channel_id}}
)
return True
except Exception as e:
logger.error(f"Error setting user channel for {user_id}: {e}")
return False

async def ban_user(self, user_id: int, duration_days: int, reason: str) -> bool:
"""Ban a user from using the bot."""
try:
banned_on = datetime.datetime.now(pytz.timezone("Africa/Lubumbashi")).isoformat()
await self.users.update_one(
{"_id": user_id},
{"$set": {
"ban_status.is_banned": True,
"ban_status.ban_duration": duration_days,
"ban_status.banned_on": banned_on,
"ban_status.ban_reason": reason
}}
)
return True
except Exception as e:
logger.error(f"Error banning user {user_id}: {e}")
return False

async def remove_ban(self, user_id: int) -> bool:
"""Remove ban from a user."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {
"ban_status.is_banned": False,
"ban_status.ban_duration": 0,
"ban_status.unbanned_by": "admin",
"ban_status.unban_reason": "Manual unban"
}}
)
return True
except Exception as e:
logger.error(f"Error unbanning user {user_id}: {e}")
return False

async def set_referrer(self, user_id: int, referrer_id: int) -> bool:
"""Set referrer for a user."""
try:
await self.users.update_one(
{"_id": user_id},
{"$set": {"referral.referrer_id": referrer_id}}
)

# Update referrer's stats
await self.users.update_one(
{"_id": referrer_id},
{
"$inc": {"referral.referred_count": 1},
"$push": {"referral.referred_users": user_id}
}
)
return True
except Exception as e:
logger.error(f"Error setting referrer for {user_id}: {e}")
return False

async def is_refferer(self, user_id: int) -> Optional[int]:
"""Check if user is a referrer and return their referrer ID."""
try:
user = await self.users.find_one({"_id": user_id})
return user.get("referral", {}).get("referrer_id") if user else None
except Exception as e:
logger.error(f"Error getting referrer for user {user_id}: {e}")
return None

async def total_renamed_files(self) -> int:
"""Get total number of files renamed across all users."""
try:
result = await self.users.aggregate([
{"$group": {"_id": None, "total": {"$sum": "$activity.total_files_renamed"}}}
]).to_list(length=1)
return result[0]["total"] if result else 0
except Exception as e:
logger.error(f"Error counting total renamed files: {e}")
return 0

async def clear_all_user_channels(self) -> None:
"""Remove the 'user_channel' field from all user documents."""
if not self.users:
logger.error("❌ 'users' collection is not initialized.")
return

try:
result = await self.users.update_many(
{},  # Match all documents
{"$unset": {"settings.user_channel": ""}}  # Use $unset to remove the field
)
logger.info(f"✅ Removed 'user_channel' from {result.modified_count} users.")
except Exception as e:
logger.error(f"❌ Error while removing 'user_channel': {e}")

async def total_points_distributed(self) -> int:
"""Get total points distributed across all users."""
try:
result = await self.users.aggregate([
{"$group": {"_id": None, "total": {"$sum": "$points.total_earned"}}}
]).to_list(length=1)
return result[0]["total"] if result else 0
except Exception as e:
logger.error(f"Error counting total points distributed: {e}")
return 0

async def get_config(self, key: str, default=None):
"""Get configuration value with default fallback."""
try:
config = await self.config.find_one({"key": key})
return config["value"] if config else default
except Exception as e:
logger.error(f"Error getting config {key}: {e}")
return default

# Initialize database instance with retry logic
hyoshcoder = Database(Config.DATA_URI, Config.DATA_NAME)

async def initialize_database():
"""Initialize database connection with retry logic."""
max_retries = 3
retry_delay = 2  # seconds

for attempt in range(max_retries):
try:
await hyoshcoder.connect()
# Initialize leaderboard cache on startup
await hyoshcoder.update_leaderboard_cache()
return hyoshcoder
except Exception as e:
if attempt == max_retries - 1:
logger.error(f"❌ Failed to initialize database after {max_retries} attempts: {e}")
raise
logger.warning(f"⚠️ Database connection failed (attempt {attempt + 1}), retrying in {retry_delay}s...")
await asyncio.sleep(retry_delay)
retry_delay *= 2  # Exponential backoff
