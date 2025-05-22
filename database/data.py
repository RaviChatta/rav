import motor.motor_asyncio
import datetime
import pytz
import secrets
import logging
from config import settings
from typing import Optional, Dict, List, Union, Tuple
from bson.objectid import ObjectId
from urllib.parse import urlencode
from pyrogram.errors import ChatWriteForbidden

logger = logging.getLogger(__name__)
Config = settings

class Database:
    def __init__(self, uri: str, database_name: str):
        """Initialize database connection."""
        self._uri = uri
        self._database_name = database_name
        self._client = None
        self.db = None
        self.users = None
        self.premium_codes = None
        self.transactions = None
        self.rewards = None
        self.point_links = None
        self.leaderboards = None
        self.file_stats = None

    async def connect(self, max_retries: int = 3, retry_delay: int = 5):
        """Establish database connection with retry logic."""
        for attempt in range(max_retries):
            try:
                self._client = motor.motor_asyncio.AsyncIOMotorClient(
                    self._uri,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=30000,
                    socketTimeoutMS=30000,
                    maxPoolSize=100,
                    minPoolSize=10
                )
                await self._client.admin.command('ping')
                
                self.db = self._client[self._database_name]
                self.users = self.db.users
                self.premium_codes = self.db.premium_codes
                self.transactions = self.db.transactions
                self.rewards = self.db.rewards
                self.point_links = self.db.point_links
                self.leaderboards = self.db.leaderboards
                self.file_stats = self.db.file_stats
                
                await self._create_indexes()
                logger.info("✅ Database connection established")
                return True
                
            except Exception as e:
                logger.error(f"⚠️ Database connection failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(retry_delay * (attempt + 1))
        return False

    async def _create_indexes(self):
        """Create necessary indexes for performance optimization."""
        indexes = [
            ("users", "referrer_id", False),
            ("users", "ban_status.is_banned", False),
            ("point_links", "code", True),
            ("point_links", "expires_at", False),
            ("transactions", "user_id", False),
            ("transactions", "timestamp", False),
            ("leaderboards", "period", False),
            ("leaderboards", "type", False),
            ("leaderboards", "start_date", False),
            ("leaderboards", "end_date", False),
            ("file_stats", "user_id", False),
            ("file_stats", "date", False)
        ]
        
        for collection, field, unique in indexes:
            try:
                await self.db[collection].create_index(field, unique=unique)
                logger.debug(f"Created index on {collection}.{field} (unique={unique})")
            except Exception as e:
                logger.error(f"Failed to create index on {collection}.{field}: {e}")

    # ====================== USER MANAGEMENT ======================
    def new_user(self, id: int) -> Dict:
        """Create a new user document with default values."""
        return {
            "_id": int(id),
            "join_date": datetime.datetime.now(pytz.timezone("Africa/Lubumbashi")).isoformat(),
            "file_id": None,
            "caption": None,
            "metadata": True,
            "metadata_code": "Telegram : @REQUETE_ANIME_30sbot",
            "format_template": None,
            "ban_status": {
                "is_banned": False,
                "ban_duration": 0,
                "banned_on": None,
                "ban_reason": '',
                "unbanned_by": None,
                "unban_reason": None
            },
            "points": {
                "balance": 70,
                "total_earned": 70,
                "total_spent": 0,
                "last_earned": datetime.datetime.now().isoformat()
            },
            "premium": {
                "is_premium": False,
                "since": None,
                "until": None,
                "plan": None,
                "payment_method": None
            },
            "referral": {
                "referrer_id": None,
                "referred_count": 0,
                "referral_earnings": 0,
                "referred_users": []
            },
            "settings": {
                "sequential_mode": False,
                "user_channel": None,
                "src_info": "file_name",
                "language": "en",
                "notifications": True
            },
            "activity": {
                "last_active": datetime.datetime.now().isoformat(),
                "total_files_renamed": 0,
                "daily_usage": 0,
                "last_usage_date": None
            },
            "security": {
                "two_factor": False,
                "last_login": None,
                "login_history": []
            }
        }

    async def add_user(self, user_id: int, referrer_id: int = None) -> bool:
        """Add a new user with comprehensive initialization."""
        try:
            if await self.is_user_exist(user_id):
                return False
                
            user_data = self.new_user(user_id)
            if referrer_id:
                user_data["referral"]["referrer_id"] = referrer_id
                
            await self.users.insert_one(user_data)
            logger.info(f"Added new user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding user {user_id}: {e}")
            return False

    async def is_user_exist(self, id: int) -> bool:
        """Check if user exists in database."""
        try:
            user = await self.users.find_one({"_id": int(id)})
            return bool(user)
        except Exception as e:
            logger.error(f"Error checking if user {id} exists: {e}")
            return False

    async def read_user(self, id: int) -> Optional[Dict]:
        """Get user document by ID."""
        try:
            return await self.users.find_one({"_id": int(id)})
        except Exception as e:
            logger.error(f"Error reading user {id}: {e}")
            return None

    async def update_user(self, user_id: int, update_data: Dict) -> bool:
        """Update user document."""
        try:
            result = await self.users.update_one(
                {"_id": user_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return False

    async def delete_user(self, user_id: int) -> bool:
        """Soft delete user data."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {
                    "deleted": True,
                    "deleted_at": datetime.datetime.now().isoformat()
                }}
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False

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

    async def get_all_users(self, filter: Dict = None):
        """Get all users with optional filter."""
        try:
            return self.users.find(filter or {})
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            raise

    # ====================== FILE MANAGEMENT ======================
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

    async def get_metadata(self, user_id: int) -> Dict:
        """Get user's metadata settings."""
        try:
            user = await self.users.find_one({"_id": user_id})
            if user:
                return {
                    "metadata": user.get("metadata", True),
                    "metadata_code": user.get("metadata_code", "")
                }
            return {"metadata": True, "metadata_code": ""}
        except Exception as e:
            logger.error(f"Error getting metadata for {user_id}: {e}")
            return {"metadata": True, "metadata_code": ""}

    async def get_sequential_mode(self, user_id: int) -> bool:
        """Get user's sequential mode setting."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("settings", {}).get("sequential_mode", False) if user else False
        except Exception as e:
            logger.error(f"Error getting sequential mode for {user_id}: {e}")
            return False

    async def set_format_template(self, user_id: int, template: str) -> bool:
        """Set user's auto-rename format template."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"format_template": template}}
            )
            return True
        except Exception as e:
            logger.error(f"Error setting format template for {user_id}: {e}")
            return False

    async def get_format_template(self, user_id: int) -> Optional[str]:
        """Get user's auto-rename format template."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("format_template") if user else None
        except Exception as e:
            logger.error(f"Error getting format template for {user_id}: {e}")
            return None

    # ====================== FILE STATISTICS ======================
    async def track_file_rename(self, user_id: int, original_name: str, new_name: str) -> bool:
        """Track a file rename operation."""
        try:
            # Update user's total count
            await self.users.update_one(
                {"_id": user_id},
                {"$inc": {"activity.total_files_renamed": 1}}
            )
            
            # Record detailed stats
            await self.file_stats.insert_one({
                "user_id": user_id,
                "original_name": original_name,
                "new_name": new_name,
                "timestamp": datetime.datetime.now().isoformat(),
                "date": datetime.datetime.now().date().isoformat()
            })
            return True
        except Exception as e:
            logger.error(f"Error tracking file rename for {user_id}: {e}")
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
            
        except Exception as e:
            logger.error(f"Error getting file stats for {user_id}: {e}")
            
        return stats

    # ====================== POINTS SYSTEM ======================
    async def add_points(self, user_id: int, points: int, source: str = "system", description: str = None) -> bool:
        """Add points to user's balance."""
        try:
            # Update user's points
            await self.users.update_one(
                {"_id": user_id},
                {
                    "$inc": {
                        "points.balance": points,
                        "points.total_earned": points
                    },
                    "$set": {"points.last_earned": datetime.datetime.now().isoformat()}
                }
            )
            
            # Record transaction
            await self.transactions.insert_one({
                "user_id": user_id,
                "type": "credit",
                "amount": points,
                "source": source,
                "description": description or f"Added {points} points",
                "timestamp": datetime.datetime.now().isoformat(),
                "balance_after": (await self.get_points(user_id)) + points
            })
            return True
        except Exception as e:
            logger.error(f"Error adding points to {user_id}: {e}")
            return False

    async def deduct_points(self, user_id: int, points: int, reason: str = "system") -> bool:
        """Deduct points from user's balance."""
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
                "timestamp": datetime.datetime.now().isoformat(),
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

    # ====================== PREMIUM FEATURES ======================
    async def activate_premium(self, user_id: int, plan: str, duration_days: int, payment_method: str = "manual") -> bool:
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

    async def deactivate_premium(self, user_id: int) -> bool:
        """Deactivate premium subscription for a user."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {
                    "premium.is_premium": False,
                    "premium.until": None
                }}
            )
            return True
        except Exception as e:
            logger.error(f"Error deactivating premium for {user_id}: {e}")
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
                return {
                    "is_premium": True,
                    "until": user["premium"]["until"],
                    "plan": user["premium"]["plan"]
                }
            return {"is_premium": False, "reason": "No active subscription"}
        except Exception as e:
            logger.error(f"Error checking premium status for {user_id}: {e}")
            return {"is_premium": False, "reason": "Error checking status"}

    # ====================== LEADERBOARDS ======================
    async def update_leaderboards(self):
        """Update all leaderboards."""
        await self._update_daily_leaderboard()
        await self._update_weekly_leaderboard()
        await self._update_monthly_leaderboard()
        await self._update_alltime_leaderboard()

    async def get_leaderboard(self, period: str = "daily", lb_type: str = "points") -> List[Dict]:
        """Get leaderboard data."""
        try:
            if period not in ["daily", "weekly", "monthly", "alltime"]:
                period = "daily"
                
            leaderboard = await self.leaderboards.find_one(
                {"period": period},
                sort=[("updated_at", -1)]
            )
            
            if not leaderboard:
                return []
                
            return leaderboard["data"].get(lb_type, [])
        except Exception as e:
            logger.error(f"Error getting {period} leaderboard: {e}")
            return []

    async def _update_daily_leaderboard(self):
        """Update daily leaderboard."""
        today = datetime.datetime.now().date()
        
        # Points leaders
        points_leaders = await self.users.aggregate([
            {"$match": {"ban_status.is_banned": False}},
            {"$sort": {"points.balance": -1}},
            {"$limit": 100},
            {"$project": {
                "_id": 1,
                "username": 1,
                "value": "$points.balance",
                "is_premium": "$premium.is_premium"
            }}
        ]).to_list(length=100)
        
        # File rename leaders (today)
        rename_leaders = await self.file_stats.aggregate([
            {"$match": {"date": today.isoformat()}},
            {"$group": {
                "_id": "$user_id",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 100},
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
                "value": "$count",
                "is_premium": "$user.premium.is_premium"
            }}
        ]).to_list(length=100)
        
        await self._save_leaderboard("daily", {
            "points": points_leaders,
            "renames": rename_leaders
        })

    async def _save_leaderboard(self, period: str, data: Dict):
        """Save leaderboard data to database."""
        try:
            await self.leaderboards.update_one(
                {"period": period},
                {
                    "$set": {
                        "data": data,
                        "updated_at": datetime.datetime.now().isoformat()
                    }
                },
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error saving {period} leaderboard: {e}")

# Initialize database instance
hyoshcoder = Database(Config.DATA_URI, Config.DATA_NAME)

async def initialize_database():
    """Initialize database connection"""
    try:
        await hyoshcoder.connect()
        logger.info("✅ Database initialized successfully")
        return hyoshcoder
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise
