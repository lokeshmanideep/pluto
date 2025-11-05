from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
import uuid
import shutil

from ..database import get_db
from ..schemas.document import (
    DocumentResponse, DocumentSummary, PlaceholderResponse, 
    ChatMessage, ChatResponse,
    DocumentUploadResponse, DocumentProcessingResponse, DocumentCompletionResponse
)
from ..crud.document import DocumentCRUD, PlaceholderCRUD
from ..services.document_service import DocumentProcessingService
from ..services.conversation_service import ConversationService

router = APIRouter(prefix="/documents", tags=["documents"])

# Initialize services
document_service = DocumentProcessingService()
conversation_service = ConversationService()

# Create upload directory if it doesn't exist
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a legal document for processing."""
    
    # Validate file type
    if not file.filename.lower().endswith(('.docx', '.doc', '.txt')):
        raise HTTPException(
            status_code=400, 
            detail="Only .docx, .doc, and .txt files are supported"
        )
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
    
    # Create document record
    try:
        from ..schemas.document import DocumentCreate
        document_create = DocumentCreate(original_filename=file.filename)
        document = DocumentCRUD.create(
            db=db, 
            document=document_create, 
            filename=unique_filename, 
            file_path=file_path
        )
        
        return DocumentUploadResponse(
            document=DocumentResponse.from_orm(document),
            message="Document uploaded successfully. Ready for processing."
        )
    except Exception as e:
        # Clean up file if database operation fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error creating document record: {str(e)}")


@router.post("/{document_id}/process", response_model=DocumentProcessingResponse)
async def process_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Process a document to extract placeholders."""
    
    # Get document
    document = DocumentCRUD.get(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "uploaded":
        raise HTTPException(status_code=400, detail="Document has already been processed")
    
    try:
        # Update status to processing
        from ..schemas.document import DocumentUpdate, DocumentStatus
        DocumentCRUD.update(db, document_id, DocumentUpdate(status=DocumentStatus.PROCESSING))
        
        # Process document
        text_content, placeholders, template_path = await document_service.process_document(document.file_path)
        
        # Update document with extracted content and template path
        DocumentCRUD.update(db, document_id, DocumentUpdate(
            content_text=text_content,
            template_text=text_content,
            template_path=template_path,
            status=DocumentStatus.PROCESSED
        ))
        
        # Create placeholder records
        from ..schemas.document import PlaceholderCreate
        placeholder_creates = [
            PlaceholderCreate(
                document_id=document_id,
                placeholder_text=p.get('text', p.get('original', '')),
                jinja_name=p.get('jinja_name'),
                placeholder_type=p.get('type'),
                description=p.get('description'),
                context=p.get('context'),
                position_start=p.get('position_start'),
                position_end=p.get('position_end')
            )
            for p in placeholders
        ]
        
        PlaceholderCRUD.create_bulk(db, placeholder_creates)
        
        # Get updated document with placeholders
        updated_document = DocumentCRUD.get(db, document_id)
        
        return DocumentProcessingResponse(
            document=DocumentResponse.from_orm(updated_document),
            placeholders_found=len(placeholders),
            message=f"Document processed successfully. Found {len(placeholders)} placeholders."
        )
        
    except Exception as e:
        # Update status to error
        DocumentCRUD.update(db, document_id, DocumentUpdate(status=DocumentStatus.ERROR))
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@router.get("/", response_model=List[DocumentSummary])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all documents with summary information."""
    
    documents = DocumentCRUD.get_all(db, skip=skip, limit=limit)
    
    summaries = []
    for document in documents:
        placeholder_count = len(document.placeholders)
        filled_count = sum(1 for p in document.placeholders if p.is_filled)
        
        summaries.append(DocumentSummary(
            id=document.id,
            original_filename=document.original_filename,
            status=document.status,
            created_at=document.created_at,
            placeholder_count=placeholder_count,
            filled_count=filled_count
        ))
    
    return summaries


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific document with all details."""
    
    document = DocumentCRUD.get(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse.from_orm(document)


@router.get("/{document_id}/placeholders", response_model=List[PlaceholderResponse])
async def get_document_placeholders(
    document_id: int,
    unfilled_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get placeholders for a document."""
    
    document = DocumentCRUD.get(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if unfilled_only:
        placeholders = PlaceholderCRUD.get_unfilled_by_document(db, document_id)
    else:
        placeholders = PlaceholderCRUD.get_by_document(db, document_id)
    
    return [PlaceholderResponse.from_orm(p) for p in placeholders]


@router.post("/{document_id}/chat", response_model=ChatResponse)
async def chat_with_document(
    document_id: int,
    chat_message: ChatMessage,
    db: Session = Depends(get_db)
):
    """Chat with the assistant to fill document placeholders."""
    
    # Get or create conversation
    session_id = chat_message.session_id or str(uuid.uuid4())
    
    conversation = conversation_service.get_or_create_conversation(
        db=db, 
        document_id=document_id, 
        session_id=session_id
    )
    
    try:
        # Process user message
        ai_response, current_placeholder, progress = await conversation_service.process_user_message(
            db=db,
            conversation_id=conversation.id,
            user_message=chat_message.message
        )
        
        return ChatResponse(
            response=ai_response,
            conversation_id=conversation.id,
            session_id=session_id,
            current_placeholder=PlaceholderResponse.from_orm(current_placeholder) if current_placeholder else None,
            progress=progress,
            is_complete=progress["filled"] == progress["total"] and progress["total"] > 0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat message: {str(e)}")


@router.post("/{document_id}/complete", response_model=DocumentCompletionResponse)
async def complete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Generate the completed document with all placeholders filled."""
    
    document = DocumentCRUD.get(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not document.template_path:
        raise HTTPException(status_code=400, detail="Document has not been processed yet")
    
    # Check if all placeholders are filled
    placeholders = PlaceholderCRUD.get_by_document(db, document_id)
    unfilled_placeholders = [p for p in placeholders if not p.is_filled]
    
    if unfilled_placeholders:
        raise HTTPException(
            status_code=400,
            detail=f"Document is not complete. {len(unfilled_placeholders)} placeholders still need to be filled."
        )
    
    try:
        # Prepare context data for template rendering
        context = {}
        for placeholder in placeholders:
            if placeholder.jinja_name and placeholder.filled_value:
                context[placeholder.jinja_name] = placeholder.filled_value
        
        # Generate completed document using docxtpl
        completed_file_path = await document_service.generate_completed_document(
            document.template_path,
            context,
            document_id
        )
        
        # Update document status
        from ..schemas.document import DocumentUpdate, DocumentStatus
        DocumentCRUD.update(db, document_id, DocumentUpdate(status=DocumentStatus.COMPLETED))
        
        # Generate download URL
        download_url = f"/documents/{document_id}/download"
        
        return DocumentCompletionResponse(
            document=DocumentResponse.from_orm(document),
            completed_content=f"Document completed and saved to {completed_file_path}",
            download_url=download_url
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error completing document: {str(e)}")


@router.get("/{document_id}/download")
async def download_completed_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Download the completed document."""
    
    document = DocumentCRUD.get(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status != "completed":
        raise HTTPException(status_code=400, detail="Document is not completed yet")
    
    # Look for the completed document file
    completed_file_path = f"completed_documents/completed_document_{document_id}.docx"
    
    if not os.path.exists(completed_file_path):
        raise HTTPException(status_code=404, detail="Completed document file not found")
    
    return FileResponse(
        path=completed_file_path,
        filename=f"completed_{document.original_filename}",
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Delete a document and its associated file."""
    
    document = DocumentCRUD.get(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    # Delete document record (cascades to placeholders and conversations)
    DocumentCRUD.delete(db, document_id)
    
    return {"message": "Document deleted successfully"}