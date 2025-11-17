"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime

# Example schemas (you can keep or remove if not needed)
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Chat application schemas
AgentType = Literal[
    "general",
    "code",
    "automation",
    "research",
    "design"
]

class Message(BaseModel):
    role: Literal["user", "assistant", "system"] = Field(..., description="Message role")
    content: str = Field(..., description="Markdown content of the message")
    agent: Optional[AgentType] = Field(None, description="Agent that produced the message, if assistant")
    created_at: Optional[datetime] = None

class Conversation(BaseModel):
    title: str = Field(..., description="Conversation title")
    agent: AgentType = Field(..., description="Default agent for the conversation")
    messages: List[Message] = Field(default_factory=list, description="Messages in the conversation")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
