# Legal Document Processing API

A FastAPI-based backend for processing legal documents and filling placeholders through conversational AI.

## Features

- **Document Upload**: Upload legal documents in various formats (.docx, .doc, .txt)
- **Intelligent Placeholder Detection**: Uses LangChain to identify and extract placeholders from documents
- **Conversational Filling**: Interactive chat interface to fill placeholders with AI assistance
- **Document Completion**: Generate completed documents with all placeholders filled
- **Progress Tracking**: Monitor completion progress and conversation history

## Technology Stack

- **FastAPI**: Modern, fast web framework for building APIs
- **LangChain**: For AI-powered document processing and conversational interface
- **SQLAlchemy**: Database ORM for data persistence
- **Pydantic**: Data validation and serialization
- **Python-docx**: For processing Word documents

## Project Structure

```
app/
├── __init__.py
├── main.py                 # FastAPI application entry point
├── database.py            # Database configuration
├── dependencies.py        # FastAPI dependencies
├── models/               # SQLAlchemy database models
│   ├── __init__.py
│   ├── document.py       # Document, Placeholder, Conversation models
│   ├── item.py
│   └── user.py
├── schemas/              # Pydantic schemas (DTOs)
│   ├── __init__.py
│   ├── document.py       # Document-related schemas
│   ├── item.py
│   └── user.py
├── crud/                 # Database operations
│   ├── __init__.py
│   ├── document.py       # Document CRUD operations
│   ├── item.py
│   └── user.py
├── routers/              # FastAPI route handlers
│   ├── __init__.py
│   ├── documents.py      # Document processing endpoints
│   ├── items.py
│   └── users.py
├── services/             # Business logic services
│   ├── __init__.py
│   ├── document_service.py     # Document processing with LangChain
│   └── conversation_service.py # Conversational AI service
├── utils/                # Utility functions
│   ├── __init__.py
│   ├── authentication.py
│   ├── validation.py
│   └── file_utils.py     # File handling utilities
└── external_services/    # External service integrations
    ├── __init__.py
    ├── email.py
    └── notification.py
```

## Setup and Installation

1. **Clone the repository**

   ```bash
   git clone <repository-url>
   cd pluto
   ```

2. **Create virtual environment**

   ```bash
   python -m venv env
   source env/bin/activate  # On Windows: env\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env file with your configuration
   ```

5. **Set up OpenAI API key**

   - Get an API key from [OpenAI](https://platform.openai.com/)
   - Add it to your `.env` file: `OPENAI_API_KEY=your_key_here`

6. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

The API will be available at `http://localhost:8000`

## API Endpoints

### Document Management

- `POST /api/v1/documents/upload` - Upload a document
- `GET /api/v1/documents/` - List all documents
- `GET /api/v1/documents/{document_id}` - Get document details
- `POST /api/v1/documents/{document_id}/process` - Process document to extract placeholders
- `DELETE /api/v1/documents/{document_id}` - Delete document

### Document Processing

- `GET /api/v1/documents/{document_id}/placeholders` - Get document placeholders
- `POST /api/v1/documents/{document_id}/chat` - Chat with AI to fill placeholders
- `POST /api/v1/documents/{document_id}/complete` - Generate completed document
- `GET /api/v1/documents/{document_id}/download` - Download completed document

## Usage Workflow

1. **Upload Document**

   ```bash
   curl -X POST "http://localhost:8000/api/v1/documents/upload" \
        -H "Content-Type: multipart/form-data" \
        -F "file=@your_document.docx"
   ```

2. **Process Document**

   ```bash
   curl -X POST "http://localhost:8000/api/v1/documents/1/process"
   ```

3. **Start Conversation**

   ```bash
   curl -X POST "http://localhost:8000/api/v1/documents/1/chat" \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello, I need help filling this document", "session_id": "unique-session-id"}'
   ```

4. **Complete Document**
   ```bash
   curl -X POST "http://localhost:8000/api/v1/documents/1/complete"
   ```

## API Documentation

Once the server is running, you can access:

- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## Configuration

### Environment Variables

| Variable         | Description                  | Default                     |
| ---------------- | ---------------------------- | --------------------------- |
| `DATABASE_URL`   | Database connection string   | `sqlite:///./legal_docs.db` |
| `OPENAI_API_KEY` | OpenAI API key for LangChain | Required                    |

### Database Support

The application supports multiple databases:

- **SQLite** (default): `sqlite:///./legal_docs.db`

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
black app/
flake8 app/
```

### Database Migrations

The application automatically creates database tables on startup. For production use, consider using Alembic for migrations.

## Features in Detail

### Document Processing

The system uses LangChain to intelligently identify placeholders in legal documents:

1. **Pattern Recognition**: Detects common placeholder patterns like `[NAME]`, `{DATE}`, `__________`
2. **Semantic Analysis**: Uses AI to identify fields that need to be filled based on context
3. **Type Inference**: Automatically determines the type of information needed (name, date, amount, etc.)

### Conversational Interface

The chat interface provides:

1. **Context-Aware Assistance**: AI understands the document context and current placeholder
2. **Validation**: Automatically validates input based on field types
3. **Progress Tracking**: Shows completion progress and guides users through the process
4. **Memory**: Maintains conversation history for better user experience

### Supported Document Types

- **DOCX**: Microsoft Word documents
- **DOC**: Legacy Word documents
- **TXT**: Plain text files
- **PDF**: (planned for future releases)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For support and questions, please open an issue in the repository.
