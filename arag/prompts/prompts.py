from .answer import ANSWER
from .concise_answer import CONCISE_ANSWER
from .decision import DECISION
from .default import DEFAULT
from .evaluator import EVALUATOR
from .formatter import FORMATTER
from .improver import IMPROVER
from .knowledge import KNOWLEDGE
from .knowledge_gaps import KNOWLEDGE_GAPS
from .missing_info import MISSING_INFO
from .query_rewrite import QUERY_REWRITE

PROMPTS = {
    "default": DEFAULT,
    "query_rewrite": QUERY_REWRITE,
    "knowledge_gaps": KNOWLEDGE_GAPS,
    "decision": DECISION,
    "answer": ANSWER,
    "evaluator": EVALUATOR,
    "improver": IMPROVER,
    "knowledge": KNOWLEDGE,
    "missing_info": MISSING_INFO,
    "formatter": FORMATTER,
    "concise_answer": CONCISE_ANSWER

}