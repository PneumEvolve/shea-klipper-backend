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
        db.commit()
        db.refresh(system_user)
    return system_user

# Optimize conversation creation, user addition, and messaging
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

    # Add both the user and system user to the conversation
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

    db.add(system_message)
    db.add(user_message)

    # Commit all the changes at once
    db.commit()

    return {"status": "message_sent", "conversation_id": conversation.id, "message_id": user_message.id}

# Send message to a conversation
@router.post("/inbox/send")
def send_message(data: MessageInput, db: Session = Depends(get_db)):
    # Check if the conversation exists
    conversation = db.query(Conversation).filter(Conversation.id == data.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    
    msg = InboxMessage(user_id=data.user_id, content=data.content, timestamp=datetime.utcnow(), conversation_id=conversation.id)
    db.add(msg)
    db.commit()

    return {"status": "sent"}

# Get all messages from a conversation
@router.get("/inbox/{conversation_id}")
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    
    messages = db.query(InboxMessage).filter(InboxMessage.conversation_id == conversation_id).order_by(InboxMessage.timestamp).all()

    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read,
            "user_id": m.user_id
        }
        for m in messages
    ]

# Ensure there's a unique "System" conversation for the user, create if not
@router.get("/inbox/{user_id}")
def get_inbox(user_id: str, db: Session = Depends(get_db)):
    print(f"Fetching inbox for user: {user_id}")
    
    # Check if the user already has a unique "System" conversation
    system_conversation = db.query(Conversation).join(ConversationUser).filter(
        ConversationUser.user_id == user_id, Conversation.name == "System"
    ).first()

    # If no unique System conversation exists, create one
    if not system_conversation:
        print(f"No System conversation found for user {user_id}. Creating one.")
        
        # Create new System conversation specifically for this user
        conversation = Conversation(name="System")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        # Add the user to the System conversation
        user = db.query(User).filter(User.email == user_id).first()  # Get user by email
        if user:
            conversation_user = ConversationUser(user_id=user.id, conversation_id=conversation.id)
            db.add(conversation_user)
        db.commit()

        # Send system-generated message to the new System conversation
        system_message = InboxMessage(
            user_id="system",  # system user (non-real user)
            content="Welcome to your inbox! This is a system-generated message.",
            timestamp=datetime.utcnow(),
            conversation_id=conversation.id
        )
        db.add(system_message)
        db.commit()
        db.refresh(system_message)

        # Re-fetch the conversation with messages
        system_conversation = db.query(Conversation).join(ConversationUser).filter(
            ConversationUser.user_id == user_id, Conversation.name == "System"
        ).first()

    # Fetch the system conversation messages
    messages = db.query(InboxMessage).filter(InboxMessage.conversation_id == system_conversation.id).order_by(InboxMessage.timestamp).all()

    print(f"Messages found: {len(messages)}")
    
    return [
        {
            "id": m.id,
            "content": m.content,
            "timestamp": m.timestamp,
            "read": m.read
        }
        for m in messages
    ]

# Mark a message as read
@router.post("/inbox/read/{message_id}")
def mark_message_read(message_id: int, db: Session = Depends(get_db)):
    message = db.query(InboxMessage).filter(InboxMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    message.read = True
    db.commit()
    return {"status": "marked_as_read"}

# Submit a contribution message
@router.post("/inbox/contribute")
def submit_contribution(data: dict, db=Depends(get_db)):
    content = f"""
📬 **New Contributor Submission**

📧 Contact: {data.get('contact', 'N/A')}
🎯 Interests: {', '.join(data.get('interests', []))}
💡 Idea: {data.get('idea', '')}
🐞 Bugs: {data.get('bugs', '')}
🛠 Skills: {data.get('skills', '')}
🗨 Extra: {data.get('extra', '')}
""".strip()

    msg = InboxMessage(
        user_id="1",  # Send to your inbox
        content=content,
        timestamp=datetime.utcnow()
    )
    db.add(msg)
    db.commit()
    return {"status": "received"}