from typing import Dict, Any, Optional, Tuple, List
import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from ..models.document import Document, Placeholder, Conversation
from ..schemas.document import ConversationStatus, PlaceholderType


class DatabaseChatMessageHistory(BaseChatMessageHistory):
    
    def __init__(self, conversation: Conversation, db: Session):
        self.conversation = conversation
        self.db = db
        self._messages: List[BaseMessage] = []
        self._load_messages()
    
    def _load_messages(self):
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


@tool
def fill_placeholder_tool(placeholder_text: str, extracted_value: str, reasoning: str) -> str:
    """
    Call this function when you have successfully gathered complete information for a placeholder 
    and are ready to fill it with a confirmed value.
    
    Args:
        placeholder_text: The text of the placeholder being filled
        extracted_value: The clean, validated value to fill the placeholder with
        reasoning: Brief explanation of why this value is complete and correct
    
    Returns:
        Confirmation that the placeholder will be filled
    """
    return f"FILL_PLACEHOLDER:{placeholder_text}|{extracted_value}|{reasoning}"


@tool
def request_more_info_tool(placeholder_text: str, question: str, examples: str = "") -> str:
    """
    Call this function when you need more information or clarification from the user 
    before filling a placeholder.
    
    Args:
        placeholder_text: The text of the placeholder being discussed
        question: The specific question or request for clarification
        examples: Optional examples to help the user understand what's needed
    
    Returns:
        Indication that more information is needed
    """
    return f"REQUEST_INFO:{placeholder_text}|{question}|{examples}"


@tool
def complete_document_tool(message: str) -> str:
    """
    Call this function when all placeholders have been filled and the document is complete.
    
    Args:
        message: Congratulatory message for the user
    
    Returns:
        Confirmation that document is complete
    """
    return f"DOCUMENT_COMPLETE:{message}"


class ConversationService:
    def __init__(self):
        self.llm = ChatOpenAI(
            temperature=0.3,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o"
        )
        
        # Bind tools to the LLM
        self.tools = [
            fill_placeholder_tool,
            request_more_info_tool, 
            complete_document_tool
        ]
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Create a chat prompt template with message history
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an intelligent legal document assistant helping users fill in placeholders in their legal documents.

Document Context: {document_context}
Current Placeholder: {current_placeholder}
Progress: {progress_info}

Your role is to help users fill placeholders accurately through natural conversation. You have access to these tools:

1. fill_placeholder_tool: Use when you have complete, validated information for a placeholder
   - The system will automatically move to the next placeholder after filling
   - You don't need to manually handle transitions

2. request_more_info_tool: Use when you need clarification or more details from the user

3. complete_document_tool: Use when all placeholders are filled

Guidelines:
- Ask follow-up questions when responses are incomplete or unclear
- Validate information thoroughly before filling placeholders
- Use examples to help users understand requirements
- Only use fill_placeholder_tool when you're completely satisfied with the information
- Be professional, helpful, and accurate for legal documents
- If the placeholder is similar to a previously filled one, suggest reusing that value to the user

