from sqlalchemy.orm import Session
from typing import List, Optional
from ..models.document import Document, Placeholder, Conversation, ConversationMessage
from ..schemas.document import (
    DocumentCreate, DocumentUpdate, PlaceholderCreate, PlaceholderUpdate,
    ConversationCreate, ConversationUpdate, ConversationMessageCreate
)


class DocumentCRUD:
    @staticmethod
    def create(db: Session, document: DocumentCreate, filename: str, file_path: str) -> Document:
        """Create a new document."""
        db_document = Document(
            filename=filename,
            original_filename=document.original_filename,
            file_path=file_path,
            status="uploaded"
        )
        db.add(db_document)
        db.commit()
        db.refresh(db_document)
        return db_document
    
    @staticmethod
    def get(db: Session, document_id: int) -> Optional[Document]:
        """Get a document by ID."""
        return db.query(Document).filter(Document.id == document_id).first()
    
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[Document]:
        """Get all documents with pagination."""
        return db.query(Document).offset(skip).limit(limit).all()
    
    @staticmethod
    def update(db: Session, document_id: int, document_update: DocumentUpdate) -> Optional[Document]:
        """Update a document."""
        db_document = db.query(Document).filter(Document.id == document_id).first()
        if db_document:
            update_data = document_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_document, field, value)
            db.commit()
            db.refresh(db_document)
        return db_document
    
    @staticmethod
    def delete(db: Session, document_id: int) -> bool:
        """Delete a document."""
        db_document = db.query(Document).filter(Document.id == document_id).first()
        if db_document:
            db.delete(db_document)
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_by_status(db: Session, status: str) -> List[Document]:
        """Get documents by status."""
        return db.query(Document).filter(Document.status == status).all()


class PlaceholderCRUD:
    @staticmethod
    def create(db: Session, placeholder: PlaceholderCreate) -> Placeholder:
        """Create a new placeholder."""
        db_placeholder = Placeholder(**placeholder.dict())
        db.add(db_placeholder)
        db.commit()
        db.refresh(db_placeholder)
        return db_placeholder
    
    @staticmethod
    def create_bulk(db: Session, placeholders: List[PlaceholderCreate]) -> List[Placeholder]:
        """Create multiple placeholders."""
        db_placeholders = [Placeholder(**placeholder.dict()) for placeholder in placeholders]
        db.add_all(db_placeholders)
        db.commit()
        for placeholder in db_placeholders:
            db.refresh(placeholder)
        return db_placeholders
    
    @staticmethod
    def get(db: Session, placeholder_id: int) -> Optional[Placeholder]:
        """Get a placeholder by ID."""
        return db.query(Placeholder).filter(Placeholder.id == placeholder_id).first()
    
    @staticmethod
    def get_by_document(db: Session, document_id: int) -> List[Placeholder]:
        """Get all placeholders for a document."""
        return db.query(Placeholder).filter(Placeholder.document_id == document_id).all()
    
    @staticmethod
    def get_unfilled_by_document(db: Session, document_id: int) -> List[Placeholder]:
        """Get unfilled placeholders for a document."""
        return db.query(Placeholder).filter(
            Placeholder.document_id == document_id,
            Placeholder.is_filled == False
        ).all()
    
    @staticmethod
    def update(db: Session, placeholder_id: int, placeholder_update: PlaceholderUpdate) -> Optional[Placeholder]:
        """Update a placeholder."""
        db_placeholder = db.query(Placeholder).filter(Placeholder.id == placeholder_id).first()
        if db_placeholder:
            update_data = placeholder_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_placeholder, field, value)
            db.commit()
            db.refresh(db_placeholder)
        return db_placeholder
    
    @staticmethod
    def fill_placeholder(db: Session, placeholder_id: int, value: str) -> Optional[Placeholder]:
        """Fill a placeholder with a value."""
        db_placeholder = db.query(Placeholder).filter(Placeholder.id == placeholder_id).first()
        if db_placeholder:
            db_placeholder.filled_value = value
            db_placeholder.is_filled = True
            db.commit()
            db.refresh(db_placeholder)
        return db_placeholder
    
    @staticmethod
    def delete(db: Session, placeholder_id: int) -> bool:
        """Delete a placeholder."""
        db_placeholder = db.query(Placeholder).filter(Placeholder.id == placeholder_id).first()
        if db_placeholder:
            db.delete(db_placeholder)
            db.commit()
            return True
        return False


class ConversationCRUD:
    @staticmethod
    def create(db: Session, conversation: ConversationCreate) -> Conversation:
        """Create a new conversation."""
        db_conversation = Conversation(**conversation.dict())
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)
        return db_conversation
    
    @staticmethod
    def get(db: Session, conversation_id: int) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()
    
    @staticmethod
    def get_by_session(db: Session, session_id: str, document_id: int) -> Optional[Conversation]:
        """Get a conversation by session ID and document ID."""
        return db.query(Conversation).filter(
            Conversation.session_id == session_id,
            Conversation.document_id == document_id
        ).first()
    
    @staticmethod
    def get_by_document(db: Session, document_id: int) -> List[Conversation]:
        """Get all conversations for a document."""
        return db.query(Conversation).filter(Conversation.document_id == document_id).all()
    
    @staticmethod
    def update(db: Session, conversation_id: int, conversation_update: ConversationUpdate) -> Optional[Conversation]:
        """Update a conversation."""
        db_conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if db_conversation:
            update_data = conversation_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_conversation, field, value)
            db.commit()
            db.refresh(db_conversation)
        return db_conversation
    
    @staticmethod
    def delete(db: Session, conversation_id: int) -> bool:
        """Delete a conversation."""
        db_conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if db_conversation:
            db.delete(db_conversation)
            db.commit()
            return True
        return False


class ConversationMessageCRUD:
    @staticmethod
    def create(db: Session, message: ConversationMessageCreate) -> ConversationMessage:
        """Create a new conversation message."""
        db_message = ConversationMessage(**message.dict())
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        return db_message
    
    @staticmethod
    def get_by_conversation(db: Session, conversation_id: int) -> List[ConversationMessage]:
        """Get all messages for a conversation."""
        return db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).order_by(ConversationMessage.created_at).all()
    
    @staticmethod
    def delete_by_conversation(db: Session, conversation_id: int) -> bool:
        """Delete all messages for a conversation."""
        messages = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id
        ).all()
        for message in messages:
            db.delete(message)
        db.commit()
        return True