import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from app.config import settings
from app.utils import configure_logging
from app.schemas import AgentRunRequest, AgentRunResponse
from app.agent.agent import LangGraphAgent
from app.db import create_db
from loguru import logger

configure_logging()
app = FastAPI(title=settings.APP_NAME)

agent = LangGraphAgent()

@app.on_event("startup")
async def startup_event():
    logger.info("Starting app, creating DB tables if needed")
    await create_db()

@app.post("/run-agent", response_model=AgentRunResponse)
async def run_agent(req: AgentRunRequest):
    try:
        result = await agent.run(req.payload.dict(), simulate_human_answer=req.simulate_human_answer)
        return {"final_payload": result["final_payload"], "logs": result["logs"]}
    except Exception as e:
        logger.exception("Agent error")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False, log_config=None)
