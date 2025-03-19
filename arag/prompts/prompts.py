from .answer import ANSWER
from .concise_answer import CONCISE_ANSWER
from .content_referencer import CONTENT_REFERENCER
from .decision import DECISION
from .default import DEFAULT
from .evaluator import EVALUATOR
from .image_referencer import IMAGE_REFERENCER
from .improver import IMPROVER
from .knowledge import KNOWLEDGE
from .knowledge_gaps import KNOWLEDGE_GAPS
from .missing_info import MISSING_INFO
from .process import PROCESS
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
    "concise_answer": CONCISE_ANSWER,
    "process": PROCESS,
    "image_referencer": IMAGE_REFERENCER,
    "content_referencer": CONTENT_REFERENCER
}