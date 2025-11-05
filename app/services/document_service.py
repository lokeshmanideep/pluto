from typing import List, Dict, Any,Tuple
import re
import os
import tempfile
from langchain_openai import OpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import BaseOutputParser
import json
from ..schemas.document import PlaceholderType
from docx import Document
from docxtpl import DocxTemplate
import time


class PlaceholderExtractionParser(BaseOutputParser):
    """Custom parser for extracting structured placeholder information."""
    
    def parse(self, text: str) -> List[Dict[str, Any]]:
        """Parse the LLM output into structured placeholder data."""
        try:
            # Try to parse as JSON first
            if text.strip().startswith('[') or text.strip().startswith('{'):
                return json.loads(text)
            
            # Fallback: parse manually
            placeholders = []
            lines = text.split('\n')
            current_placeholder = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_placeholder:
                        placeholders.append(current_placeholder)
                        current_placeholder = {}
                    continue
                
                if line.startswith('Placeholder:'):
                    current_placeholder['text'] = line.replace('Placeholder:', '').strip()
                elif line.startswith('Type:'):
                    current_placeholder['type'] = line.replace('Type:', '').strip().lower()
                elif line.startswith('Description:'):
                    current_placeholder['description'] = line.replace('Description:', '').strip()
                elif line.startswith('Context:'):
                    current_placeholder['context'] = line.replace('Context:', '').strip()
            
            if current_placeholder:
                placeholders.append(current_placeholder)
            
            return placeholders
        except Exception as e:
            # If parsing fails, return empty list
            return []


