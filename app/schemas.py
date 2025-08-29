from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List

class InputPayload(BaseModel):
    customer_name: Optional[str] = Field(None)
    email: Optional[EmailStr] = Field(None)
    query: str
    priority: Optional[str] = "NORMAL"
    ticket_id: Optional[str]

class AgentRunRequest(BaseModel):
    payload: InputPayload
    simulate_human_answer: Optional[str] = None

class AgentRunResponse(BaseModel):
    final_payload: Dict[str, Any]
    logs: List[str]
