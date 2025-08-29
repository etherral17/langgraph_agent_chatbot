Lang Graph Agent - production-ready skeleton

1. Create .env with:
MCP_COMMON_URL=http://localhost:9000/common
MCP_ATLAS_URL=http://localhost:9001/atlas
DATABASE_URL=sqlite+aiosqlite:///./app.db
LOG_LEVEL=DEBUG
2. Run the two uvicorn apps for common and atlas using :
    uvicorn mcp.atlas:app --port 9001 --reload
    uvicorn mcp.common:app --port 9000 --reload
4. Run sqliite3, then:
    pip install -r requirements.txt
    uvicorn app.main:app --reload

5. Example call:
Go to http://127.0.0.1:8000/docs and run the API
POST http://localhost:8000/run-agent
Body:
{
  "payload": {
    "customer_name": "Rohit",
    "email": "rohit@example.com",
    "query": "My invoice is delayed",
    "priority": "high",
    "ticket_id": "TCKT-001"
  },
  "simulate_human_answer": "Invoice INV-123 is delayed"
}
6. Video link for my submission - https://www.loom.com/share/adbc75089ef84a83b98b00c500b86c64?sid=4998b4fa-f6d4-47f4-83b6-329011776bfd
