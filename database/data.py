import motor.motor_asyncio
import datetime
import pytz
import secrets
from config import settings
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any
from bson.objectid import ObjectId
from urllib.parse import urlencode
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
        self.db = None
        self.users = None  # Initialize all collections here
        self.premium_codes = None
        self.transactions = None
        self._is_connected = False
        self._initialize_collections()
        
    def _initialize_collections(self):
        """Initialize all collection references."""
        self.users = None
        self.premium_codes = None
        self.transactions = None
        self.rewards = None
        self.point_links = None
        self.leaderboards = None
        self.file_stats = None
        self.config = None

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
            logging.info("✅ Successfully connected to MongoDB")
            
            # Initialize database and collections
            self.db = self._client[self._database_name]
            self._initialize_collections()
            self.users = self.db.users
            self.premium_codes = self.db.premium_codes
            self.transactions = self.db.transactions
            self.rewards = self.db.rewards
            self.users = self.db.users
            self.premium_codes = self.db.premium_codes
            self.transactions = self.db.transactions
            self.point_links = self.db.point_links
            self.leaderboards = self.db.leaderboards
            self.file_stats = self.db.file_stats
            self.config = self.db.config
            self._is_connected = True

            
            # Create indexes
            await self._create_indexes()
            
            return True
            
        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            logging.error(f"❌ Failed to connect to MongoDB: {e}")
            raise ConnectionError(f"Database connection failed: {e}") from e
        except PyMongoError as e:
            logging.error(f"❌ MongoDB error: {e}")
            raise
        except Exception as e:
            logging.error(f"❌ Unexpected error connecting to MongoDB: {e}")
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
        """Create necessary indexes with enhanced error handling."""
        indexes = [
            ("users", [("referrer_id", False)]),
            ("users", [("ban_status.is_banned", False)]),
            ("point_links", [("code", True), ("expires_at", False)]),
            ("transactions", [("user_id", False), ("timestamp", False)]),
            ("leaderboards", [("period", False), ("type", False), ("start_date", False), ("end_date", False)]),
            ("file_stats", [("user_id", False), ("date", False), ("timestamp", -1)]),
            ("config", [("key", True)])
        ]
        for collection, fields in indexes:
            try:
                for field, unique in fields:
                    await self.db[collection].create_index(field, unique=unique)
                logging.info(f"Created indexes for {collection}")
            except PyMongoError as e:
                logging.error(f"Failed to create indexes for {collection}: {e}")
                continue

    def new_user(self, id: int) -> Dict[str, Any]:
        """Create a new user document with comprehensive default values."""
        now = datetime.datetime.now(pytz.timezone("Africa/Lubumbashi"))
        return {
            "_id": int(id),
            "username": None,
            "join_date": now.isoformat(),
            "file_id": None,
            "caption": None,
            "metadata": True,
            "metadata_code": None,
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
                "last_earned": now.isoformat()
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
                "notifications": True,
                "leaderboard_period": "weekly",
                "leaderboard_type": "points"
            },
            "activity": {
                "last_active": now.isoformat(),
                "total_files_renamed": 0,
                "daily_usage": 0,
                "last_usage_date": None
            },
            "security": {
                "two_factor": False,
                "last_login": None,
                "login_history": []
            },
            "deleted": False,
            "deleted_at": None
        }

    async def add_user(self, id: int) -> bool:
        """Add a new user with comprehensive initialization."""
        try:
            if await self.is_user_exist(id):
                return False
                
            user_data = self.new_user(id)
            await self.users.insert_one(user_data)
            logging.info(f"Added new user: {id}")
            return True
        except PyMongoError as e:
            logging.error(f"Error adding user {id}: {e}")
            return False

    async def is_user_exist(self, id: int) -> bool:
        """Check if user exists in database."""
        try:
            user = await self.users.find_one({"_id": int(id)})
            return bool(user)
        except Exception as e:
            logging.error(f"Error checking if user {id} exists: {e}")
            return False

    async def get_user(self, id: int) -> Optional[Dict[str, Any]]:
        """Get user document by ID with proper error handling."""
        try:
            return await self.users.find_one({"_id": int(id)})
        except PyMongoError as e:
            logging.error(f"Error getting user {id}: {e}")
            return None

    async def update_user_activity(self, user_id: int) -> bool:
        """Update user's last active timestamp."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"activity.last_active": datetime.datetime.now().isoformat()}}
            )
            return True
        except PyMongoError as e:
            logging.error(f"Error updating activity for {user_id}: {e}")
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
            logging.error(f"Error getting users: {e}")
            raise

    async def close(self):
        """Close the database connection."""
        try:
            if self._client:
                self._client.close()
                logging.info("Database connection closed")
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")

    async def total_users_count(self) -> int:
        """Get total number of users."""
        try:
            return await self.users.count_documents({})
        except Exception as e:
            logging.error(f"Error counting users: {e}")
            return 0

    async def total_banned_users_count(self) -> int:
        """Get total number of banned users."""
        try:
            return await self.users.count_documents({"ban_status.is_banned": True})
        except Exception as e:
            logging.error(f"Error counting banned users: {e}")
            return 0

    async def total_premium_users_count(self) -> int:
        """Get total number of premium users."""
        try:
            return await self.users.count_documents({"premium.is_premium": True})
        except Exception as e:
            logging.error(f"Error counting premium users: {e}")
            return 0

    async def get_daily_active_users(self) -> int:
        """Get count of daily active users."""
        try:
            today = datetime.datetime.now().date()
            return await self.users.count_documents({
                "activity.last_active": {
                    "$gte": today.isoformat()
                }
            })
        except Exception as e:
            logging.error(f"Error counting daily active users: {e}")
            return 0

    async def read_user(self, id: int) -> Optional[Dict]:
        """Get user document by ID."""
        try:
            return await self.users.find_one({"_id": int(id)})
        except Exception as e:
            logging.error(f"Error reading user {id}: {e}")
            return None

    async def delete_user(self, user_id: int) -> bool:
        """Delete user data (soft delete)."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"deleted": True, "deleted_at": datetime.datetime.now().isoformat()}}
            )
            return True
        except Exception as e:
            logging.error(f"Error deleting user {user_id}: {e}")
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
            logging.error(f"Error setting thumbnail for {user_id}: {e}")
            return False

    async def get_thumbnail(self, user_id: int) -> Optional[str]:
        """Get user's thumbnail."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("file_id") if user else None
        except Exception as e:
            logging.error(f"Error getting thumbnail for {user_id}: {e}")
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
            logging.error(f"Error setting caption for {user_id}: {e}")
            return False

    async def get_caption(self, user_id: int) -> Optional[str]:
        """Get user's default caption."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("caption") if user else None
        except Exception as e:
            logging.error(f"Error getting caption for {user_id}: {e}")
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
            logging.error(f"Error setting metadata code for {user_id}: {e}")
            return False
    async def get_metadata_code(self, user_id: int) -> Optional[str]:
        try:
            if not await self.is_connected():
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
            logging.error(f"Error setting format template for user {user_id}: {e}")
            return False

    async def get_format_template(self, user_id: int) -> Optional[str]:
        """Get user's format template."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("format_template") if user else None
        except Exception as e:
            logging.error(f"Error getting format template for user {user_id}: {e}")
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
            logging.error(f"Error setting media preference for user {user_id}: {e}")
            return False

    async def get_media_preference(self, user_id: int) -> Optional[str]:
        """Get user's media preference."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("media_type") if user else None
        except Exception as e:
            logging.error(f"Error getting media preference for user {user_id}: {e}")
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
            logging.error(f"Error setting metadata for user {user_id}: {e}")
            return False

    async def get_metadata(self, user_id: int) -> bool:
        """Get user's metadata setting."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("metadata", True) if user else True
        except Exception as e:
            logging.error(f"Error getting metadata for user {user_id}: {e}")
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
            logging.error(f"Error setting src_info for {user_id}: {e}")
            return False

    async def toggle_src_info(self, user_id: int) -> bool:
        """Toggle source info preference for a user."""
        current_setting = await self.get_src_info(user_id)
        new_setting = "file_name" if current_setting == "metadata" else "metadata"
        await self.set_src_info(user_id, new_setting)
        return new_setting

    async def get_src_info(self, user_id: int) -> Optional[str]:
        """Get user's source info preference."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("settings", {}).get("src_info") if user else None
        except Exception as e:
            logging.error(f"Error getting src_info for {user_id}: {e}")
            return None

    async def track_file_rename(self, user_id: int, file_name: str, new_name: str) -> bool:
        """Track a file rename operation."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$inc": {"activity.total_files_renamed": 1}}
            )
            
            await self.file_stats.insert_one({
                "user_id": user_id,
                "original_name": file_name,
                "new_name": new_name,
                "timestamp": datetime.datetime.now().isoformat(),
                "date": datetime.datetime.now().date().isoformat()
            })
            
            return True
        except Exception as e:
            logging.error(f"Error tracking file rename for {user_id}: {e}")
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
            logging.error(f"Error getting file stats for {user_id}: {e}")
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
                    "$set": {"points.last_earned": datetime.datetime.now().isoformat()}
                }
            )
            
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
            logging.error(f"Error adding points to {user_id}: {e}")
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
                "timestamp": datetime.datetime.now().isoformat(),
                "balance_after": current_points - points
            })
            
            return True
        except Exception as e:
            logging.error(f"Error deducting points from {user_id}: {e}")
            return False

    async def get_points(self, user_id: int) -> int:
        """Get user's current points balance."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user["points"]["balance"] if user else 0
        except Exception as e:
            logging.error(f"Error getting points for {user_id}: {e}")
            return 0

    async def get_points_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's points transaction history."""
        try:
            cursor = self.transactions.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            logging.error(f"Error getting points history for {user_id}: {e}")
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
            logging.error(f"Error activating premium for {user_id}: {e}")
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
            logging.error(f"Error checking premium status for {user_id}: {e}")
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
            logging.error(f"Error deactivating premium for {user_id}: {e}")
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
                "created_at": datetime.datetime.now().isoformat(),
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
            logging.error(f"Error creating points link: {e}")
            return None, None

    async def claim_points_link(self, user_id: int, code: str) -> Dict:
        """Claim points from a shareable link."""
        try:
            link = await self.point_links.find_one({
                "code": code,
                "is_active": True,
                "expires_at": {"$gt": datetime.datetime.now().isoformat()}
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
                "timestamp": datetime.datetime.now().isoformat(),
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
            logging.error(f"Error claiming points link {code} by {user_id}: {e}")
            return {"success": False, "reason": "Internal error"}

    async def set_expend_points(self, user_id: int, points: int, code: str) -> bool:
        """Track points expenditure"""
        try:
            await self.transactions.insert_one({
                "user_id": user_id,
                "type": "free_points",
                "amount": points,
                "code": code,
                "timestamp": datetime.datetime.now().isoformat()
            })
            return True
        except Exception as e:
            logging.error(f"Error tracking points expenditure: {e}")
            return False

    async def update_leaderboards(self):
        """Update all leaderboards (run periodically)."""
        await self._update_daily_leaderboard()
        await self._update_weekly_leaderboard()
        await self._update_monthly_leaderboard()
        await self._update_alltime_leaderboard()

    async def _update_daily_leaderboard(self):
        """Update daily leaderboard."""
        try:
            today = datetime.datetime.now().date()
            
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
            
            await self._save_leaderboard("daily", today.isoformat(), {
                "points": points_leaders,
                "renames": rename_leaders
            })
        except Exception as e:
            logging.error(f"Error updating daily leaderboard: {e}")

    async def _update_weekly_leaderboard(self):
        """Update weekly leaderboard."""
        try:
            today = datetime.datetime.now().date()
            start_of_week = today - datetime.timedelta(days=today.weekday())
            
            weekly_points = await self.transactions.aggregate([
                {
                    "$match": {
                        "type": "credit",
                        "timestamp": {
                            "$gte": datetime.datetime.combine(start_of_week, datetime.time.min).isoformat()
                        }
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id",
                        "value": {"$sum": "$amount"}
                    }
                },
                {"$sort": {"value": -1}},
                {"$limit": 100},
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
                    "value": 1,
                    "is_premium": "$user.premium.is_premium"
                }}
            ]).to_list(length=100)
            
            weekly_renames = await self.file_stats.aggregate([
                {
                    "$match": {
                        "date": {"$gte": start_of_week.isoformat()}
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id",
                        "value": {"$sum": 1}
                    }
                },
                {"$sort": {"value": -1}},
                {"$limit": 100},
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
                    "value": 1,
                    "is_premium": "$user.premium.is_premium"
                }}
            ]).to_list(length=100)
            
            await self._save_leaderboard("weekly", start_of_week.isoformat(), {
                "points_earned": weekly_points,
                "renames": weekly_renames
            })
        except Exception as e:
            logging.error(f"Error updating weekly leaderboard: {e}")

    async def _update_monthly_leaderboard(self):
        """Update monthly leaderboard."""
        try:
            today = datetime.datetime.now().date()
            start_of_month = datetime.date(today.year, today.month, 1)
            
            monthly_points = await self.transactions.aggregate([
                {
                    "$match": {
                        "type": "credit",
                        "timestamp": {
                            "$gte": datetime.datetime.combine(start_of_month, datetime.time.min).isoformat()
                        }
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id",
                        "value": {"$sum": "$amount"}
                    }
                },
                {"$sort": {"value": -1}},
                {"$limit": 100},
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
                    "value": 1,
                    "is_premium": "$user.premium.is_premium"
                }}
            ]).to_list(length=100)
            
            monthly_renames = await self.file_stats.aggregate([
                {
                    "$match": {
                        "date": {"$gte": start_of_month.isoformat()}
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id",
                        "value": {"$sum": 1}
                    }
                },
                {"$sort": {"value": -1}},
                {"$limit": 100},
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
                    "value": 1,
                    "is_premium": "$user.premium.is_premium"
                }}
            ]).to_list(length=100)
            
            await self._save_leaderboard("monthly", start_of_month.isoformat(), {
                "points_earned": monthly_points,
                "renames": monthly_renames
            })
        except Exception as e:
            logging.error(f"Error updating monthly leaderboard: {e}")

    async def _update_alltime_leaderboard(self):
        """Update all-time leaderboard."""
        try:
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
            
            rename_leaders = await self.users.aggregate([
                {"$match": {"ban_status.is_banned": False}},
                {"$sort": {"activity.total_files_renamed": -1}},
                {"$limit": 100},
                {"$project": {
                    "_id": 1,
                    "username": 1,
                    "value": "$activity.total_files_renamed",
                    "is_premium": "$premium.is_premium"
                }}
            ]).to_list(length=100)
            
            await self._save_leaderboard("alltime", "alltime", {
                "points": points_leaders,
                "renames": rename_leaders
            })
        except Exception as e:
            logging.error(f"Error updating alltime leaderboard: {e}")

    async def _save_leaderboard(self, period: str, date_key: str, data: Dict):
        """Save leaderboard data to database."""
        try:
            await self.leaderboards.update_one(
                {
                    "period": period,
                    "date_key": date_key
                },
                {
                    "$set": {
                        "data": data,
                        "updated_at": datetime.datetime.now().isoformat()
                    }
                },
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error saving {period} leaderboard: {e}")

    async def get_leaderboard(self, period: str = "daily", 
                            lb_type: str = "points") -> List[Dict]:
        """
        Get leaderboard data.
        
        Args:
            period: "daily", "weekly", "monthly", or "alltime"
            lb_type: "points", "renames", or "points_earned"
            
        Returns:
            list: Leaderboard entries with user details
        """
        try:
            if period not in ["daily", "weekly", "monthly", "alltime"]:
                period = "daily"
                
            leaderboard = await self.leaderboards.find_one({
                "period": period,
                "date_key": {
                    "$ne": None if period != "alltime" else "alltime"
                }
            }, sort=[("date_key", -1)])
            
            if not leaderboard:
                return []
                
            return leaderboard["data"].get(lb_type, [])
        except Exception as e:
            logging.error(f"Error getting {period} leaderboard: {e}")
            return []

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
                                    {"$gt": ["$expires_at", datetime.datetime.now().isoformat()]},
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
            logging.error(f"Error getting points links stats: {e}")
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
                            "$gte": start_date.isoformat(),
                            "$lte": end_date.isoformat()
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
                            "$gte": start_date.isoformat(),
                            "$lte": end_date.isoformat()
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
            logging.error(f"Error generating points report: {e}")
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
            logging.error(f"Error getting banned users: {e}")
            return []

    async def get_sequential_mode(self, user_id: int) -> bool:
        """Get user's sequential mode setting."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("settings", {}).get("sequential_mode", False) if user else False
        except Exception as e:
            logging.error(f"Error getting sequential mode for {user_id}: {e}")
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
            logging.error(f"Error toggling sequential mode for {user_id}: {e}")
            return False
    
    async def get_user_channel(self, user_id: int) -> Optional[str]:
        """Get user's dump channel ID."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("settings", {}).get("user_channel") if user else None
        except Exception as e:
            logging.error(f"Error getting user channel for {user_id}: {e}")
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
            logging.error(f"Error setting user channel for {user_id}: {e}")
            return False
    
    async def get_leaderboard_period(self, user_id: int) -> str:
        """Get user's preferred leaderboard period."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("settings", {}).get("leaderboard_period", "weekly") if user else "weekly"
        except Exception as e:
            logging.error(f"Error getting leaderboard period for {user_id}: {e}")
            return "weekly"
    
    async def set_leaderboard_period(self, user_id: int, period: str) -> bool:
        """Set user's preferred leaderboard period."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"settings.leaderboard_period": period}}
            )
            return True
        except Exception as e:
            logging.error(f"Error setting leaderboard period for {user_id}: {e}")
            return False
    
    async def get_leaderboard_type(self, user_id: int) -> str:
        """Get user's preferred leaderboard type."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("settings", {}).get("leaderboard_type", "points") if user else "points"
        except Exception as e:
            logging.error(f"Error getting leaderboard type for {user_id}: {e}")
            return "points"
    
    async def set_leaderboard_type(self, user_id: int, lb_type: str) -> bool:
        """Set user's preferred leaderboard type."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"settings.leaderboard_type": lb_type}}
            )
            return True
        except Exception as e:
            logging.error(f"Error setting leaderboard type for {user_id}: {e}")
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
            logging.error(f"Error banning user {user_id}: {e}")
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
            logging.error(f"Error unbanning user {user_id}: {e}")
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
            logging.error(f"Error setting referrer for {user_id}: {e}")
            return False

    async def is_refferer(self, user_id: int) -> Optional[int]:
        """Check if user is a referrer and return their referrer ID."""
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("referral", {}).get("referrer_id") if user else None
        except Exception as e:
            logging.error(f"Error getting referrer for user {user_id}: {e}")
            return None

    async def total_renamed_files(self) -> int:
        """Get total number of files renamed across all users."""
        try:
            result = await self.users.aggregate([
                {"$group": {"_id": None, "total": {"$sum": "$activity.total_files_renamed"}}}
            ]).to_list(length=1)
            return result[0]["total"] if result else 0
        except Exception as e:
            logging.error(f"Error counting total renamed files: {e}")
            return 0

    async def clear_all_user_channels(self) -> None:
        """Remove the 'user_channel' field from all user documents."""
        if not self.users:
            logging.error("❌ 'users' collection is not initialized.")
            return
    
        try:
            result = await self.users.update_many(
                {},  # Match all documents
                {"$unset": {"settings.user_channel": ""}}  # Use $unset to remove the field
            )
            logging.info(f"✅ Removed 'user_channel' from {result.modified_count} users.")
        except Exception as e:
            logging.error(f"❌ Error while removing 'user_channel': {e}")

    async def total_points_distributed(self) -> int:
        """Get total points distributed across all users."""
        try:
            result = await self.users.aggregate([
                {"$group": {"_id": None, "total": {"$sum": "$points.total_earned"}}}
            ]).to_list(length=1)
            return result[0]["total"] if result else 0
        except Exception as e:
            logging.error(f"Error counting total points distributed: {e}")
            return 0
    
    async def get_config(self, key: str, default=None):
        """Get configuration value with default fallback."""
        try:
            config = await self.config.find_one({"key": key})
            return config["value"] if config else default
        except Exception as e:
            logging.error(f"Error getting config {key}: {e}")
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
            return hyoshcoder
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Failed to initialize database after {max_retries} attempts: {e}")
                raise
            logger.warning(f"⚠️ Database connection failed (attempt {attempt + 1}), retrying in {retry_delay}s...")
            import asyncio
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
