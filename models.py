from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base  # Import Base model from database.py

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    transcriptions = relationship("Transcription", back_populates="user", cascade="all, delete-orphan")

class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    transcription_text = Column(String, nullable=True)
    summary_text = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)  # Store the upload time
    
     # ✅ Ensure this relationship exists
    user = relationship("User", back_populates="transcriptions")