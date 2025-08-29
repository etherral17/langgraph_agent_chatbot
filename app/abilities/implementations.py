from typing import Dict, Any
from app.mcp.clients import common_client, atlas_client
from loguru import logger
from app.agent.stage_def import StageAbility
import asyncio
import random

# Abilities should be small, pure-ish functions that accept and modify a central state dict.
# They return a result dict and may call MCP clients.

async def accept_payload(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    input_payload = kwargs.get("input_payload", {})
    state['payload'].update(input_payload)
    logger.info("accept_payload recorded")
    return {"status": "ok"}

async def parse_request_text(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    q = state['payload'].get('query', '')
    parsed = {"len": len(q), "words": q.split()}
    state.setdefault('parsed', {}).update(parsed)
    logger.debug("parse_request_text", parsed=parsed)
    return {"status": "ok", "parsed": parsed}

async def extract_entities(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    resp = await atlas_client.call("extract_entities", state['payload'])
    # assume resp contains 'entities'
    entities = resp.get("entities", {})
    state.setdefault('entities', {}).update(entities)
    logger.debug("extract_entities", entities=entities)
    return {"status": "ok", "entities": entities}

async def normalize_fields(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    p = state['payload']
    p['priority'] = (p.get('priority') or 'NORMAL').upper()
    if p.get('ticket_id'):
        p['ticket_id'] = str(p['ticket_id']).upper()
    logger.debug("normalize_fields", priority=p['priority'])
    return {"status": "ok"}

async def enrich_records(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    resp = await atlas_client.call("enrich_records", state['payload'])
    state.setdefault('enrichment', {}).update(resp.get('enrichment', {}))
    logger.debug("enrich_records", enrichment=state['enrichment'])
    return {"status": "ok"}

async def add_flags_calculations(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    priority = state['payload'].get('priority', 'NORMAL')
    state.setdefault('flags', {})['sla_risk'] = True if priority == "HIGH" else False
    logger.debug("flags", flags=state['flags'])
    return {"status": "ok"}

async def clarify_question(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    missing = kwargs.get("missing_fields", [])
    resp = await atlas_client.call("clarify_question", {"missing_fields": missing, **state['payload']})
    state.setdefault('pending_clarification', {})['prompt'] = resp.get("prompt")
    logger.info("clarify_question prompt created")
    return {"status": "ok", "prompt": resp.get("prompt")}

async def extract_answer(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    # In production you'd wait on message bus or callback. For sync-run we accept a simulate value
    simulated = kwargs.get("simulate_human_answer")
    if simulated:
        resp = {"answer": simulated}
    else:
        resp = await atlas_client.call("extract_answer", state['payload'])
    state.setdefault('answers', []).append(resp.get('answer'))
    logger.info("extract_answer captured")
    return {"status": "ok", "answer": resp.get("answer")}

async def store_answer(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    answers = state.get('answers', [])
    state['latest_answer'] = answers[-1] if answers else None
    logger.debug("store_answer", latest=state.get('latest_answer'))
    return {"status": "ok"}

async def knowledge_base_search(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    resp = await atlas_client.call("knowledge_base_search", {"query": state['payload'].get('query')})
    state.setdefault('kb', {})['hits'] = resp.get('kb_hits', [])
    return {"status": "ok"}

async def store_data(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    # no-op for now; keep for audit
    logger.debug("store_data stored to state.kb")
    return {"status": "ok"}

async def solution_evaluation(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    kb_hits = len(state.get('kb', {}).get('hits', []))
    base = 70 + min(20, kb_hits * 10)
    if state['payload'].get('priority') == "HIGH":
        base -= 10
    score = max(0, min(100, base + random.randint(-3, 3)))
    state.setdefault('decision', {})['score'] = score
    logger.info("solution_evaluation", score=score)
    return {"score": score}

async def escalation_decision(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    score = state.get('decision', {}).get('score', 100)
    if score < 90:
        resp = await atlas_client.call("escalation_decision", state['payload'])
        state['decision']['escalated_to'] = resp.get('assigned_to')
        return {"status": "escalated", "assigned_to": resp.get('assigned_to')}
    return {"status": "not_escalated"}

async def update_payload(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    state.setdefault('audit', []).append({'decision': state.get('decision', {}), 'ts': __import__('time').time()})
    return {"status": "ok"}

async def update_ticket(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    update_fields = {
        "status": "in_progress",
        "priority": state['payload'].get('priority'),
        "assigned_to": state.get('decision', {}).get('escalated_to')
    }
    resp = await atlas_client.call("update_ticket", {"ticket_id": state['payload'].get('ticket_id'), "update_fields": update_fields})
    return resp

async def close_ticket(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    score = state.get('decision', {}).get('score', 0)
    if score >= 90:
        resp = await atlas_client.call("close_ticket", {"ticket_id": state['payload'].get('ticket_id')})
        state['payload']['status'] = 'closed'
        return resp
    return {"status": "not_closed"}

async def response_generation(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    name = state['payload'].get('customer_name') or "Customer"
    reply = f"Hi {name},\n\nThanks for contacting support about: {state['payload'].get('query')}\n\nRegards,\nSupport Team"
    state['generated_response'] = reply
    return {"response": reply}

async def execute_api_calls(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    resp = await atlas_client.call("execute_api_calls", state['payload'])
    return resp

async def trigger_notifications(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    resp = await atlas_client.call("trigger_notifications", state['payload'])
    return resp

async def output_payload(state: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    return {"final_payload": state}
