from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    COMPLETED = "completed"
    ERROR = "error"


class PlaceholderType(str, Enum):
    TEXT = "text"
    DATE = "date"
    NUMBER = "number"
    EMAIL = "email"
    NAME = "name"
    ADDRESS = "address"
    PHONE = "phone"
    AMOUNT = "amount"
    PERCENTAGE = "percentage"
    BOOLEAN = "boolean"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# Placeholder schemas
class PlaceholderBase(BaseModel):
    placeholder_text: str
    jinja_name: Optional[str] = None
    placeholder_type: Optional[PlaceholderType] = None
    description: Optional[str] = None
    context: Optional[str] = None


class PlaceholderCreate(PlaceholderBase):
    document_id: int
    position_start: Optional[int] = None
    position_end: Optional[int] = None


class PlaceholderUpdate(BaseModel):
    filled_value: Optional[str] = None
    is_filled: Optional[bool] = None
    placeholder_type: Optional[PlaceholderType] = None
    description: Optional[str] = None


class PlaceholderResponse(PlaceholderBase):
    id: int
    document_id: int
    filled_value: Optional[str] = None
    is_filled: bool = False
    position_start: Optional[int] = None
    position_end: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Document schemas
class DocumentBase(BaseModel):
    original_filename: str


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    status: Optional[DocumentStatus] = None
    content_text: Optional[str] = None
    template_text: Optional[str] = None
    template_path: Optional[str] = None


class DocumentResponse(DocumentBase):
    id: int
    filename: str
    file_path: str
    template_path: Optional[str] = None
    content_text: Optional[str] = None
    template_text: Optional[str] = None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    user_id: Optional[int] = None
    placeholders: List[PlaceholderResponse] = []

    class Config:
        from_attributes = True


class DocumentSummary(BaseModel):
    id: int
    original_filename: str
    status: DocumentStatus
    created_at: datetime
    placeholder_count: int
    filled_count: int

    class Config:
        from_attributes = True


# Conversation schemas
class ConversationMessageBase(BaseModel):
    message_type: MessageType
    content: str
    message_metadata: Optional[Dict[str, Any]] = None


class ConversationMessageCreate(ConversationMessageBase):
    conversation_id: int
    placeholder_id: Optional[int] = None


class ConversationMessageResponse(ConversationMessageBase):
    id: int
    conversation_id: int
    placeholder_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationBase(BaseModel):
    session_id: str


class ConversationCreate(ConversationBase):
    document_id: int


class ConversationUpdate(BaseModel):
    conversation_history: Optional[Dict[str, Any]] = None
    current_placeholder_id: Optional[int] = None
    status: Optional[ConversationStatus] = None


class ConversationResponse(ConversationBase):
    id: int
    document_id: int
    conversation_history: Optional[Dict[str, Any]] = None
    current_placeholder_id: Optional[int] = None
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Chat schemas
class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: int
    session_id: str
    current_placeholder: Optional[PlaceholderResponse] = None
    progress: Dict[str, Any]
    is_complete: bool = False


# Document processing schemas
class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    message: str


class DocumentProcessingResponse(BaseModel):
    document: DocumentResponse
    placeholders_found: int
    message: str


class DocumentCompletionResponse(BaseModel):
    document: DocumentResponse
    completed_content: str
    download_url: str