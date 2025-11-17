import os
from datetime import datetime, timezone
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Conversation, Message
from bson import ObjectId

app = FastAPI(title="AI Chat Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- Agent Registry ----------------------
AgentType = Literal["general", "code", "automation", "research", "design"]

AGENTS: List[Dict[str, Any]] = [
    {
        "id": "general",
        "name": "General AI Agent",
        "description": "Helpful, conversational assistant for everyday questions.",
        "icon": "MessageSquare"
    },
    {
        "id": "code",
        "name": "Code Agent",
        "description": "Writes and optimizes code with explanations.",
        "icon": "Code2"
    },
    {
        "id": "automation",
        "name": "Automation Agent",
        "description": "Creates Selenium/Appium style test flows.",
        "icon": "Bot"
    },
    {
        "id": "research",
        "name": "Research Agent",
        "description": "Plans, reasons, and drafts long-form answers.",
        "icon": "Search"
    },
    {
        "id": "design",
        "name": "Design Agent",
        "description": "UI/UX ideas, components, and visual suggestions.",
        "icon": "Palette"
    },
]

# ---------------------- Models ----------------------
class NewConversationRequest(BaseModel):
    title: Optional[str] = None
    agent: AgentType = "general"
    first_message: Optional[str] = None

class SendMessageRequest(BaseModel):
    content: str
    agent: Optional[AgentType] = None

# ---------------------- Utilities ----------------------

def oid(oid_str: str) -> ObjectId:
    try:
        return ObjectId(oid_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid conversation id")


def get_collection_name(model_cls) -> str:
    return model_cls.__name__.lower()


def agent_general(prompt: str) -> str:
    return f"Here is a thoughtful answer to your question:\n\n{prompt}\n\n- I summarized the key points.\n- I provided actionable steps.\n\nIf you'd like more depth, ask for examples."


def agent_code(prompt: str) -> str:
    return (
        "I drafted a code example and an optimization tip:\n\n"
        "```python\n# Example function\nfrom typing import List\n\n" 
        "def unique_sorted(items: List[int]) -> List[int]:\n    # O(n log n) due to sort\n    return sorted(set(items))\n```\n\n"
        "Optimization: Prefer built-in data structures (set, dict) and avoid premature micro-opts."
    )


def agent_automation(prompt: str) -> str:
    return (
        "Here's a Selenium test outline you can adapt:\n\n"
        "```python\nfrom selenium import webdriver\nfrom selenium.webdriver.common.by import By\nfrom selenium.webdriver.common.keys import Keys\n\nwith webdriver.Chrome() as d:\n    d.get('https://example.com')\n    d.find_element(By.ID, 'username').send_keys('user')\n    d.find_element(By.ID, 'password').send_keys('secret')\n    d.find_element(By.CSS_SELECTOR, 'button[type=submit]').click()\n    assert 'Dashboard' in d.title\n```\n\n"
        "Tip: Use data-testids for robust selectors."
    )


def agent_research(prompt: str) -> str:
    return (
        "Plan → Gather → Synthesize → Answer\n\n"
        "Plan:\n- Define scope and criteria\n- Identify sources\n\nAnswer draft:\n"
        f"- Key insights around: {prompt}\n- Trade-offs and alternatives\n- References to explore further"
    )


def agent_design(prompt: str) -> str:
    return (
        "Design directions:\n\n"
        "- Visual: minimal, high-contrast, soft shadows\n"
        "- Components: cards, segmented controls, progress\n\n"
        "Example button style:\n\n"
        "```css\n.btn{padding:.75rem 1rem;border-radius:.75rem;background:linear-gradient(135deg,#6d5dfc,#3a8bff);color:#fff;font-weight:600;}\n.btn:hover{filter:brightness(1.05)}\n```"
    )


def route_to_agent(agent: AgentType, prompt: str) -> str:
    if agent == "code":
        return agent_code(prompt)
    if agent == "automation":
        return agent_automation(prompt)
    if agent == "research":
        return agent_research(prompt)
    if agent == "design":
        return agent_design(prompt)
    return agent_general(prompt)

# ---------------------- Routes ----------------------

@app.get("/")
def read_root():
    return {"message": "AI Chat Backend running"}

@app.get("/api/agents")
def list_agents():
    return {"agents": AGENTS}

@app.get("/api/conversations")
def list_conversations():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    items = list(db["conversation"].find({}, {"messages": 0}).sort("updated_at", -1).limit(50))
    for it in items:
        it["id"] = str(it.pop("_id"))
    return {"conversations": items}

@app.post("/api/conversations")
def create_conversation(payload: NewConversationRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    now = datetime.now(timezone.utc)
    conv: Conversation = Conversation(
        title=payload.title or "New Chat",
        agent=payload.agent,
        messages=[],
        created_at=now,
        updated_at=now,
    )
    conv_id = create_document(get_collection_name(Conversation), conv)

    # If a first message was provided, immediately add it and reply
    if payload.first_message:
        user_msg = Message(role="user", content=payload.first_message)
        assistant_content = route_to_agent(payload.agent, payload.first_message)
        assistant_msg = Message(role="assistant", content=assistant_content, agent=payload.agent)
        db["conversation"].update_one(
            {"_id": ObjectId(conv_id)},
            {
                "$push": {"messages": {"$each": [user_msg.model_dump(), assistant_msg.model_dump()]}},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
    return {"id": conv_id}

@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    doc = db["conversation"].find_one({"_id": oid(conversation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Conversation not found")
    doc["id"] = str(doc.pop("_id"))
    return doc

@app.post("/api/conversations/{conversation_id}/messages")
def send_message(conversation_id: str, payload: SendMessageRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    doc = db["conversation"].find_one({"_id": oid(conversation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Conversation not found")

    active_agent: AgentType = payload.agent or doc.get("agent", "general")

    # Append user message
    user_msg = Message(role="user", content=payload.content)

    # Route to agent stub (synchronous, structured markdown reply)
    assistant_content = route_to_agent(active_agent, payload.content)
    assistant_msg = Message(role="assistant", content=assistant_content, agent=active_agent)

    db["conversation"].update_one(
        {"_id": oid(conversation_id)},
        {
            "$push": {"messages": {"$each": [user_msg.model_dump(), assistant_msg.model_dump()]}},
            "$set": {"updated_at": datetime.now(timezone.utc), "agent": active_agent}
        }
    )

    return {"message": assistant_msg.model_dump()}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
