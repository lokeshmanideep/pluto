import os
import secrets
import string
from typing import Optional
from datetime import datetime
import re


def generate_secure_filename(original_filename: str) -> str:
    """Generate a secure filename with timestamp and random suffix."""
    # Get file extension
    name, ext = os.path.splitext(original_filename)
    
    # Clean the original name
    clean_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', name)
    clean_name = clean_name[:50]  # Limit length
    
    # Generate timestamp and random suffix
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    
    return f"{clean_name}_{timestamp}_{random_suffix}{ext}"


def validate_file_size(file_size: int, max_size_mb: int = 10) -> bool:
    """Validate file size in MB."""
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_size_bytes


def get_file_extension(filename: str) -> str:
    """Get file extension in lowercase."""
    return os.path.splitext(filename)[1].lower()


def is_allowed_file_type(filename: str, allowed_extensions: list = None) -> bool:
    """Check if file type is allowed."""
    if allowed_extensions is None:
        allowed_extensions = ['.docx', '.doc', '.txt', '.pdf']
    
    extension = get_file_extension(filename)
    return extension in allowed_extensions


def create_upload_directory(directory: str) -> bool:
    """Create upload directory if it doesn't exist."""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception:
        return False


def delete_file_safely(file_path: str) -> bool:
    """Safely delete a file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        return False


def get_file_size(file_path: str) -> Optional[int]:
    """Get file size in bytes."""
    try:
        return os.path.getsize(file_path)
    except Exception:
        return None


def clean_text_content(text: str) -> str:
    """Clean and normalize text content."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    return text.strip()


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_text_preview(text: str, max_length: int = 500) -> str:
    """Extract a preview of text content."""
    cleaned_text = clean_text_content(text)
    return truncate_text(cleaned_text, max_length)


def parse_percentage(value: str) -> Optional[float]:
    """Parse percentage value from string."""
    try:
        # Remove % symbol and whitespace
        cleaned = value.strip().replace('%', '')
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def parse_currency(value: str) -> Optional[float]:
    """Parse currency value from string."""
    try:
        # Remove currency symbols and commas
        cleaned = re.sub(r'[$,€£¥]', '', value.strip())
        return float(cleaned)
    except (ValueError, AttributeError):
        return None


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def is_valid_session_id(session_id: str) -> bool:
    """Validate session ID format."""
    if not session_id:
        return False
    
    # Check length (UUID is 36 characters with hyphens)
    if len(session_id) not in [32, 36]:
        return False
    
    # Check for valid characters (alphanumeric and hyphens)
    pattern = r'^[a-fA-F0-9\-]+$'
    return bool(re.match(pattern, session_id))


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing dangerous characters."""
    # Remove path separators and other dangerous characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    
    return name + ext


def get_content_type(filename: str) -> str:
    """Get MIME content type for file."""
    extension = get_file_extension(filename)
    
    content_types = {
        '.txt': 'text/plain',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.pdf': 'application/pdf',
        '.html': 'text/html',
        '.htm': 'text/html'
    }
    
    return content_types.get(extension, 'application/octet-stream')


def calculate_progress_percentage(filled: int, total: int) -> float:
    """Calculate progress percentage."""
    if total == 0:
        return 0.0
    return round((filled / total) * 100, 2)


def estimate_completion_time(filled: int, total: int, avg_time_per_field: float = 30.0) -> Optional[float]:
    """Estimate completion time in seconds based on remaining fields."""
    if total == 0 or filled >= total:
        return 0.0
    
    remaining = total - filled
    return remaining * avg_time_per_field


def is_placeholder_text(text: str) -> bool:
    """Check if text looks like a placeholder."""
    # Common placeholder patterns
    patterns = [
        r'^\[.*\]$',          # [PLACEHOLDER]
        r'^\{.*\}$',          # {PLACEHOLDER}
        r'^\{\{.*\}\}$',      # {{PLACEHOLDER}}
        r'^<.*>$',            # <PLACEHOLDER>
        r'^_{2,}$',           # Multiple underscores
        r'^\.{3,}$',          # Multiple dots
        r'^\$\{.*\}$',        # ${PLACEHOLDER}
    ]
    
    return any(re.match(pattern, text.strip()) for pattern in patterns)


def normalize_placeholder_text(text: str) -> str:
    """Normalize placeholder text for comparison."""
    # Remove brackets and normalize whitespace
    normalized = re.sub(r'[\[\]{}()<>]', '', text)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip().lower()