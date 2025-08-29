"""
lang_graph_agent.py

Complete implementation of a Lang Graph Agent for a customer support workflow.
- Models 11 stages (INTAKE .. COMPLETE)
- Supports deterministic stages (sequential) and non-deterministic stages (runtime choice)
- Routes abilities to MCP clients: COMMON or ATLAS (simulated)
- Persists state across stages
- Produces logs and final structured payload

How to run:
    python lang_graph_agent.py
"""

import json
import time
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ----------------------------
# Configuration (Agent Config)
# ----------------------------
AGENT_CONFIG = {
    "input_schema": {
        "customer_name": "str",
        "email": "str",
        "query": "str",
        "priority": "str",
        "ticket_id": "str"
    },
    "stages": [
        {
            "name": "INTAKE",
            "mode": "deterministic",
            "abilities": [
                {"name": "accept_payload", "mcp": "COMMON", "prompt": "Accept payload and record input fields."}
            ]
        },
        {
            "name": "UNDERSTAND",
            "mode": "deterministic",
            "abilities": [
                {"name": "parse_request_text", "mcp": "COMMON", "prompt": "Parse text to structured fields."},
                {"name": "extract_entities", "mcp": "ATLAS", "prompt": "Extract product/account/dates from text."}
            ]
        },
        {
            "name": "PREPARE",
            "mode": "deterministic",
            "abilities": [
                {"name": "normalize_fields", "mcp": "COMMON", "prompt": "Normalize dates/codes/IDs."},
                {"name": "enrich_records", "mcp": "ATLAS", "prompt": "Attach SLA and historical ticket info."},
                {"name": "add_flags_calculations", "mcp": "COMMON", "prompt": "Compute priority / SLA risk flags."}
            ]
        },
        {
            "name": "ASK",
            "mode": "human",
            "abilities": [
                {"name": "clarify_question", "mcp": "ATLAS", "prompt": "Request missing information from user/human."}
            ]
        },
        {
            "name": "WAIT",
            "mode": "deterministic",
            "abilities": [
                {"name": "extract_answer", "mcp": "ATLAS", "prompt": "Capture human response."},
                {"name": "store_answer", "mcp": "COMMON", "prompt": "Store captured answer into state."}
            ]
        },
        {
            "name": "RETRIEVE",
            "mode": "deterministic",
            "abilities": [
                {"name": "knowledge_base_search", "mcp": "ATLAS", "prompt": "Search KB/FAQ."},
                {"name": "store_data", "mcp": "COMMON", "prompt": "Attach retrieved KB results to payload."}
            ]
        },
        {
            "name": "DECIDE",
            "mode": "non-deterministic",
            "abilities": [
                {"name": "solution_evaluation", "mcp": "COMMON", "prompt": "Score potential solutions 1-100."},
                {"name": "escalation_decision", "mcp": "ATLAS", "prompt": "If score < 90, escalate to human."},
                {"name": "update_payload", "mcp": "COMMON", "prompt": "Record decision results into payload."}
            ],
            "exec_rule": "score_then_maybe_escalate"  # custom orchestration hint
        },
        {
            "name": "UPDATE",
            "mode": "deterministic",
            "abilities": [
                {"name": "update_ticket", "mcp": "ATLAS", "prompt": "Update ticket fields and status."},
                {"name": "close_ticket", "mcp": "ATLAS", "prompt": "Close ticket if resolved."}
            ]
        },
        {
            "name": "CREATE",
            "mode": "deterministic",
            "abilities": [
                {"name": "response_generation", "mcp": "COMMON", "prompt": "Generate customer-facing reply."}
            ]
        },
        {
            "name": "DO",
            "mode": "deterministic",
            "abilities": [
                {"name": "execute_api_calls", "mcp": "ATLAS", "prompt": "Execute backend CRM/API calls."},
                {"name": "trigger_notifications", "mcp": "ATLAS", "prompt": "Send notifications to customer/human agent."}
            ]
        },
        {
            "name": "COMPLETE",
            "mode": "deterministic",
            "abilities": [
                {"name": "output_payload", "mcp": "COMMON", "prompt": "Return final structured payload."}
            ]
        }
    ]
}

