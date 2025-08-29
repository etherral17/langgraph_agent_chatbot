from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Atlas MCP")

class EntityPayload(BaseModel):
    customer_name: Optional[str] = None
    email: Optional[str] = None
    query: str
    priority: Optional[str] = None

@app.post("/extract_entities")
async def extract_entities(payload: EntityPayload):
    # Mock entity extraction
    return {
        "entities": {
            "customer_name": payload.customer_name or "Unknown",
            "email": payload.email or "not_provided@example.com",
            "priority": payload.priority or "NORMAL"
        }
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "atlas-mcp"}
