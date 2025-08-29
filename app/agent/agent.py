from app.agent.stage_def import Stage, StageAbility
from typing import List, Dict, Any
from app.config import settings
from loguru import logger
from app.abilities import implementations as impl
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import AsyncSessionLocal
from app.models import AgentRun

# Stage graph config — mirrors your appendix
STAGE_CONFIG: List[Stage] = [
    Stage("INTAKE", "deterministic", [StageAbility("accept_payload","COMMON","Accept payload")]),
    Stage("UNDERSTAND", "deterministic", [
        StageAbility("parse_request_text","COMMON","Parse text"),
        StageAbility("extract_entities","ATLAS","Extract entities")
    ]),
    Stage("PREPARE", "deterministic", [
        StageAbility("normalize_fields","COMMON","Normalize"),
        StageAbility("enrich_records","ATLAS","Enrich"),
        StageAbility("add_flags_calculations","COMMON","Flags")
    ]),
    Stage("ASK","human",[StageAbility("clarify_question","ATLAS","Clarify")]),
    Stage("WAIT","deterministic",[
        StageAbility("extract_answer","ATLAS","Extract answer"),
        StageAbility("store_answer","COMMON","Store answer")
    ]),
    Stage("RETRIEVE","deterministic",[
        StageAbility("knowledge_base_search","ATLAS","KB search"),
        StageAbility("store_data","COMMON","Store KB")
    ]),
    Stage("DECIDE","non-deterministic",[
        StageAbility("solution_evaluation","COMMON","Score solutions"),
        StageAbility("escalation_decision","ATLAS","Escalate if needed"),
        StageAbility("update_payload","COMMON","Record decision")
    ], exec_rule="score_then_maybe_escalate"),
    Stage("UPDATE","deterministic",[
        StageAbility("update_ticket","ATLAS","Update ticket"),
        StageAbility("close_ticket","ATLAS","Close ticket")
    ]),
    Stage("CREATE","deterministic",[StageAbility("response_generation","COMMON","Generate reply")]),
    Stage("DO","deterministic",[
        StageAbility("execute_api_calls","ATLAS","Execute APIs"),
        StageAbility("trigger_notifications","ATLAS","Notify")
    ]),
    Stage("COMPLETE","deterministic",[StageAbility("output_payload","COMMON","Output payload")])
]

# mapping ability names to implementations
ABILITY_LOOKUP = {
    "accept_payload": impl.accept_payload,
    "parse_request_text": impl.parse_request_text,
    "extract_entities": impl.extract_entities,
    "normalize_fields": impl.normalize_fields,
    "enrich_records": impl.enrich_records,
    "add_flags_calculations": impl.add_flags_calculations,
    "clarify_question": impl.clarify_question,
    "extract_answer": impl.extract_answer,
    "store_answer": impl.store_answer,
    "knowledge_base_search": impl.knowledge_base_search,
    "store_data": impl.store_data,
    "solution_evaluation": impl.solution_evaluation,
    "escalation_decision": impl.escalation_decision,
    "update_payload": impl.update_payload,
    "update_ticket": impl.update_ticket,
    "close_ticket": impl.close_ticket,
    "response_generation": impl.response_generation,
    "execute_api_calls": impl.execute_api_calls,
    "trigger_notifications": impl.trigger_notifications,
    "output_payload": impl.output_payload
}

class LangGraphAgent:
    def __init__(self, stages: List[Stage] = None):
        self.stages = stages or STAGE_CONFIG

    async def run(self, input_payload: Dict[str, Any], simulate_human_answer: str = None) -> Dict[str, Any]:
        # central mutable state
        state: Dict[str, Any] = {"payload": dict(input_payload)}
        logs = []
        try:
            for stage in self.stages:
                logs.append(f"=== STAGE {stage.name} ({stage.mode}) ===")
                logger.info(f"stage: {stage.name} mode={stage.mode}")
                if stage.mode in ("deterministic", "human"):
                    for ability in stage.abilities:
                        logs.append(f"-> ability {ability.name}")
                        fn = ABILITY_LOOKUP.get(ability.name)
                        if not fn:
                            logs.append(f"!! missing impl {ability.name}")
                            continue
                        extra = {}
                        if ability.name == "accept_payload":
                            extra["input_payload"] = input_payload
                        if ability.name == "extract_answer":
                            extra["simulate_human_answer"] = simulate_human_answer
                        res = await fn(state, **extra)
                        logs.append(f"   -> res: {res}")
                elif stage.mode == "non-deterministic":
                    if stage.exec_rule == "score_then_maybe_escalate":
                        # evaluate
                        res = await ABILITY_LOOKUP["solution_evaluation"](state)
                        logs.append(f"   -> solution score: {res.get('score')}")
                        score = state.get('decision', {}).get('score', 100)
                        if score < 90:
                            res2 = await ABILITY_LOOKUP["escalation_decision"](state)
                            logs.append(f"   -> escalation: {res2}")
                        else:
                            logs.append("   -> score >= 90, skipping escalation")
                        await ABILITY_LOOKUP["update_payload"](state)
                    else:
                        # fallback: run sequentially
                        for ability in stage.abilities:
                            fn = ABILITY_LOOKUP.get(ability.name)
                            if fn:
                                res = await fn(state)
                                logs.append(f"   -> {ability.name} {res}")
                else:
                    logs.append(f"Unknown stage mode {stage.mode}")
            # final payload
            final = state
            # persist run
            await self._persist_run(input_payload, final, logs)
            return {"final_payload": final, "logs": logs}
        except Exception as e:
            logger.exception("agent run failed")
            logs.append(f"error: {str(e)}")
            await self._persist_run(input_payload, state, logs)
            raise

    async def _persist_run(self, input_payload: Dict[str, Any], final_payload: Dict[str, Any], logs):
        # persist to DB for audit
        try:
            async with AsyncSessionLocal() as session:
                run = AgentRun(ticket_id=input_payload.get("ticket_id"), input_payload=input_payload, result_payload=final_payload, logs=logs)
                session.add(run)
                await session.commit()
        except Exception:
            logger.exception("failed to persist run (non-fatal)")