# ----------------------------
# Simulated MCP Clients
# ----------------------------
class MCPClient:
    def __init__(self, server_name: str):
        self.server_name = server_name

    def call(self, ability: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate calling an ability on remote servers (COMMON or ATLAS).
        In a real integration, this would do HTTP/RPC, auth, retries, etc.
        """
        # Logging point: which server and ability
        print(f"[MCP:{self.server_name}] Calling ability '{ability}' with payload keys: {list(payload.keys())}")
        # Simulated latency
        time.sleep(0.05)

        # Dispatch to local ability implementations (simulated remote)
        handler_name = f"_remote_{ability}"
        handler = getattr(self, handler_name, None)
        if handler:
            return handler(payload)
        else:
            # default simulated response
            return {"status": "ok", "ability": ability, "server": self.server_name, "result": {}}

    # Simulated remote ability implementations for demonstration
    def _remote_extract_entities(self, payload):
        text = payload.get("query", "")
        # naive extraction
        entities = {}
        if "invoice" in text.lower():
            entities["topic"] = "billing"
        if "delay" in text.lower() or "late" in text.lower():
            entities["issue_type"] = "delay"
        # pretend we also fetch account id
        entities["account_id"] = payload.get("ticket_id", "acct-" + str(random.randint(1000, 9999)))
        return {"status": "ok", "entities": entities}

    def _remote_enrich_records(self, payload):
        # simulate looking up SLA and history
        sla = {"SLA": "48h", "historical_tickets": random.randint(0, 5)}
        return {"status": "ok", "enrichment": sla}

    def _remote_clarify_question(self, payload):
        # produce a message that would be sent to the human/customer
        missing = payload.get("missing_fields", ["additional_details"])
        prompt = f"Please provide: {', '.join(missing)}"
        return {"status": "pending_human", "prompt": prompt}

    def _remote_extract_answer(self, payload):
        # simulate receiving human answer
        # In demo we will assume human replied with a provided 'simulated_human_answer' in payload
        answer = payload.get("simulated_human_answer", "The invoice number is INV-1234.")
        return {"status": "ok", "answer": answer}

    def _remote_knowledge_base_search(self, payload):
        query = payload.get("query", "")
        # simple rule-based KB retrieval
        kb_hits = []
        if "billing" in query.lower():
            kb_hits.append({"id": "kb-101", "title": "How billing works", "snippet": "Invoices are due in 30 days."})
        if "delay" in query.lower():
            kb_hits.append({"id": "kb-201", "title": "Shipment delays", "snippet": "Reasons for delays and remedies."})
        return {"status": "ok", "kb_hits": kb_hits}

    def _remote_update_ticket(self, payload):
        # pretend the ticket was updated in a ticketing system
        ticket_id = payload.get("ticket_id")
        return {"status": "ok", "ticket_id": ticket_id, "updated_fields": payload.get("update_fields", {})}

    def _remote_close_ticket(self, payload):
        ticket_id = payload.get("ticket_id")
        return {"status": "ok", "ticket_id": ticket_id, "closed": True}

    def _remote_execute_api_calls(self, payload):
        # simulate performing CRM operations; return success/fail
        return {"status": "ok", "api_calls": ["crm.update", "order.process"], "results": {"crm.update": "success"}}

    def _remote_trigger_notifications(self, payload):
        # simulate notification dispatch
        return {"status": "ok", "notifications_sent": ["email", "slack"]}

    def _remote_escalation_decision(self, payload):
        # This server would route to human agent systems; simulate assignment id
        assigned_to = "human_agent_" + str(random.randint(1, 50))
        return {"status": "escalated", "assigned_to": assigned_to}


# Instantiate MCP clients for COMMON and ATLAS
MCP_COMMON = MCPClient("COMMON")
MCP_ATLAS = MCPClient("ATLAS")

# ----------------------------
# Agent Data Structures
# ----------------------------
@dataclass
class StageAbility:
    name: str
    mcp: str
    prompt: str


@dataclass
class Stage:
    name: str
    mode: str  # deterministic | non-deterministic | human
    abilities: List[StageAbility]
    exec_rule: Optional[str] = None  # optional orchestration hint


@dataclass
class AgentState:
    payload: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def log(self, message: str):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{ts} | {message}"
        self.logs.append(entry)
        print(entry)  # also print to stdout for the demo

# ----------------------------
# Ability Implementations (local wrappers)
# ----------------------------
def call_mcp(ability: str, mcp: str, state: AgentState, **kwargs) -> Dict[str, Any]:
    """
    Wrapper to call the simulated MCP client.
    Returns the response dict.
    """
    payload = {"payload": state.payload, **kwargs}
    if mcp.upper() == "COMMON":
        resp = MCP_COMMON.call(ability, {**state.payload, **kwargs})
    elif mcp.upper() == "ATLAS":
        resp = MCP_ATLAS.call(ability, {**state.payload, **kwargs})
    else:
        raise ValueError(f"Unknown MCP server: {mcp}")
    # record history
    state.history.append({
        "ability": ability,
        "mcp": mcp,
        "request": {**state.payload, **kwargs},
        "response": resp,
        "timestamp": time.time()
    })
    return resp

# Local wrappers for abilities that also update state when needed
def ability_accept_payload(state: AgentState, **kwargs):
    state.payload.update(kwargs.get("input_payload", {}))
    state.log(f"[INTAKE] accept_payload: recorded ticket_id={state.payload.get('ticket_id')}")
    return {"status": "ok"}

def ability_parse_request_text(state: AgentState, **kwargs):
    query = state.payload.get("query", "")
    # Very simple parsing heuristics for demo
    parsed = {"text_length": len(query), "lower": query.lower()}
    state.payload.setdefault("parsed", {}).update(parsed)
    state.log(f"[UNDERSTAND] parse_request_text: extracted text_length={parsed['text_length']}")
    return {"status": "ok", "parsed": parsed}

def ability_extract_entities(state: AgentState, **kwargs):
    resp = call_mcp("extract_entities", "ATLAS", state)
    entities = resp.get("entities", {})
    state.payload.setdefault("entities", {}).update(entities)
    state.log(f"[UNDERSTAND] extract_entities: {entities}")
    return resp

def ability_normalize_fields(state: AgentState, **kwargs):
    # Example: normalize priority to uppercase, ticket id to standard format
    priority = state.payload.get("priority", "normal").upper()
    state.payload["priority"] = priority
    if "ticket_id" in state.payload:
        state.payload["ticket_id"] = str(state.payload["ticket_id"]).upper()
    state.log(f"[PREPARE] normalize_fields: priority={priority}")
    return {"status": "ok"}

def ability_enrich_records(state: AgentState, **kwargs):
    resp = call_mcp("enrich_records", "ATLAS", state)
    enrichment = resp.get("enrichment", {})
    state.payload.setdefault("enrichment", {}).update(enrichment)
    state.log(f"[PREPARE] enrich_records: {enrichment}")
    return resp

def ability_add_flags_calculations(state: AgentState, **kwargs):
    # Example: compute SLA risk flag
    sla = state.payload.get("enrichment", {}).get("SLA", "72h")
    # heuristic: if priority is HIGH then risk = True
    risk = state.payload.get("priority", "") == "HIGH"
    state.payload.setdefault("flags", {})["sla_risk"] = risk
    state.log(f"[PREPARE] add_flags_calculations: sla={sla}, sla_risk={risk}")
    return {"status": "ok", "sla": sla, "sla_risk": risk}

def ability_clarify_question(state: AgentState, **kwargs):
    # Simulate a human question creation via ATLAS
    missing = []
    if not state.payload.get("customer_name"):
        missing.append("customer_name")
    if not state.payload.get("email"):
        missing.append("email")
    resp = call_mcp("clarify_question", "ATLAS", state, missing_fields=missing)
    state.payload.setdefault("pending_clarification", {})["prompt"] = resp.get("prompt")
    state.log(f"[ASK] clarify_question: prompt='{resp.get('prompt')}'")
    return resp

def ability_extract_answer(state: AgentState, **kwargs):
    # Simulate waiting and then capturing an answer
    resp = call_mcp("extract_answer", "ATLAS", state, simulated_human_answer=kwargs.get("simulated_human_answer"))
    answer = resp.get("answer")
    state.payload.setdefault("answers", []).append(answer)
    state.log(f"[WAIT] extract_answer: captured answer='{answer}'")
    return resp

def ability_store_answer(state: AgentState, **kwargs):
    # store_answer is part of state management — ensure answers exist
    answers = state.payload.get("answers", [])
    state.payload["latest_answer"] = answers[-1] if answers else None
    state.log(f"[WAIT] store_answer: latest_answer='{state.payload.get('latest_answer')}'")
    return {"status": "ok"}

def ability_knowledge_base_search(state: AgentState, **kwargs):
    resp = call_mcp("knowledge_base_search", "ATLAS", state, query=state.payload.get("query", ""))
    kb_hits = resp.get("kb_hits", [])
    state.payload.setdefault("kb", {})["hits"] = kb_hits
    state.log(f"[RETRIEVE] knowledge_base_search: {len(kb_hits)} hits")
    return resp

def ability_store_data(state: AgentState, **kwargs):
    # store KB results into payload (done above as well)
    kb = state.payload.get("kb", {})
    state.log(f"[RETRIEVE] store_data: stored {len(kb.get('hits', []))} kb hits")
    return {"status": "ok"}

def ability_solution_evaluation(state: AgentState, **kwargs):
    # Score potential solutions 1-100 using simple heuristics
    kb_hits = len(state.payload.get("kb", {}).get("hits", []))
    priority = state.payload.get("priority", "NORMAL")
    # heuristic scoring
    base = 70
    base += min(20, kb_hits * 10)
    if priority == "HIGH":
        base -= 10
    # clamp
    score = max(0, min(100, base + random.randint(-5, 5)))
    state.payload.setdefault("decision", {})["score"] = score
    state.log(f"[DECIDE] solution_evaluation: score={score}")
    return {"score": score}

def ability_escalation_decision(state: AgentState, **kwargs):
    score = state.payload.get("decision", {}).get("score", 100)
    if score < 90:
        # call ATLAS to escalate
        resp = call_mcp("escalation_decision", "ATLAS", state)
        assigned_to = resp.get("assigned_to")
        state.payload["decision"]["escalated_to"] = assigned_to
        state.log(f"[DECIDE] escalation_decision: escalated to {assigned_to}")
        return resp
    else:
        state.payload["decision"]["escalated_to"] = None
        state.log(f"[DECIDE] escalation_decision: not escalated (score={score})")
        return {"status": "not_escalated", "score": score}

def ability_update_payload(state: AgentState, **kwargs):
    # record the decision outcomes
    d = state.payload.get("decision", {})
    state.payload.setdefault("audit", []).append({"decision_recorded": d, "ts": time.time()})
    state.log(f"[DECIDE] update_payload: decision recorded")
    return {"status": "ok"}

def ability_update_ticket(state: AgentState, **kwargs):
    update_fields = {
        "status": "in_progress",
        "priority": state.payload.get("priority"),
        "assigned_to": state.payload.get("decision", {}).get("escalated_to")
    }
    resp = call_mcp("update_ticket", "ATLAS", state, ticket_id=state.payload.get("ticket_id"), update_fields=update_fields)
    state.log(f"[UPDATE] update_ticket: {resp}")
    return resp

def ability_close_ticket(state: AgentState, **kwargs):
    # decide to close if decision score >= 90
    score = state.payload.get("decision", {}).get("score", 0)
    if score >= 90:
        resp = call_mcp("close_ticket", "ATLAS", state, ticket_id=state.payload.get("ticket_id"))
        state.payload["status"] = "closed"
        state.log(f"[UPDATE] close_ticket: closed ticket")
        return resp
    else:
        state.log(f"[UPDATE] close_ticket: not closing ticket (score={score})")
        return {"status": "not_closed", "score": score}

def ability_response_generation(state: AgentState, **kwargs):
    # generate a reply using available info
    name = state.payload.get("customer_name", "Customer")
    latest_answer = state.payload.get("latest_answer", "")
    kb_snips = [h["snippet"] for h in state.payload.get("kb", {}).get("hits", [])]
    kb_text = " ".join(kb_snips) if kb_snips else ""
    reply = f"Hi {name},\n\nThanks for contacting us. Based on your message: '{latest_answer}'.\n{kb_text}\n\nRegards,\nSupport Team"
    state.payload["generated_response"] = reply
    state.log(f"[CREATE] response_generation: drafted response (len={len(reply)})")
    return {"response": reply}

def ability_execute_api_calls(state: AgentState, **kwargs):
    resp = call_mcp("execute_api_calls", "ATLAS", state)
    state.log(f"[DO] execute_api_calls: {resp}")
    return resp

def ability_trigger_notifications(state: AgentState, **kwargs):
    resp = call_mcp("trigger_notifications", "ATLAS", state)
    state.log(f"[DO] trigger_notifications: {resp}")
    return resp

def ability_output_payload(state: AgentState, **kwargs):
    # final payload output
    state.log("[COMPLETE] output_payload: preparing final payload")
    return {"final_payload": state.payload}

# Map ability names to local wrappers
ABILITY_REGISTRY: Dict[str, Callable[[AgentState], Dict[str, Any]]] = {
    "accept_payload": ability_accept_payload,
    "parse_request_text": ability_parse_request_text,
    "extract_entities": ability_extract_entities,
    "normalize_fields": ability_normalize_fields,
    "enrich_records": ability_enrich_records,
    "add_flags_calculations": ability_add_flags_calculations,
    "clarify_question": ability_clarify_question,
    "extract_answer": ability_extract_answer,
    "store_answer": ability_store_answer,
    "knowledge_base_search": ability_knowledge_base_search,
    "store_data": ability_store_data,
    "solution_evaluation": ability_solution_evaluation,
    "escalation_decision": ability_escalation_decision,
    "update_payload": ability_update_payload,
    "update_ticket": ability_update_ticket,
    "close_ticket": ability_close_ticket,
    "response_generation": ability_response_generation,
    "execute_api_calls": ability_execute_api_calls,
    "trigger_notifications": ability_trigger_notifications,
    "output_payload": ability_output_payload
}

# ----------------------------
# Graph Orchestration Engine
# ----------------------------
class LangGraphAgent:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.stages: List[Stage] = self._load_stages(config)
        self.state = AgentState()

    def _load_stages(self, cfg: Dict[str, Any]) -> List[Stage]:
        stages = []
        for s in cfg.get("stages", []):
            abilities = [StageAbility(**a) for a in s.get("abilities", [])]
            stages.append(Stage(name=s["name"], mode=s["mode"], abilities=abilities, exec_rule=s.get("exec_rule")))
        return stages

    def _execute_ability(self, ability: StageAbility, **kwargs) -> Dict[str, Any]:
        self.state.log(f"--> Executing ability '{ability.name}' via {ability.mcp} (prompt: {ability.prompt})")
        impl = ABILITY_REGISTRY.get(ability.name)
        if not impl:
            self.state.log(f"!! No local implementation for ability '{ability.name}'")
            return {"status": "error", "reason": "not_implemented"}
        # pass through state and any extra kwargs (like simulated human replies)
        return impl(self.state, **kwargs)

    def run(self, input_payload: Dict[str, Any], simulate_human_answer: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the full agent workflow end-to-end.
        simulate_human_answer: if provided, will be used when WAIT/extract_answer is called.
        """
        # Validate & accept payload
        self.state.payload = {}
        self.state.log("Agent starting. Loading input payload.")
        # stage-by-stage execution
        for stage in self.stages:
            self.state.log(f"=== STAGE: {stage.name} (mode={stage.mode}) ===")
            # deterministic/human stages: execute abilities in sequence
            if stage.mode in ("deterministic", "human"):
                for ability in stage.abilities:
                    # special case: accept_payload needs the input
                    extra = {}
                    if ability.name == "accept_payload":
                        extra["input_payload"] = input_payload
                    if ability.name == "extract_answer":
                        extra["simulated_human_answer"] = simulate_human_answer
                    resp = self._execute_ability(ability, **extra)
            elif stage.mode == "non-deterministic":
                # non-deterministic orchestration; use exec_rule or default behavior
                if stage.exec_rule == "score_then_maybe_escalate":
                    # 1) evaluate solutions
                    self._execute_ability(StageAbility(name="solution_evaluation", mcp="COMMON", prompt="Score solutions"), )
                    # 2) if score < 90 -> escalate (ATLAS)
                    score = self.state.payload.get("decision", {}).get("score", 100)
                    if score < 90:
                        self._execute_ability(StageAbility(name="escalation_decision", mcp="ATLAS", prompt="Escalate if needed"))
                    else:
                        self.state.log("[DECIDE] score >= 90: skipping escalation")
                    # 3) update payload to record decision
                    self._execute_ability(StageAbility(name="update_payload", mcp="COMMON", prompt="Record decision"))
                else:
                    # default: run abilities in some dynamic order (for demo, run sequentially)
                    for ability in stage.abilities:
                        self._execute_ability(ability)
            else:
                self.state.log(f"[WARN] Unknown stage mode '{stage.mode}'. Skipping.")
        # After all stages, get final payload output ability result
        final_resp = ability_output_payload(self.state)
        return final_resp.get("final_payload", {})

# ----------------------------
# Demo run (sample input)
# ----------------------------
if __name__ == "__main__":
    sample_input = {
        "customer_name": "Rohit Sharma",
        "email": "rohit@example.com",
        "query": "My invoice INV-9876 is delayed and I was charged extra. Please help!",
        "priority": "high",
        "ticket_id": "TCKT-20250827-001"
    }

    print("\n=== Lang Graph Agent Demo Run ===\n")
    agent = LangGraphAgent(AGENT_CONFIG)
    final_payload = agent.run(sample_input, simulate_human_answer="Invoice number INV-9876, please check billing cycle.")
    print("\n=== Final Structured Payload (JSON) ===")
    print(json.dumps(final_payload, indent=2))
    print("\n=== Execution Logs ===")
    for log_line in agent.state.logs:
        print(log_line)
    print("\n=== History of Abilities Called (summary) ===")
    for h in agent.state.history:
        print(f"- {h['ability']} via {h['mcp']} -> status: {h['response'].get('status')}")