IMPORTANT: When you use fill_placeholder_tool, the system will automatically:
1. Fill the current placeholder
2. Move to the next unfilled placeholder
3. Generate an introduction for the next field
4. Combine both messages for a smooth user experience"""),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        
        # Create the basic chain with tools
        self.chain = self.prompt | self.llm_with_tools
    
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
    
    def _is_initial_message(self, message: str, conversation: Conversation) -> bool:
        """Check if this is the initial trigger message from the frontend."""
        if not conversation.conversation_history or not conversation.conversation_history.get("messages"):
            return True
        
        trigger_phrases = ["start", "begin", "help me fill", "initial", "trigger"]
        message_lower = message.lower().strip()
        return any(phrase in message_lower for phrase in trigger_phrases) or len(message_lower) < 5

    async def process_user_message(
        self, 
        db: Session, 
        conversation_id: int, 
        user_message: str
    ) -> Tuple[str, Optional[Placeholder], Dict[str, Any]]:
        """Process user message using function calling for better efficiency."""
        
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
            placeholder_context += f"\nType: {current_placeholder.placeholder_type}"
        
        # Calculate progress
        total_placeholders = db.query(Placeholder).filter(Placeholder.document_id == document.id).count()
        filled_placeholders = db.query(Placeholder).filter(
            Placeholder.document_id == document.id,
            Placeholder.is_filled == True
        ).count()
        
        progress_info = f"{filled_placeholders}/{total_placeholders} placeholders filled"
        
        # Check if initial message
        is_initial = self._is_initial_message(user_message, conversation)
        input_text = user_message
        if is_initial and current_placeholder:
            input_text = "I'm ready to help you fill out this document. Let's start with the first placeholder."
        
        try:
            # Single LLM call with function calling
            response = await chain_with_history.ainvoke(
                {
                    "input": input_text,
                    "current_placeholder": placeholder_context,
                    "document_context": document_context,
                    "progress_info": progress_info
                },
                config={"configurable": {"session_id": conversation.session_id}}
            )
            
            # Process the response and tool calls
            ai_response, current_placeholder = await self._process_tool_calls(
                response, current_placeholder, document, conversation, db
            )
            
        except Exception as e:
            ai_response = f"I'm having trouble processing your request. Could you please try again? Error: {str(e)}"
        
        # Recalculate progress after potential updates
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

    async def _process_tool_calls(
        self, 
        response, 
        current_placeholder: Optional[Placeholder], 
        document: Document,
        conversation: Conversation, 
        db: Session
    ) -> Tuple[str, Optional[Placeholder]]:
        """Process the LLM response and handle any tool calls."""
        
        # Extract text response
        if hasattr(response, 'content'):
            ai_response = response.content
        else:
            ai_response = str(response)
        
        # Check for tool calls
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                if tool_name == "fill_placeholder_tool":
                    # Fill the current placeholder
                    extracted_value = tool_args.get("extracted_value", "")
                    reasoning = tool_args.get("reasoning", "")
                    
                    if current_placeholder and extracted_value:
                        # Validate the value
                        is_valid, validation_message = self.validate_placeholder_value(current_placeholder, extracted_value)
                        
                        if is_valid:
                            # Fill the current placeholder
                            filled_placeholder_name = current_placeholder.placeholder_text
                            current_placeholder.filled_value = extracted_value
                            current_placeholder.is_filled = True
                            db.commit()
                            
                            # Create confirmation message
                            confirmation_msg = f"✅ Perfect! I've filled '{filled_placeholder_name}' with: {extracted_value}"
                            
                            # Move to next placeholder
                            next_placeholder = self.get_next_placeholder(db, document.id)
                            
                            if next_placeholder:
                                # Update conversation to point to next placeholder
                                conversation.current_placeholder_id = next_placeholder.id
                                current_placeholder = next_placeholder
                                db.commit()
                                
                                # Get the question for the next placeholder from LLM
                                next_question = await self._introduce_next_placeholder(
                                    conversation, next_placeholder, document, db
                                )
                                
                                # Combine both responses
                                ai_response = f"{confirmation_msg}\n\n{next_question}"
                                
                            else:
                                # No more placeholders - document is complete
                                conversation.current_placeholder_id = None
                                conversation.status = ConversationStatus.COMPLETED
                                current_placeholder = None
                                ai_response = f"{confirmation_msg}\n\n🎉 Congratulations! All placeholders have been filled. Your document is now complete and ready for download!"
                                db.commit()
                        else:
                            ai_response = f"❌ Validation failed: {validation_message}. Please provide a valid value."
                
                elif tool_name == "complete_document_tool":
                    # Document completion
                    completion_message = tool_args.get("message", "")
                    conversation.current_placeholder_id = None
                    conversation.status = ConversationStatus.COMPLETED
                    current_placeholder = None
                    ai_response = completion_message + "\n\n🎉 Your document is now complete and ready for download!"
                    db.commit()
                
                elif tool_name == "request_more_info_tool":
                    # Just use the response as-is, no database changes needed
                    question = tool_args.get("question", "")
                    examples = tool_args.get("examples", "")
                    if examples:
                        ai_response = f"{question}\n\nFor example: {examples}"
                    else:
                        ai_response = question
        
        return ai_response, current_placeholder
    
    async def _introduce_next_placeholder(
        self,
        conversation: Conversation,
        next_placeholder: Placeholder,
        document: Document,
        db: Session
    ) -> str:
        """Trigger LLM to introduce the next placeholder after filling the previous one."""
        
        # Create conversation chain with history
        chain_with_history = self.create_conversation_chain(conversation, db)
        
        # Prepare context for next placeholder
        document_context = f"Document: {document.original_filename}"
        if document.content_text:
            document_context += f"\n\nContent preview: {document.content_text[:500]}..."
        
        placeholder_context = f"Placeholder: {next_placeholder.placeholder_text}"
        if next_placeholder.description:
            placeholder_context += f"\nDescription: {next_placeholder.description}"
        if next_placeholder.context:
            placeholder_context += f"\nContext: {next_placeholder.context}"
        placeholder_context += f"\nType: {next_placeholder.placeholder_type}"
        
        # Calculate updated progress
        total_placeholders = db.query(Placeholder).filter(Placeholder.document_id == document.id).count()
        filled_placeholders = db.query(Placeholder).filter(
            Placeholder.document_id == document.id,
            Placeholder.is_filled == True
        ).count()
        
        progress_info = f"{filled_placeholders}/{total_placeholders} placeholders filled"
        
        try:
            # Trigger LLM to introduce next placeholder
            response = await chain_with_history.ainvoke(
                {
                    "input": "The previous placeholder has been filled successfully. Please introduce the next placeholder and ask for the required information.",
                    "current_placeholder": placeholder_context,
                    "document_context": document_context,
                    "progress_info": progress_info
                },
                config={"configurable": {"session_id": conversation.session_id}}
            )
            
            # Extract the introduction response
            if hasattr(response, 'content'):
                return response.content
            else:
                return str(response)
                
        except Exception as e:
            return f"Now I need information for: {next_placeholder.placeholder_text}. Could you please provide this information?"