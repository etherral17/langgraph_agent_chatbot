from dataclasses import dataclass
from typing import List, Optional

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
    exec_rule: Optional[str] = None
