from typing import Dict, Any, Optional, Tuple, List
import os
import re
from langchain_openai import OpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from sqlalchemy.orm import Session
from ..models.document import Document, Placeholder, Conversation
from ..schemas.document import ConversationStatus, PlaceholderType


class DatabaseChatMessageHistory(BaseChatMessageHistory):
    """Custom chat message history that stores messages in database."""
    
    def __init__(self, conversation: Conversation, db: Session):
        self.conversation = conversation
        self.db = db
        self._messages: List[BaseMessage] = []
        self._load_messages()
    
    def _load_messages(self):
        """Load messages from database."""
        if self.conversation.conversation_history:
            chat_history = self.conversation.conversation_history.get("messages", [])
            for message in chat_history:
                if message["type"] == "human":
                    self._messages.append(HumanMessage(content=message["content"]))
                elif message["type"] == "ai":
                    self._messages.append(AIMessage(content=message["content"]))
    
    @property
    def messages(self) -> List[BaseMessage]:
        """Return the list of messages."""
        return self._messages
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the store."""
        self._messages.append(message)
        self._save_to_database()
    
    def clear(self) -> None:
        """Clear all messages."""
        self._messages = []
        self._save_to_database()
    
    def _save_to_database(self):
        """Save messages to database."""
        messages = []
        for message in self._messages:
            if isinstance(message, HumanMessage):
                messages.append({"type": "human", "content": message.content})
            elif isinstance(message, AIMessage):
                messages.append({"type": "ai", "content": message.content})
        
        self.conversation.conversation_history = {"messages": messages}
        self.db.commit()


class ConversationService:
    def __init__(self):
        self.llm = OpenAI(
            temperature=0.3,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o-mini"
        )
        
        # Create a chat prompt template with message history
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intelligent legal document assistant helping users fill in placeholders in their legal documents.

Document Context: {document_context}
Current Placeholder: {current_placeholder}

Your role is to:
1. Help users understand what information is needed for each placeholder
2. Ask clarifying questions if the information provided is unclear or incomplete
3. Validate the information provided (format, completeness, etc.)
4. Guide users through the document completion process step by step
5. Be professional, helpful, and accurate

Guidelines:
- Ask one question at a time to avoid overwhelming the user
- Provide examples when helpful
- Validate information format (e.g., dates, phone numbers, emails)
- If unsure about legal implications, suggest consulting with a legal professional
- Keep responses concise but informative"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        # Create the basic chain
        self.chain = self.prompt | self.llm
    
    def create_conversation_chain(self, conversation: Conversation, db: Session):
        """Create a conversation chain with message history."""
        # Create custom message history
        def get_session_history(session_id: str) -> BaseChatMessageHistory:
            return DatabaseChatMessageHistory(conversation, db)
        
        # Create chain with message history
        return RunnableWithMessageHistory(
            self.chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="history",
        )
    
    def get_or_create_conversation(self, db: Session, document_id: int, session_id: str) -> Conversation:
        """Get existing conversation or create a new one."""
        conversation = db.query(Conversation).filter(
            Conversation.document_id == document_id,
            Conversation.session_id == session_id,
            Conversation.status == ConversationStatus.ACTIVE
        ).first()
        
        if not conversation:
            conversation = Conversation(
                document_id=document_id,
                session_id=session_id,
                status=ConversationStatus.ACTIVE,
                conversation_history={}
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        
        return conversation
    
    def get_next_placeholder(self, db: Session, document_id: int) -> Optional[Placeholder]:
        """Get the next unfilled placeholder."""
        return db.query(Placeholder).filter(
            Placeholder.document_id == document_id,
            Placeholder.is_filled == False
        ).first()
    
    def validate_placeholder_value(self, placeholder: Placeholder, value: str) -> Tuple[bool, str]:
        """Validate the value for a placeholder based on its type."""
        placeholder_type = placeholder.placeholder_type
        
        if placeholder_type == PlaceholderType.EMAIL:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                return False, "Please provide a valid email address"
        
        elif placeholder_type == PlaceholderType.PHONE:
            phone_pattern = r'^\+?[\d\s\-\(\)]{10,}$'
            if not re.match(phone_pattern, value):
                return False, "Please provide a valid phone number"
        
        elif placeholder_type == PlaceholderType.DATE:
            # Basic date validation - you might want to use a proper date parsing library
            date_patterns = [
                r'^\d{1,2}/\d{1,2}/\d{4}$',
                r'^\d{4}-\d{1,2}-\d{1,2}$',
                r'^\d{1,2}-\d{1,2}-\d{4}$'
            ]
            if not any(re.match(pattern, value) for pattern in date_patterns):
                return False, "Please provide a valid date (MM/DD/YYYY, YYYY-MM-DD, or MM-DD-YYYY)"
        
        elif placeholder_type == PlaceholderType.NUMBER:
            try:
                float(value.replace(',', ''))
            except ValueError:
                return False, "Please provide a valid number"
        
        elif placeholder_type == PlaceholderType.AMOUNT:
            # Remove currency symbols and validate as number
            cleaned_value = re.sub(r'[$,]', '', value)
            try:
                float(cleaned_value)
            except ValueError:
                return False, "Please provide a valid amount (e.g., $1,000.00 or 1000)"
        
        return True, ""
    
    async def process_user_message(
        self, 
        db: Session, 
        conversation_id: int, 
        user_message: str
    ) -> Tuple[str, Optional[Placeholder], Dict[str, Any]]:
        """Process user message and return AI response."""
        
        # Get conversation and document
        conversation = db.query(Conversation).get(conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
        
        document = db.query(Document).get(conversation.document_id)
        if not document:
            raise ValueError("Document not found")
        
        # Get current or next placeholder
        current_placeholder = None
        if conversation.current_placeholder_id:
            current_placeholder = db.query(Placeholder).get(conversation.current_placeholder_id)
        
        if not current_placeholder:
            current_placeholder = self.get_next_placeholder(db, document.id)
            if current_placeholder:
                conversation.current_placeholder_id = current_placeholder.id
                db.commit()
        
        # Create conversation chain with history
        chain_with_history = self.create_conversation_chain(conversation, db)
        
        # Prepare context
        document_context = f"Document: {document.original_filename}"
        if document.content_text:
            document_context += f"\n\nContent preview: {document.content_text[:500]}..."
        
        placeholder_context = ""
        if current_placeholder:
            placeholder_context = f"Placeholder: {current_placeholder.placeholder_text}"
            if current_placeholder.description:
                placeholder_context += f"\nDescription: {current_placeholder.description}"
            if current_placeholder.context:
                placeholder_context += f"\nContext: {current_placeholder.context}"
        
        # Try to extract value from user message
        extracted_value = None
        if current_placeholder:
            # Simple extraction - in a real app, you might use more sophisticated NLP
            extracted_value = user_message.strip()
            
            # Validate the extracted value
            is_valid, validation_message = self.validate_placeholder_value(current_placeholder, extracted_value)
            
            if is_valid and extracted_value:
                # Fill the placeholder
                current_placeholder.filled_value = extracted_value
                current_placeholder.is_filled = True
                db.commit()
                
                # Move to next placeholder
                next_placeholder = self.get_next_placeholder(db, document.id)
                if next_placeholder:
                    conversation.current_placeholder_id = next_placeholder.id
                    current_placeholder = next_placeholder
                else:
                    conversation.current_placeholder_id = None
                    conversation.status = ConversationStatus.COMPLETED
                
                db.commit()
        
        # Generate AI response using LCEL with message history
        try:
            response = await chain_with_history.ainvoke(
                {
                    "input": user_message,
                    "current_placeholder": placeholder_context,
                    "document_context": document_context
                },
                config={"configurable": {"session_id": conversation.session_id}}
            )
            
            # Extract the content from the response
            if hasattr(response, 'content'):
                ai_response = response.content
            else:
                ai_response = str(response)
                
        except Exception as e:
            ai_response = f"I'm having trouble processing your request. Could you please try again? Error: {str(e)}"
        
        # Calculate progress
        total_placeholders = db.query(Placeholder).filter(Placeholder.document_id == document.id).count()
        filled_placeholders = db.query(Placeholder).filter(
            Placeholder.document_id == document.id,
            Placeholder.is_filled == True
        ).count()
        
        progress = {
            "total": total_placeholders,
            "filled": filled_placeholders,
            "percentage": (filled_placeholders / total_placeholders * 100) if total_placeholders > 0 else 0
        }
        
        return ai_response, current_placeholder, progress