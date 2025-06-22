import motor.motor_asyncio
import pytz
import secrets
import asyncio
import uuid
import re
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any
from bson.objectid import ObjectId
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError, ConnectionFailure
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, time  # Include `time`
from config import settings
from pyrogram import Client

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
        self.leaderboards = None
        self.file_stats = None
        self.config = None
        self.sequences = None  # Will store completed sequences
        self.active_sequences = None  # Will track in-progress sequences
        self.sequence_stats = None  # Will store aggregated sequence stats
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
            self.sequences = self.db["active_sequences"]
            self.users_sequence = self.db["users_sequence"]
            self.token_links = self.db["token_links"]
            self.global_referrals = self.db["global_referrals"]  # Add this line
            self.transactions = self.db.transactions
            self.rewards = self.db.rewards
            self.leaderboards = self.db.leaderboards
            self.file_stats = self.db.file_stats
            self.referrals = self.db.referrals
            self.config = self.db.config
            self._is_connected = True
            self.sequences = self.db.sequences
            self.active_sequences = self.db.active_sequences
            self.sequence_stats = self.db.sequence_stats

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
            # Users collection - Enhanced for all leaderboard types
            ("users", [("_id", 1)]),  # Essential for primary key lookups
            ("users", [("ban_status.is_banned", 1)]),  # For filtering banned users
            ("users", [("points.balance", -1)]),  # For points leaderboard
            ("users", [("activity.total_files_renamed", -1)]),  # For renames leaderboard
            ("users", [("referral.referred_count", -1)]),  # For referral leaderboard
            ("users", [("activity.last_active", -1)]),  # For time-based filtering
            ("users", [("premium.is_premium", 1)]),  # For premium user filtering
            ("users", [("join_date", -1)]),  # For referral tracking
            
            # File stats collection - Optimized for renames leaderboard
            ("file_stats", [("user_id", 1), ("timestamp", -1)]),  # Compound index for user activity
            ("file_stats", [("timestamp", -1)]),  # For time-based queries
            ("file_stats", [("date", 1)]),  # For daily aggregations
            
            # Referral tracking (if using separate collection)
            ("referrals", [("referrer_id", 1), ("joined_at", -1)]),
            ("referrals", [("joined_at", -1)]),
            
            # Leaderboard cache
            ("leaderboards", [("period", 1), ("type", 1), ("updated_at", -1)]),  # Compound index
            
            # Sequences
            ("active_sequences", [("user_id", 1)], {"unique": True}),
            ("users_sequence", [("files_sequenced", -1)]),
            
            # Config
            ("config", [("key", 1)], {"unique": True}),
            
            # Additional performance indexes
            ("users", [("username", 1)]),  # For username lookups
            ("users", [("settings.leaderboard_period", 1), ("settings.leaderboard_type", 1)]),
        ]
        for entry in indexes:
            collection_name, keys, *options = entry if len(entry) > 2 else [*entry, {}]
            opts = options[0] if options else {}
            
            try:
                # Skip if collection doesn't exist
                if collection_name not in await self.db.list_collection_names():
                    continue
                    
                await self.db[collection_name].create_index(keys, **opts)
                logger.info(f"Created index on {collection_name} for {keys}")
            except Exception as e:
                logger.error(f"Failed to create index on {collection_name}: {e}")
                if collection_name == "users" and "referral.referred_count" in keys:
                    raise  # Critical index, fail hard

    def set_client(self, client: Client):
        """Store the Pyrogram client for Telegram API calls"""
        self._pyrogram_client = client
        logger.info("Pyrogram client set for database operations")

    def new_user(self, id: int) -> Dict[str, Any]:
        """Create a new user document with ad campaign support."""
        now = datetime.now(pytz.timezone("Asia/Kolkata"))
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
                "balance": 2000,
                "total_earned": 2000,
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

    async def start_sequence(self, user_id: int) -> bool:
        """Start tracking a new sequence for a user"""
        try:
            await self.active_sequences.insert_one({
                "user_id": user_id,
                "start_time": datetime.now(pytz.UTC),
                "files": [],
                "last_update": datetime.now(pytz.UTC)
            })
            return True
        except Exception as e:
            logger.error(f"Error starting sequence for {user_id}: {e}")
            return False

    async def add_to_sequence(self, user_id: int, file_id: str, file_name: str) -> bool:
        """Add a file to an active sequence"""
        try:
            result = await self.active_sequences.update_one(
                {"user_id": user_id},
                {
                    "$push": {"files": {"file_id": file_id, "file_name": file_name}},
                    "$set": {"last_update": datetime.now(pytz.UTC)}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error adding file to sequence for {user_id}: {e}")
            return False

    async def end_sequence(self, user_id: int) -> Tuple[bool, List[Dict]]:
        """Complete a sequence and return the files"""
        try:
            # Get and remove the active sequence
            sequence = await self.active_sequences.find_one_and_delete({"user_id": user_id})
            if not sequence:
                return False, []
                
            # Record the completed sequence
            await self.sequences.insert_one({
                "user_id": user_id,
                "file_count": len(sequence["files"]),
                "start_time": sequence["start_time"],
                "end_time": datetime.now(pytz.UTC),
                "duration_seconds": (datetime.now(pytz.UTC) - sequence["start_time"]).total_seconds()
            })
            
            # Update sequence stats
            await self._update_sequence_stats(user_id, len(sequence["files"]))
            
            return True, sequence["files"]
        except Exception as e:
            logger.error(f"Error ending sequence for {user_id}: {e}")
            return False, []

    async def _update_sequence_stats(self, user_id: int, file_count: int) -> bool:
        """Update user's sequence statistics"""
        try:
            await self.sequence_stats.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "total_sequences": 1,
                        "total_files": file_count,
                        "current_streak": 1
                    },
                    "$set": {
                        "last_sequence": datetime.now(pytz.UTC),
                        "longest_streak": await self._calculate_longest_streak(user_id)
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error updating sequence stats for {user_id}: {e}")
            return False

    async def _calculate_longest_streak(self, user_id: int) -> int:
        """Calculate the user's longest sequence streak"""
        try:
            stats = await self.sequence_stats.find_one({"user_id": user_id})
            if not stats:
                return 1
                
            current_streak = stats.get("current_streak", 1)
            longest_streak = stats.get("longest_streak", 1)
            
            return max(current_streak, longest_streak)
        except Exception as e:
            logger.error(f"Error calculating streak for {user_id}: {e}")
            return 1

    async def get_sequence_stats(self, user_id: int) -> Dict:
        """Get user's sequence statistics"""
        try:
            stats = await self.sequence_stats.find_one({"user_id": user_id})
            if not stats:
                return {
                    "total_sequences": 0,
                    "total_files": 0,
                    "current_streak": 0,
                    "longest_streak": 0,
                    "last_sequence": None
                }
            return stats
        except Exception as e:
            logger.error(f"Error getting sequence stats for {user_id}: {e}")
            return {
                "total_sequences": 0,
                "total_files": 0,
                "current_streak": 0,
                "longest_streak": 0,
                "last_sequence": None
            }

    async def get_top_sequences(self, limit: int = 10) -> List[Dict]:
        """Get top users by sequence file count"""
        try:
            return await self.sequence_stats.aggregate([
                {"$sort": {"total_files": -1}},
                {"$limit": limit},
                {"$project": {
                    "user_id": 1,
                    "total_files": 1,
                    "total_sequences": 1,
                    "longest_streak": 1
                }}
            ]).to_list(length=limit)
        except Exception as e:
            logger.error(f"Error getting top sequences: {e}")
            return []

    async def get_user_sequence_rank(self, user_id: int) -> Tuple[Optional[int], int]:
        """Get user's rank and total files in sequences"""
        try:
            # Get all users sorted by total files in sequences
            all_users = await self.sequence_stats.aggregate([
                {"$sort": {"total_files": -1}},
                {"$project": {"user_id": 1, "total_files": 1}}
            ]).to_list(None)
            
            # Find the user's position
            for index, user in enumerate(all_users, start=1):
                if user["user_id"] == user_id:
                    return index, user["total_files"]
                    
            return None, 0
        except Exception as e:
            logger.error(f"Error getting sequence rank for {user_id}: {e}")
            return None, 0

    # Create a point link (valid for 24 hours, one-time use)
    async def create_point_link(self, user_id: int, point_id: str, points: int):
        expiry = datetime.utcnow().replace(tzinfo=pytz.UTC) + timedelta(hours=24)
        try:
            await self.token_links.update_one(
                {"_id": point_id},
                {
                    "$set": {
                        "user_id": user_id,
                        "points": points,
                        "used": False,
                        "expiry": expiry
                    }
                },
                upsert=True
            )
            logging.info(f"Point link created for user {user_id} with ID {point_id}.")
        except Exception as e:
            logging.error(f"Error creating point link: {e}")
    
    # Fetch a point link by ID
    async def get_point_link(self, point_id: str):
        try:
            return await self.token_links.find_one({"_id": point_id})
        except Exception as e:
            logging.error(f"Error fetching point link for ID {point_id}: {e}")
            return None
    
    # Mark a point link as used
    async def mark_point_used(self, point_id: str):
        try:
            await self.token_links.update_one(
                {"_id": point_id},
                {"$set": {"used": True}}
            )
            logging.info(f"Point link {point_id} marked as used.")
        except Exception as e:
            logging.error(f"Error marking point link as used: {e}")

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
    async def create_referral_code(self, user_id: int) -> str:
        """Generate and store a unique referral code for a user."""
        while True:
            code = secrets.token_hex(3).upper()  # 6-character code
            existing = await self.users.find_one({"referral.referral_code": code})
            if not existing:
                await self.users.update_one(
                    {"_id": user_id},
                    {"$set": {"referral.referral_code": code}},
                    upsert=True
                )
                return code
    
    async def process_referral(self, referrer_id: int, referred_id: int) -> bool:
        """
        Process a referral in a transactional way.
        Returns True if successful, False if referral already exists or failed.
        """
        try:
            async with await self._client.start_session() as session:
                async with session.start_transaction():
                    # Check if referral already exists
                    existing = await self.global_referrals.find_one(
                        {"referrer_id": referrer_id, "referred_id": referred_id},
                        session=session
                    )
                    if existing:
                        return False
    
                    # Record the referral
                    await self.global_referrals.insert_one(
                        {
                            "referrer_id": referrer_id,
                            "referred_id": referred_id,
                            "timestamp": datetime.now(),
                            "status": "pending"
                        },
                        session=session
                    )
    
                    # Update both users' records
                    await self.users.update_one(
                        {"_id": referred_id},
                        {"$set": {"referral.referrer_id": referrer_id}},
                        session=session
                    )
    
                    await self.users.update_one(
                        {"_id": referrer_id},
                        {
                            "$inc": {
                                "referral.referred_count": 1,
                                "points.balance": settings.REFER_POINT_REWARD
                            },
                            "$addToSet": {"referral.referred_users": referred_id}
                        },
                        session=session
                    )
    
                    # Add points to referred user
                    await self.users.update_one(
                        {"_id": referred_id},
                        {"$inc": {"points.balance": settings.REFER_POINT_REWARD}},
                        session=session
                    )
    
                    # Mark referral as completed
                    await self.global_referrals.update_one(
                        {"referrer_id": referrer_id, "referred_id": referred_id},
                        {"$set": {"status": "completed"}},
                        session=session
                    )
    
                    return True
    
        except Exception as e:
            logger.error(f"Referral processing failed: {e}")
            return False
    
    async def get_referral_info(self, user_id: int) -> dict:
        """Get user's referral information including code and stats."""
        user = await self.users.find_one({"_id": user_id})
        if not user:
            return None
    
        referral_data = user.get("referral", {})
        return {
            "code": referral_data.get("referral_code"),
            "count": referral_data.get("referred_count", 0),
            "earnings": referral_data.get("referral_earnings", 0),
            "referred_users": referral_data.get("referred_users", [])
        }
    async def verify_shortlink_click(self, user_id: int, link_type: str) -> bool:
        """Verify shortlink click and reward user"""
        try:
            points = 5  # Points to reward per click
            
            # Add points to user
            await self.add_points(
                user_id, 
                points, 
                source="shortlink", 
                description=f"{link_type} link click"
            )
            
            # Track in database
            await self.rewards.insert_one({
                "user_id": user_id,
                "type": link_type,
                "points": points,
                "timestamp": datetime.utcnow()
            })
            
            return True
        except Exception as e:
            logger.error(f"Error verifying shortlink: {e}")
            return False
    # Add these patterns as a class variable
    EPISODE_PATTERNS = [
        re.compile(r'\b(?:EP|E)\s*-\s*(\d{1,3})\b', re.IGNORECASE),
        re.compile(r'\b(?:EP|E)\s*(\d{1,3})\b', re.IGNORECASE),
        re.compile(r'S(\d+)(?:E|EP)(\d+)', re.IGNORECASE),
        re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)\s*(\d+)', re.IGNORECASE),
        re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)', re.IGNORECASE),
        re.compile(r'(?:EP|E)?\s*[-]?\s*(\d{1,3})', re.IGNORECASE),
        re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE),
        re.compile(r'(\d+)')
    ]
    
    # Add these methods to your Database class
    def _extract_episode_number(self, filename: str) -> int:
        """Extract episode number from filename for sorting"""
        for pattern in self.EPISODE_PATTERNS:
            match = pattern.search(filename)
            if match:
                return int(match.groups()[-1])
        return float('inf')
    
    async def is_in_sequence_mode(self, user_id: int) -> bool:
        """Check if user is in sequence mode"""
        return await self.sequences.find_one({"user_id": user_id}) is not None
    
    async def start_sequence(self, user_id: int, username: str) -> bool:
        """Start a new sequence for user"""
        if await self.is_in_sequence_mode(user_id):
            return False
            
        await self.sequences.insert_one({
            "user_id": user_id,
            "username": username,
            "files": [],
            "started_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        return True
    
    async def add_file_to_sequence(self, user_id: int, file_data: Dict) -> bool:
        """Add a file to user's sequence"""
        result = await self.sequences.update_one(
            {"user_id": user_id},
            {"$push": {"files": file_data},
             "$set": {"updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    
    async def get_sequence_files(self, user_id: int) -> Optional[List[Dict]]:
        """Get all files in user's sequence"""
        sequence = await self.sequences.find_one({"user_id": user_id})
        if sequence:
            return sorted(sequence.get("files", []), key=lambda x: self._extract_episode_number(x["filename"]))
        return None
    
    async def end_sequence(self, user_id: int) -> bool:
        """Delete user's sequence"""
        result = await self.sequences.delete_one({"user_id": user_id})
        return result.deleted_count > 0
    
    async def increment_sequence_count(self, user_id: int, username: str, count: int = 1) -> None:
        """Increment user's sequenced files count in leaderboard"""
        await self.users_sequence.update_one(
            {"_id": user_id},
            {
                "$inc": {"files_sequenced": count},
                "$set": {
                    "username": username,
                    "last_active": datetime.utcnow()
                }
            },
            upsert=True
        )



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


    async def update_user_activity(self, user_id: int) -> bool:
        """Update user's last active timestamp."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"activity.last_active": datetime.utcnow()}}
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
            today = datetime.utcnow().date()
            start_of_day = datetime.combine(today, time.min)
            return await self.users.count_documents({
                "activity.last_active": {
                    "$gte": start_of_day
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
                {"$set": {"deleted": True, "deleted_at": datetime.utcnow()}}
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
        """Track a file rename operation with proper date handling."""
        try:
            now = datetime.utcnow()
            result = await self.file_stats.insert_one({
                "user_id": user_id,
                "original_name": file_name,
                "new_name": new_name,
                "timestamp": now,
                "date": now.date().isoformat()  # Store as ISO format string
            })
    
            await self.users.update_one(
                {"_id": user_id},
                {
                    "$inc": {"activity.total_files_renamed": 1},
                    "$set": {"activity.last_active": now}
                }
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
            today = datetime.utcnow().date()
            start_of_week = today - timedelta(days=today.weekday())
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
    
            now = datetime.utcnow()
            today = now.date()
            start_of_week = today - timedelta(days=today.weekday())
            start_of_month = datetime(today.year, today.month, 1).date()
    
            # Convert dates to datetime objects at midnight for proper comparison
            today_start = datetime.combine(today, datetime.min.time())
            week_start = datetime.combine(start_of_week, datetime.min.time())
            month_start = datetime.combine(start_of_month, datetime.min.time())
    
            # Get all user's file stats
            file_stats = await self.file_stats.find({"user_id": user_id}).to_list(None)
    
            for stat in file_stats:
                if not isinstance(stat.get("date"), datetime):
                    # Convert string dates or timestamps to datetime if needed
                    if isinstance(stat.get("date"), str):
                        stat_date = datetime.fromisoformat(stat["date"])
                    elif isinstance(stat.get("date"), (int, float)):
                        stat_date = datetime.fromtimestamp(stat["date"])
                    else:
                        continue
                else:
                    stat_date = stat["date"]
    
                # Compare dates
                if stat_date >= today_start:
                    stats["today"] += 1
                if stat_date >= week_start:
                    stats["this_week"] += 1
                if stat_date >= month_start:
                    stats["this_month"] += 1
    
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
                    "$set": {"points.last_earned": datetime.utcnow()}
                }
            )

            await self.transactions.insert_one({
                "user_id": user_id,
                "type": "credit",
                "amount": points,
                "source": source,
                "description": description or f"Added {points} points",
                "timestamp": datetime.utcnow(),
                "balance_after": (await self.get_points(user_id)) + points
            })

            return True
        except Exception as e:
            logger.error(f"Error adding points to {user_id}: {e}")
            return False
    async def safe_increment_points(self, user_id: int, amount: int) -> bool:
        """Safely increment points regardless of current format"""
        try:
            user = await self.users.find_one({"_id": user_id})
            if not user:
                return False
                
            if isinstance(user.get("points"), dict):
                # New format
                await self.users.update_one(
                    {"_id": user_id},
                    {"$inc": {"points.balance": amount}}
                )
            else:
                # Old format
                await self.users.update_one(
                    {"_id": user_id},
                    {"$inc": {"points": amount}}
                )
            return True
        except Exception as e:
            logger.error(f"Error incrementing points: {e}")
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
                "timestamp": datetime.utcnow(),
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
                             original_points: int, premium_points: int):
        """Activate premium with unlimited points"""
        expiry_date = datetime.now() + timedelta(days=duration_days)
        
        await self.db.users.update_one(
            {"_id": user_id},
            {"$set": {
                "premium": {
                    "is_premium": True,
                    "plan": plan,
                    "activated_at": datetime.now(),
                    "expires_at": expiry_date,
                    "original_points": original_points,
                    "premium_points": premium_points
                },
                "points.balance": premium_points
            }},
            upsert=True
        )
    
    async def check_premium_expiry(self):
        """Check and handle expired premium users"""
        now = datetime.now()
        expired_users = self.db.users.find({
            "premium.is_premium": True,
            "premium.expires_at": {"$lt": now}
        })
        
        async for user in expired_users:
            try:
                original_points = user['premium']['original_points']
                await self.db.users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "premium.is_premium": False,
                        "premium.expired_at": now,
                        "points.balance": original_points
                    }}
                )
                logger.info(f"Premium expired for user {user['_id']}, points reverted to {original_points}")
            except Exception as e:
                logger.error(f"Error handling premium expiry for user {user['_id']}: {e}")
    
    async def check_premium_status(self, user_id: int) -> Dict:
        """Check user's premium status with auto-expiration"""
        try:
            user = await self.db.users.find_one({"_id": user_id})
            if not user:
                return {"is_premium": False, "reason": "User not found"}
            
            premium = user.get("premium", {})
            if not premium.get("is_premium", False):
                return {"is_premium": False, "reason": "No active premium"}
            
            # Check if premium has expired
            if "expires_at" in premium and premium["expires_at"] < datetime.now():
                await self.check_premium_expiry()  # Force immediate check
                return {"is_premium": False, "reason": "Subscription expired"}
            
            return {
                "is_premium": True,
                "plan": premium.get("plan"),
                "expires_at": premium.get("expires_at"),
                "activated_at": premium.get("activated_at"),
                "points": premium.get("premium_points")
            }
            
        except Exception as e:
            logger.error(f"Error checking premium status for {user_id}: {e}")
            return {"is_premium": False, "reason": "Error checking status"}

    async def deactivate_premium(self, user_id: int, reason: str = "Admin deactivation") -> bool:
        """Deactivate premium and revert points"""
        try:
            user = await self.db.users.find_one({"_id": user_id})
            if not user:
                return False
                
            original_points = user.get("premium", {}).get("original_points", user["points"]["balance"])
            
            result = await self.db.users.update_one(
                {"_id": user_id},
                {"$set": {
                    "premium.is_premium": False,
                    "premium.expired_at": datetime.now(),
                    "premium.deactivation_reason": reason,
                    "points.balance": original_points
                }}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error deactivating premium for {user_id}: {e}")
            return False
    async def get_expend_points(self, user_id: int) -> int:
        """Retrieve how many expendable points the user has"""
        user = await self.users.find_one({"_id": user_id})
        if user and "expend_points" in user:
            return user["expend_points"]
        return 0

    
  
    async def set_expend_points(self, user_id: int, points: int, code: Optional[str] = None) -> Dict:
        try:
            if not code:
                code = str(uuid.uuid4())[:8]
    
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {
                    "unique_code": code,
                    "expend_points": points,
                    "code_used": False,
                    "expires_at": datetime.utcnow() + timedelta(hours=24)
                }}
            )
            return {
                "success": True,
                "code": code,
                "points": points
            }
        except Exception as e:
            logger.error(f"Error setting expend points: {e}")
            return {
                "success": False,
                "error": str(e)
            }


    # --- Update all leaderboards ---
    async def update_leaderboards(self):
        try:
            for period in ["daily", "weekly", "monthly", "alltime"]:
                await self.update_leaderboard_period(period)
                await self.update_renames_leaderboard(period)
                await self.update_referral_leaderboard(period)
            logger.info("All leaderboards updated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to update leaderboards: {e}")
            return False

    async def update_leaderboard_period(self, period: str):
        try:
            leaders = await self.get_leaderboard(period)
            await self.leaderboards.update_one(
                {"period": period, "type": "points"},
                {"$set": {"data": leaders, "updated_at": datetime.utcnow()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating {period} points leaderboard: {e}")

    # In your data.py, update these methods:

    async def get_leaderboard(self, period: str, limit: int = 10) -> List[Dict]:
        """Get points leaderboard for a specific period."""
        try:
            now = datetime.utcnow()
            match_stage = {"ban_status.is_banned": False}
            
            if period != "alltime":
                days = 1 if period == "daily" else 7 if period == "weekly" else 30
                start_date = now - timedelta(days=days)
                match_stage["activity.last_active"] = {"$gte": start_date}
    
            pipeline = [
                {"$match": match_stage},
                {"$sort": {"points.balance": -1}},
                {"$limit": limit},
                {"$project": {
                    "_id": 1,
                    "username": 1,
                    "points": "$points.balance",
                    "is_premium": "$premium.is_premium",
                    "last_active": "$activity.last_active"
                }}
            ]
            return await self.users.aggregate(pipeline).to_list(length=limit)
        except Exception as e:
            logger.error(f"Error getting {period} points leaderboard: {e}")
            return []

    async def get_renames_leaderboard(self, period: str = "weekly", limit: int = 10) -> List[Dict]:
        """Get renames leaderboard for a specific period."""
        try:
            now = datetime.utcnow()
            days = 1 if period == "daily" else 7 if period == "weekly" else 30
            start_date = now - timedelta(days=days) if period != "alltime" else None
    
            pipeline = [
                {"$match": {"timestamp": {"$gte": start_date}} if start_date else {}},
                {"$group": {
                    "_id": "$user_id",
                    "total_renames": {"$sum": 1},
                    "last_rename": {"$max": "$timestamp"}
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
                    "_id": "$_id",
                    "username": "$user.username",
                    "total_renames": 1,
                    "is_premium": "$user.premium.is_premium",
                    "last_active": "$user.activity.last_active"
                }}
            ]
            results = await self.file_stats.aggregate(pipeline).to_list(length=limit)
            return results
        except Exception as e:
            logger.error(f"Error getting {period} renames leaderboard: {e}")
            return []

    async def get_referral_leaderboard(self, period: str = "weekly", limit: int = 10) -> List[Dict]:
        """Get referral leaderboard for a specific period."""
        try:
            now = datetime.utcnow()
            days = 1 if period == "daily" else 7 if period == "weekly" else 30
            start_date = now - timedelta(days=days) if period != "alltime" else None
    
            pipeline = [
                {"$match": {
                    "referral.referrer_id": {"$ne": None},
                    "join_date": {"$gte": start_date} if start_date else {"$exists": True}
                }},
                {"$group": {
                    "_id": "$referral.referrer_id",
                    "total_referrals": {"$sum": 1},
                    "last_referral": {"$max": "$join_date"}
                }},
                {"$sort": {"total_referrals": -1}},
                {"$limit": limit},
                {"$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "user"
                }},
                {"$unwind": "$user"},
                {"$project": {
                    "_id": "$_id",
                    "username": "$user.username",
                    "total_referrals": 1,
                    "is_premium": "$user.premium.is_premium",
                    "last_active": "$user.activity.last_active"
                }}
            ]
            results = await self.users.aggregate(pipeline).to_list(length=limit)
            return results
        except Exception as e:
            logger.error(f"Error getting {period} referral leaderboard: {e}")
            return []

    async def update_referral_leaderboard(self, period: str):
        try:
            leaders = await self.get_referral_leaderboard(period)
            await self.leaderboards.update_one(
                {"type": "referrals", "period": period},
                {"$set": {"data": leaders, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error updating referral leaderboard for {period}: {e}")
            return False

    async def update_renames_leaderboard(self, period: str):
        try:
            leaders = await self.get_renames_leaderboard(period)
            await self.leaderboards.update_one(
                {"type": "renames", "period": period},
                {"$set": {"data": leaders, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Error updating renames leaderboard for {period}: {e}")
            return False

    async def get_cached_leaderboard(self, period: str, lb_type: str) -> List[Dict]:
        try:
            cache = await self.leaderboards.find_one({"period": period, "type": lb_type})
            if cache and (datetime.utcnow() - cache["updated_at"]).total_seconds() < 3600:
                return cache["data"]

            if lb_type == "points":
                data = await self.get_leaderboard(period)
            elif lb_type == "renames":
                data = await self.get_renames_leaderboard(period)
            elif lb_type == "referrals":
                data = await self.get_referral_leaderboard(period)
            else:
                return []

            await self.leaderboards.update_one(
                {"period": period, "type": lb_type},
                {"$set": {"data": data, "updated_at": datetime.utcnow()}},
                upsert=True
            )
            return data
        except Exception as e:
            logger.error(f"Error getting cached leaderboard: {e}")
            return []

    async def set_leaderboard_period(self, user_id: int, period: str) -> bool:
        if period not in ["daily", "weekly", "monthly", "alltime"]:
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
        try:
            user = await self.users.find_one({"_id": user_id})
            return user.get("settings", {}).get("leaderboard_period", "weekly")
        except Exception as e:
            logger.error(f"Error getting leaderboard period: {e}")
            return "weekly"

    async def set_leaderboard_type(self, user_id: int, lb_type: str) -> bool:
        if lb_type not in ["points", "renames", "referrals"]:
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
                                    {"$gt": ["$expires_at", datetime.utcnow()]},
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
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

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
                    "start": (datetime.utcnow() - timedelta(days=days)).isoformat(),
                    "end": datetime.utcnow().isoformat()
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
    async def set_sequential_mode(self, user_id: int, enabled: bool) -> bool:
        """Set user's sequential mode setting."""
        try:
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"settings.sequential_mode": enabled}}
            )
            return True
        except Exception as e:
            logger.error(f"Error setting sequential mode for {user_id}: {e}")
            return False
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
            result = await self.users.update_one(
                {"_id": user_id},
                {"$set": {"settings.user_channel": channel_id}},
                upsert=True
            )
            return result.acknowledged
        except Exception as e:
            logger.error(f"Error setting user channel for {user_id}: {e}")
            return False

    async def ban_user(self, user_id: int, duration_days: int, reason: str) -> bool:
        """Ban a user from using the bot."""
        try:
            banned_on = datetime.utcnow(pytz.timezone("Africa/Lubumbashi")).isoformat()
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
            # First set the referrer for the new user
            await self.users.update_one(
                {"_id": user_id},
                {"$set": {"referral.referrer_id": referrer_id}},
                upsert=True
            )
    
            # Update referrer's stats
            await self.users.update_one(
                {"_id": referrer_id},
                {
                    "$inc": {
                        "referral.referred_count": 1,
                        "referral.referral_earnings": settings.REFER_POINT_REWARD
                    },
                    "$addToSet": {"referral.referred_users": user_id}
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
    async def reset_database(self, admin_id: int) -> Dict[str, int]:
        """Completely reset all bot-related collections (admin only)"""
        try:
            # Get counts before deletion
            user_count = await self.users.count_documents({})
            file_stats_count = await self.file_stats.count_documents({})
            token_links_count = await self.token_links.count_documents({})
            
            # Delete all documents in each collection
            await self.users.delete_many({})
            await self.file_stats.delete_many({})
            await self.token_links.delete_many({})
            await self.transactions.delete_many({})
            await self.leaderboards.delete_many({})
            await self.sequences.delete_many({})
            
            # Recreate indexes
            await self._create_indexes()
            
            # Re-add the admin who executed the command
            if admin_id:
                await self.add_user(admin_id)
            
            return {
                "users_deleted": user_count,
                "files_deleted": file_stats_count,
                "tokens_deleted": token_links_count,
                "status": "Database reset complete"
            }
            
        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            return {"error": str(e)}
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
            await hyoshcoder.update_leaderboards()  # <- fixed here
            return hyoshcoder
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Failed to initialize database after {max_retries} attempts: {e}")
                raise
            logger.warning(f"⚠️ Database connection failed (attempt {attempt + 1}), retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff

