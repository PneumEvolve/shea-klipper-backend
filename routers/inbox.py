from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from models import InboxMessage, Conversation, ConversationUser, User
from database import get_db
from sqlalchemy.orm import Session
from typing import List

router = APIRouter()

class MessageInput(BaseModel):
    users: List[str]  # List of user IDs (or emails) to include in the conversation
    content: str      # The content of the message
    user_id: str      # ID of the user sending the message
    conversation_id: int  # The ID of the conversation


# Utility function to create System user if it doesn't exist
def create_system_user_if_not_exists(db: Session):
    system_user = db.query(User).filter(User.email == "system@domain.com").first()
    if not system_user:
        system_user = User(email="system@domain.com", name="System")
        db.add(system_user)
        db.commit()  # Commit the new system user to the database
        db.refresh(system_user)
    return system_user


@router.post("/inbox/start-conversation")
def start_conversation(data: MessageInput, db: Session = Depends(get_db)):
    # Ensure the real user exists by email
    user = db.query(User).filter(User.email == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User {data.user_id} not found")

    # Ensure the System user exists or create it
    system_user = create_system_user_if_not_exists(db)

    # Check if the conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == data.conversation_id).first()

    # If the conversation doesn't exist, create it
    if not conversation:
        conversation = Conversation(name="System")
        db.add(conversation)

    # Add the real user and System user to the conversation
    conversation_user = ConversationUser(user_id=user.id, conversation_id=conversation.id)
    conversation_user_system = ConversationUser(user_id=system_user.id, conversation_id=conversation.id)
    
    db.add(conversation_user)
    db.add(conversation_user_system)

    # Create and send a system-generated message
    system_message = InboxMessage(
        user_id=system_user.id,
        content="Welcome to your inbox! This is a system-generated message.",
        timestamp=datetime.utcnow(),
        conversation_id=conversation.id
    )

    # Create the user's message
    user_message = InboxMessage(
        user_id=user.id,
        content=data.content,
        timestamp=datetime.utcnow(),
        conversation_id=conversation.id
    )

    # Add all the objects and commit everything at once
    db.add(system_message)
    db.add(user_message)

    db.commit()  # Commit all changes in one go

    return {"status": "message_sent", "conversation_id": conversation.id, "message_id": user_message.id}


@router.get("/inbox/{user_id}")
def get_inbox(user_id: str, db: Session = Depends(get_db)):
    print(f"Fetching inbox for user: {user_id}")
    
    # Find the unique System conversation for the user
    system_conversation = db.query(Conversation).join(ConversationUser).filter(
        ConversationUser.user_id == user_id, Conversation.name == "System"
    ).first()

    if not system_conversation:
        print(f"No System conversation found for user {user_id}. Creating one.")
        
        # Create new System conversation specifically for this user
        conversation = Conversation(name="System")
        db.add(conversation)
        db.commit()  # Commit conversation creation
        db.refresh(conversation)  # Refresh to get conversation ID

        # Add the user to the System conversation
        user = db.query(User).filter(User.email == user_id).first()  # Get user by email
        if user:
            conversation_user = ConversationUser(user_id=user.id, conversation_id=conversation.id)
            db.add(conversation_user)
        db.commit()

        # Ensure the system user exists or create it if not
        system_user = db.query(User).filter(User.email == "system@domain.com").first()
        if not system_user:
            system_user = User(email="system@domain.com", name="System")
            db.add(system_user)
            db.commit()
            db.refresh(system_user)

        # Send system-generated message to the new System conversation
        system_message = InboxMessage(
            user_id=system_user.id,  # Use the system user ID (integer) here
            content="Welcome to your inbox! This is a system-generated message.",
            timestamp=datetime.utcnow(),
            conversation_id=conversation.id
        )
        db.add(system_message)
        db.commit()  # Commit system message

        # Re-fetch the conversation with messages
        system_conversation = db.query(Conversation).join(ConversationUser).filter(
            ConversationUser.user_id == user_id, Conversation.name == "System"
        ).first()

    if not system_conversation:
        raise HTTPException(status_code=500, detail="Failed to create or fetch system conversation.")

    print(f"System conversation ID: {system_conversation.id}")
    
    # Fetch the system conversation messages for this user
    messages = db.query(InboxMessage).filter(InboxMessage.conversation_id == system_conversation.id).order_by(InboxMessage.timestamp).all()

    # Log the number of messages found
    print(f"Messages found: {len(messages)}")

    # Debug: log the contents of messages if available
    if messages:
        for msg in messages:
            print(f"Message ID: {msg.id}, Content: {msg.content}, Timestamp: {msg.timestamp}")

    # Return the messages
    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read
        }
        for m in messages
    ]