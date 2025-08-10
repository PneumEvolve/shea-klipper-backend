from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from models import InboxMessage, Conversation, ConversationUser, User
from database import get_db
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

router = APIRouter()

class MessageInput(BaseModel):
    users: List[str]  # List of user IDs (or emails) to include in the conversation
    content: str      # The content of the message
    user_id: str      # ID of the user sending the message
    conversation_id: int  # The ID of the conversation

# Check if conversation exists or create a new one
@router.post("/inbox/start-conversation")
def start_conversation(data: MessageInput, db: Session = Depends(get_db)):
    # Ensure the user exists first
    user = db.query(User).filter(User.email == data.user_id).first()  # check the real user (sheaklipper@gmail.com)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {data.user_id} not found")

    # Check if the System user exists; if not, create it
    system_user = db.query(User).filter(User.email == "system@domain.com").first()  # System user email
    if not system_user:
        # Create the System user if it doesn't exist
        system_user = User(email="system@domain.com", name="System")
        db.add(system_user)
        db.commit()
        db.refresh(system_user)
    
    # Now create the conversation and add users (including system user)
    conversation = db.query(Conversation).filter(Conversation.id == data.conversation_id).first()

    if not conversation:
        # Create a new conversation if it doesn't exist
        conversation = Conversation(name="System")  # You can customize the name of the conversation
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Add the regular user and System user to the conversation
    conversation_user = ConversationUser(user_id=user.id, conversation_id=conversation.id)
    db.add(conversation_user)

    # Add the system user to the conversation
    conversation_user_system = ConversationUser(user_id=system_user.id, conversation_id=conversation.id)
    db.add(conversation_user_system)

    db.commit()

    # Create and send the system message
    system_message = InboxMessage(
        user_id=system_user.id,  # system user (non-real user)
        content="Welcome to your inbox! This is a system-generated message.",
        timestamp=datetime.utcnow(),
        conversation_id=conversation.id
    )
    db.add(system_message)
    db.commit()
    db.refresh(system_message)

    # Send the user's message
    message = InboxMessage(
        user_id=data.user_id,
        content=data.content,
        timestamp=datetime.utcnow(),
        conversation_id=conversation.id
    )
    db.add(message)
    db.commit()

    return {"status": "message_sent", "conversation_id": conversation.id, "message_id": message.id}

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

# Ensure there's a "System" conversation for the user, create if not
@router.get("/inbox/{user_id}")
def get_inbox(user_id: str, db: Session = Depends(get_db)):
    # Log the request to fetch the inbox
    print(f"Fetching inbox for user: {user_id}")
    
    # Find the System conversation for the user
    system_conversation = db.query(Conversation).join(ConversationUser).filter(
        ConversationUser.user_id == user_id, Conversation.name == "System"
    ).first()

    # If no System conversation exists, create one and a system message
    if not system_conversation:
        print(f"No System conversation found for user {user_id}. Creating one.")
        
        # Create new System conversation
        conversation = Conversation(name="System")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        # Add the user to the System conversation
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            conversation_user = ConversationUser(user_id=user.id, conversation_id=conversation.id)
            db.add(conversation_user)
        db.commit()

        # Send a system-generated message to the new System conversation
        system_message = InboxMessage(
            user_id="system",  # Send from the system, not a real user
            content="Welcome to your inbox! This is a system-generated message.",
            timestamp=datetime.utcnow(),
            conversation_id=conversation.id
        )
        db.add(system_message)
        db.commit()
        db.refresh(system_message)

        # Return the system conversation with messages
        system_conversation = db.query(Conversation).join(ConversationUser).filter(
            ConversationUser.user_id == user_id, Conversation.name == "System"
        ).first()

    # Fetch the system conversation messages
    messages = db.query(InboxMessage).filter(InboxMessage.conversation_id == system_conversation.id).order_by(InboxMessage.timestamp).all()

    # Log the number of messages found
    print(f"Messages found: {len(messages)}")

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
        user_id="1",  # 📥 send to your inbox
        content=content,
        timestamp=datetime.utcnow()
    )
    db.add(msg)
    db.commit()
    return {"status": "received"}