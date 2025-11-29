"""
SQLAlchemy database models for Medical ChatBot
Defines the database schema for users, conversations, messages, and documents
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
import uuid


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


class User(Base):
    """
    User model - stores authenticated users who can chat and upload documents

    Each user can have multiple conversations and documents.
    Supports OAuth authentication (Google) via google_id field.
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    # OAuth fields for Google login
    google_id = Column(String, unique=True, nullable=True, index=True)

    # Account status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships - a user can have many conversations and documents
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class Conversation(Base):
    """
    Conversation model - represents a chat session between user and MediBot

    Each conversation belongs to one user and contains multiple messages.
    Automatically deleted when the user is deleted (cascade).
    """
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # Nullable for anonymous users
    title = Column(String, nullable=True)  # Optional conversation title

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id})>"


class Message(Base):
    """
    Message model - individual chat message in a conversation

    Stores both user questions and AI assistant responses.
    Role can be 'user' or 'assistant'.
    """
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)  # Message text

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role})>"


class Document(Base):
    """
    Document model - stores metadata for uploaded medical documents

    Actual file content is stored on disk and in Pinecone vector database.
    This table tracks file info, ownership, and Pinecone vector IDs.
    """
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # File information
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Path in uploads/ directory
    file_type = Column(String, nullable=False)  # .pdf, .txt, .docx
    file_size = Column(Integer, nullable=False)  # Size in bytes

    # Processing information
    status = Column(String, default="processing")  # processing, ready, failed
    chunks_count = Column(Integer, default=0)  # Number of text chunks created
    page_count = Column(Integer, nullable=True)  # For PDFs

    # Pinecone vector database info
    pinecone_ids = Column(Text, nullable=True)  # JSON array of vector IDs for deletion

    # Additional metadata
    tags = Column(Text, nullable=True)  # JSON array of tags
    custom_metadata = Column(Text, nullable=True)  # JSON object for extra data
    processing_time = Column(Float, nullable=True)  # Time taken to process (seconds)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="documents")

    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"
