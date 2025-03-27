from .answer import ANSWER
from .default import DEFAULT
from .document_selection import DOCUMENT_SELECTION
from .evaluator import EVALUATOR
from .images_integrator import IMAGE_INTEGRATOR
from .improver import IMPROVER
from .knowledge import KNOWLEDGE_EXTRACTOR
from .process import PROCESS
from .query_rewrite import QUERY_REWRITE

PROMPTS = {
    "default": DEFAULT,
    "query_rewrite": QUERY_REWRITE,
    "process": PROCESS,
    "knowledge_extractor": KNOWLEDGE_EXTRACTOR,
    "answer": ANSWER,
    "images_integrator": IMAGE_INTEGRATOR,
    "evlauator": EVALUATOR,
    "improver": IMPROVER,
    "document_selection": DOCUMENT_SELECTION,
}