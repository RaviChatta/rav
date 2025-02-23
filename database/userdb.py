from model import User, UserType
from config import settings
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import ValidationError
from bson import ObjectId

client = AsyncIOMotorClient(settings.DB_URL)
db = client[settings.DB_NAME]
users_collection = db["users"]

async def create_user(user: User) -> Optional[str]:
    """
    Crée un nouvel utilisateur dans la base de données.
    Retourne l'ID de l'utilisateur créé ou None en cas d'erreur.
    """
    try:
        user_dict = user.model_dump()
        result = await users_collection.insert_one(user_dict)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

async def read_user(user_id: int) -> Optional[User]:
    """
    Lit un utilisateur par son ID.
    Retourne un objet User ou None si l'utilisateur n'est pas trouvé.
    """
    try:
        user_data = await users_collection.find_one({"id": user_id})
        if user_data:
            return User(**user_data)
        return None
    except ValidationError as e:
        print(f"Validation error while reading user: {e}")
        return None
    except Exception as e:
        print(f"Error reading user: {e}")
        return None

async def get_user_by_code(unique_code: str) -> Optional[User]:
    """
    Lit un utilisateur par son code unique.
    Retourne un objet User ou None si l'utilisateur n'est pas trouvé.
    """
    try:
        user_data = await users_collection.find_one({"unique_code": unique_code})
        if user_data:
            return User(**user_data)
        return None
    except ValidationError as e:
        print(f"Validation error while reading user: {e}")
        return None
    except Exception as e:
        print(f"Error reading user: {e}")
        return None

async def update_user(user_id: int, update_data: dict) -> bool:
    """
    Met à jour un utilisateur par son ID.
    Retourne True si la mise à jour est réussie, False sinon.
    """
    try:
        result = await users_collection.update_one({"id": user_id}, {"$set": update_data})
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating user: {e}")
        return False

async def delete_user(user_id: int) -> bool:
    """
    Supprime un utilisateur par son ID.
    Retourne True si la suppression est réussie, False sinon.
    """
    try:
        result = await users_collection.delete_one({"id": user_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"Error deleting user: {e}")
        return False

async def find_users_by_type(user_type: str) -> List[User]:
    """
    Trouve tous les utilisateurs d'un type donné.
    Retourne une liste d'objets User.
    """
    try:
        users = []
        async for user_data in users_collection.find({"type.type_name": user_type}):
            users.append(User(**user_data))
        return users
    except ValidationError as e:
        print(f"Validation error while finding users: {e}")
        return []
    except Exception as e:
        print(f"Error finding users: {e}")
        return []

async def add_file_to_user_queue(user_id: int, file_id: str, file_name: str, mimetype: str) -> bool:
    """
    Ajoute un fichier à la queue d'un utilisateur.
    Retourne True si l'opération est réussie, False sinon.
    """
    try:
        user = await read_user(user_id)
        if user:
            user.add_to_queue(file_id, file_name, mimetype)
            await update_user(user_id, {"queue": user.queue.model_dump()})
            return True
        return False
    except Exception as e:
        print(f"Error adding file to user queue: {e}")
        return False

async def clear_user_queue(user_id: int) -> bool:
    """
    Vide la queue d'un utilisateur.
    Retourne True si l'opération est réussie, False sinon.
    """
    try:
        user = await read_user(user_id)
        if user:
            user.clear_queue()
            await update_user(user_id, {"queue": user.queue.model_dump()})
            return True
        return False
    except Exception as e:
        print(f"Error clearing user queue: {e}")
        return False

async def update_user_metadata(user_id: int, metadata: dict) -> bool:
    """
    Met à jour les métadonnées d'un utilisateur par son ID.
    Retourne True si la mise à jour est réussie, False sinon.
    """
    try:
        update_data = {"metadata": metadata.model_dump()}
        result = await users_collection.update_one({"id": user_id}, {"$set": update_data})
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating user metadata: {e}")
        return False
    
async def create_new_user(user_id: int, username: str) -> User:
    """
    Crée un nouvel utilisateur avec des valeurs par défaut.
    """
    usertype = UserType(
        type_name="user",
        points=100,
        abonnement="free"
    )
    user = User(
        id=user_id,
        name=username,
        type=usertype 
    )
    await create_user(user)
    return user

async def get_all_users() -> List[User]:
    """
    Lit tous les utilisateurs de la base de données.
    Retourne une liste d'objets User.
    """
    try:
        users = []
        async for user_data in users_collection.find():
            users.append(User(**user_data))
        return users
    except ValidationError as e:
        print(f"Validation error while finding users: {e}")
        return []
    except Exception as e:
        print(f"Error finding users: {e}")
        return []