class DocumentProcessingService:
    """Service for processing legal documents and extracting placeholders using docxtpl."""
    
    def __init__(self):
        self.llm = OpenAI(
            temperature=0.1,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.placeholder_extraction_prompt = PromptTemplate(
            input_variables=["document_text"],
            template="""
You are an expert legal document analyzer. Analyze the following legal document text and identify ALL placeholders, variables, and fields that need to be filled in.

Document Text:
{document_text}

Please identify and extract all placeholders in the document. Look for:
1. Text in brackets like [PLACEHOLDER], {{PLACEHOLDER}}, or (PLACEHOLDER)
2. Underscores or blank spaces that indicate missing information
3. Generic terms that should be replaced with specific information
4. Template variables or merge fields

For each placeholder found, provide:
- The exact placeholder text as it appears
- The type of information needed (name, date, amount, address, etc.)
- A description of what should fill this placeholder
- The surrounding context (a few words before and after)

Return the results as a JSON array with this format:
[
  {{
    "text": "exact placeholder text",
    "type": "placeholder_type",
    "description": "what information is needed",
    "context": "surrounding text context"
  }}
]

Focus on being comprehensive - it's better to identify too many potential placeholders than to miss important ones.
"""
        )
        
        self.placeholder_chain = self.placeholder_extraction_prompt | self.llm | PlaceholderExtractionParser()
    

    def convert_custom_placeholders_to_jinja(self, docx_path: str):
        """
        Converts [Name] → {{ Name }} and ______ → {{ blank_1 }} using python-docx.
        Fixes split runs first so placeholders spanning runs are detected properly.
        Returns: (temp_docx_path, extracted_placeholders)
        """
        temp_dir = tempfile.mkdtemp()
        temp_docx = os.path.join(temp_dir, "converted_template.docx")

        document = Document(docx_path)
        placeholder_counter = 1
        extracted_placeholders = []

        # Regex patterns
        bracket_pattern = re.compile(r"\[([A-Za-z0-9 \-]+)\]")
        blank_pattern = re.compile(r"\[_{3,}\]")

        for para in document.paragraphs:
            # Merge runs' text into one combined string
            full_text = "".join(run.text for run in para.runs)
            updated_text = full_text

            # ---- 2️⃣ Replace [Something] → {{ Something }} ----
            def bracket_replacer(match):
                placeholder_text = match.group(1).strip()
                jinja_name = placeholder_text.replace(' ', '_').replace('-', '_')
                context = full_text[max(0, match.start()-30):min(len(full_text), match.end()+30)]
                extracted_placeholders.append({
                    'original': f"[{placeholder_text}]",
                    'jinja_name': jinja_name,
                    'type': self._infer_placeholder_type(placeholder_text, context),
                    'context': context,
                    'description': f"Fill in the value for {placeholder_text}"
                })
                return f"{{{{ {jinja_name} }}}}"

            updated_text = bracket_pattern.sub(bracket_replacer, updated_text)

            def blank_replacer(match):
                nonlocal placeholder_counter
                jinja_name = f"blank_{placeholder_counter}"
                context = full_text[max(0, match.start()-30):min(len(full_text), match.end()+30)]
                extracted_placeholders.append({
                    'original': match.group(0),
                    'jinja_name': jinja_name,
                    'type': "text",
                    'context': context,
                    'description': f"Fill in the blank field #{placeholder_counter}"
                })
                tag = f"{{{{ {jinja_name} }}}}"
                placeholder_counter += 1
                return tag

            updated_text = blank_pattern.sub(blank_replacer, updated_text)

            # ---- 4️⃣ Assign updated text back to runs ----
            # We assign the full paragraph text to the first run, and clear others.
            if para.runs:
                para.runs[0].text = updated_text
                for r in para.runs[1:]:
                    r.text = ""

        # Save the updated docx
        document.save(temp_docx)
        return temp_docx, extracted_placeholders
    
    
    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text content from a DOCX file."""
        try:
            doc = Document(file_path)
            text_content = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text.strip())
            
            return '\n'.join(text_content)
        except Exception as e:
            raise Exception(f"Error extracting text from DOCX: {str(e)}")

    
    def _infer_placeholder_type(self, placeholder_text: str, context: str) -> str:
        """Infer the type of placeholder based on text and context."""
        text_lower = placeholder_text.lower()
        context_lower = context.lower()
        
        # Date patterns
        if any(word in text_lower for word in ['date', 'day', 'month', 'year', 'time']):
            return PlaceholderType.DATE.value
        
        # Name patterns
        if any(word in text_lower for word in ['name', 'client', 'party', 'person', 'individual']):
            return PlaceholderType.NAME.value
        
        # Amount/Money patterns
        if any(word in text_lower for word in ['amount', 'price', 'cost', 'fee', 'payment', 'money', 'dollar', '$']):
            return PlaceholderType.AMOUNT.value
        
        # Email patterns
        if any(word in text_lower for word in ['email', 'mail', '@']):
            return PlaceholderType.EMAIL.value
        
        # Address patterns
        if any(word in text_lower for word in ['address', 'street', 'city', 'state', 'zip', 'location']):
            return PlaceholderType.ADDRESS.value
        
        # Phone patterns
        if any(word in text_lower for word in ['phone', 'telephone', 'mobile', 'cell']):
            return PlaceholderType.PHONE.value
        
        # Number patterns
        if any(word in text_lower for word in ['number', 'count', 'quantity', '#']):
            return PlaceholderType.NUMBER.value
        
        # Percentage patterns
        if any(word in text_lower for word in ['percent', '%', 'rate', 'ratio']):
            return PlaceholderType.PERCENTAGE.value
        
        # Boolean patterns
        if any(word in text_lower for word in ['yes', 'no', 'true', 'false', 'check', 'select']):
            return PlaceholderType.BOOLEAN.value
        
        return PlaceholderType.TEXT.value
    
    async def process_document(self, file_path: str) -> Tuple[str, List[Dict[str, Any]], str]:
        """Process a document and extract placeholders using docxtpl conversion."""
        try:
            # Extract text from document for analysis
            if file_path.lower().endswith('.docx'):
                text_content = self.extract_text_from_docx(file_path)
                
                # Convert document to Jinja2 template and extract placeholders
                converted_template_path, all_placeholders = self.convert_custom_placeholders_to_jinja(file_path)
                return text_content, all_placeholders, converted_template_path
            else:
                raise Exception("Unsupported file format. Only .docx files are supported.")
            
        except Exception as e:
            raise Exception(f"Error processing document: {str(e)}")
    
    def generate_completed_document(self, template_path: str, placeholders: List[Dict[str, Any]], output_path: str = None) -> str:
        """Generate the completed document with all placeholders filled using docxtpl."""
        try:
            if not template_path or not os.path.exists(template_path):
                raise Exception("Template path not found or invalid")
            
            # Prepare context for docxtpl
            context = {}
            
            for placeholder in placeholders:
                if placeholder.get('filled_value') and placeholder.get('jinja_name'):
                    # Use jinja_name if available (from conversion)
                    context[placeholder['jinja_name']] = placeholder['filled_value']
                elif placeholder.get('filled_value') and placeholder.get('text'):
                    # Convert placeholder text to valid jinja variable name
                    jinja_name = self._text_to_jinja_name(placeholder['text'])
                    context[jinja_name] = placeholder['filled_value']
            
            # Load template and render
            doc = DocxTemplate(template_path)
            doc.render(context)
            
            # Generate output path if not provided
            if not output_path:
                timestamp = int(time.time())
                output_path = f"completed_document_{timestamp}.docx"
            
            # Save completed document
            doc.save(output_path)
            
            return output_path
            
        except Exception as e:
            raise Exception(f"Error generating completed document: {str(e)}")
    
    def _text_to_jinja_name(self, text: str) -> str:
        """Convert placeholder text to valid Jinja2 variable name."""
        # Remove brackets and special characters
        clean_text = re.sub(r'[\[\]{}()<>]', '', text)
        # Replace spaces and special chars with underscores
        clean_text = re.sub(r'[^a-zA-Z0-9_]', '_', clean_text)
        # Remove multiple underscores
        clean_text = re.sub(r'_+', '_', clean_text)
        # Remove leading/trailing underscores
        clean_text = clean_text.strip('_')
        
        return clean_text if clean_text else 'placeholder'
    
    
    async def generate_completed_document(self, template_path: str, context: Dict[str, str], document_id: int) -> str:
        """Generate a completed document using docxtpl with the provided context."""
        try:
            from docxtpl import DocxTemplate
            
            # Load the template
            doc = DocxTemplate(template_path)
            
            # Render the template with context
            doc.render(context)
            
            # Create output directory if it doesn't exist
            output_dir = "completed_documents"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate output file path
            output_path = os.path.join(output_dir, f"completed_document_{document_id}.docx")
            
            # Save the completed document
            doc.save(output_path)
            
            return output_path
            
        except Exception as e:
            raise Exception(f"Error generating completed document: {str(e)}")