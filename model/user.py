from pydantic import BaseModel, Field, field_validator, conint
from typing import Optional, List, Dict
from datetime import datetime

class CreatedDate(BaseModel):
    """Base class for models that require a creation timestamp."""
    created_date: datetime = Field(default_factory=datetime.now)

class QueueItem(CreatedDate):
    file_id: str
    file_name: str
    mimetype: str

    @field_validator('mimetype')
    def validate_mimetype(cls, value):
        if not isinstance(value, str) or '/' not in value:
            raise ValueError('Invalid MIME type format. Expected format: type/subtype')
        return value

class Queue(BaseModel):
    files: List[QueueItem] = []

    def add_file(self, file_id: str, file_name: str, mimetype: str):
        """Ajoute un fichier à la queue."""
        self.files.append(QueueItem(file_id=file_id, file_name=file_name, mimetype=mimetype))

    def remove_file(self, file_id: str):
        """Supprime un fichier de la queue par son ID."""
        self.files = [item for item in self.files if item.file_id != file_id]

class Metadata(CreatedDate):
    titre: Optional[str] = None
    artiste: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    date_modification: datetime = Field(default_factory=datetime.now)

    def update(self, **kwargs):
        """Met à jour les métadonnées avec les nouvelles valeurs."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.date_modification = datetime.now()

class UserType(CreatedDate):
    type_name: str
    points: int = Field(0, ge=0)
    abonnement: Optional[str] = None

    def add_points(self, points: int):
        """Ajoute des points à l'utilisateur."""
        self.points += points

    def remove_points(self, points: int):
        """Retire des points à l'utilisateur."""
        self.points = max(0, self.points - points)

class User(CreatedDate):
    id: int = Field(..., ge=1)
    name: str
    queue: Queue = Queue()
    metadata: Metadata = Metadata()
    type: UserType
    thumb: Optional[str] = None
    auto: Optional[str] = None
    caption: Optional[str] = None
    channel_dump: Optional[Dict[str, str]] = None
    pending_points: Optional[int] = None
    unique_code: Optional[str] = None
    referrer_id: Optional[int] = None

    def add_to_queue(self, file_id: str, file_name: str, mimetype: str):
        """Ajoute un fichier à la queue de l'utilisateur."""
        self.queue.add_file(file_id, file_name, mimetype)

    def clear_queue(self):
        """Vide la queue de l'utilisateur."""
        self.queue.files.clear()

    def update_metadata(self, **kwargs):
        """Met à jour les métadonnées de l'utilisateur."""
        self.metadata.update(**kwargs)

    def set_user_type(self, new_type: str, points: int = 0, abonnement: Optional[str] = None):
        """Change le type d'utilisateur."""
        self.type = UserType(type_name=new_type, points=points, abonnement=abonnement)

    def __repr__(self):
        return (f"User(id={self.id}, type={self.type.type_name}, "
                f"metadata={self.metadata.titre}, queue_size={len(self.queue.files)})")