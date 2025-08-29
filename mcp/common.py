from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Common MCP")

class RoutePayload(BaseModel):
    query: str

@app.post("/route_ticket")
async def route_ticket(payload: RoutePayload):
    # Simple mock routing logic
    if "payment" in payload.query.lower():
        return {"route": "payments"}
    elif "refund" in payload.query.lower():
        return {"route": "refunds"}
    else:
        return {"route": "support"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": "common-mcp"}
