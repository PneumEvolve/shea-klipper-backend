from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))  # ✅ Ensure ForeignKey matches
    filename = Column(String, index=True)
    transcription_text = Column(Text)
    summary_text = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    
     # ✅ Ensure this relationship exists
    user = relationship("User", back_populates="transcriptions")