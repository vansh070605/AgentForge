"""agentforge.llm.agents — LLM-augmented agent callables.

These are drop-in hook callables that slot into the existing deterministic
agent architecture without modifying any core agent code.

    LLMIdentityGenerator  → custom_generator  hook on IdentityAgent
    LLMExecutionPlanner   → execution_plan_generator hook on PipelineOrchestrator
    LLMReviewInspector    → custom_inspector  hook on ReviewAgent
"""

from agentforge.llm.agents.llm_identity import LLMIdentityGenerator
from agentforge.llm.agents.llm_planner import LLMExecutionPlanner
from agentforge.llm.agents.llm_reviewer import LLMReviewInspector

__all__ = [
    "LLMIdentityGenerator",
    "LLMExecutionPlanner",
    "LLMReviewInspector",
]
