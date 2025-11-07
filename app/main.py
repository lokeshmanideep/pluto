from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from .routers import documents

# Import models to ensure they're registered with Base.metadata

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Legal Document Processing API",
    description="API for processing legal documents and filling placeholders through conversational AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# os.makedirs("uploads", exist_ok=True)

# app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(documents.router, prefix="/api/v1")

@app.get("/")
async def read_root():
    return {
        "message": "Legal Document Processing API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "active"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "legal-document-api"}

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}