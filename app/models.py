from pydantic import BaseModel
from typing import Optional, List

class User(BaseModel):
    sub: str
    username: str
    role: str
    department: Optional[str] = None

class LoginRequest(BaseModel):
    username: str

class Document(BaseModel):
    id: str
    title: str
    content: str
    sensitive: bool = False

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    results: List[Document]


class UserSettings(BaseModel):
    city: str
    timezone: Optional[str] = None
    theme: Optional[str] = None


class TokenUpsertRequest(BaseModel):
    provider: str
    token: str


class ContextualActionResponse(BaseModel):
    message: str
    profile: User
    settings: UserSettings
    weather: dict
