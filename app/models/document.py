from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    template_path = Column(String(500), nullable=True)  # Path to converted Jinja2 template
    content_text = Column(Text, nullable=True)
    template_text = Column(Text, nullable=True)
    status = Column(String(50), default="uploaded")  # uploaded, processed, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, nullable=True)  # For future user management
    
    # Relationships
    placeholders = relationship("Placeholder", back_populates="document", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="document", cascade="all, delete-orphan")


class Placeholder(Base):
    __tablename__ = "placeholders"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    placeholder_text = Column(String(500), nullable=False)
    jinja_name = Column(String(500), nullable=True)  # Jinja2 variable name for docxtpl
    placeholder_type = Column(String(100), nullable=True)  # name, date, amount, etc.
    description = Column(Text, nullable=True)
    filled_value = Column(Text, nullable=True)
    is_filled = Column(Boolean, default=False)
    position_start = Column(Integer, nullable=True)
    position_end = Column(Integer, nullable=True)
    context = Column(Text, nullable=True)  # Surrounding text for better understanding
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="placeholders")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    session_id = Column(String(100), nullable=False)
    conversation_history = Column(JSON, nullable=True)  # Store conversation memory
    current_placeholder_id = Column(Integer, ForeignKey("placeholders.id"), nullable=True)
    status = Column(String(50), default="active")  # active, completed, paused
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="conversations")
    current_placeholder = relationship("Placeholder")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    message_type = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    placeholder_id = Column(Integer, ForeignKey("placeholders.id"), nullable=True)
    message_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    conversation = relationship("Conversation")
    placeholder = relationship("Placeholder")