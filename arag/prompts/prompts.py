from .answer import ANSWER
from .citation_integrator import CITATION_INTEGRATOR
from .default import DEFAULT
from .document_selection import DOCUMENT_SELECTION
from .images_integrator import IMAGE_INTEGRATOR
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
    "citation_integrator": CITATION_INTEGRATOR,
    "document_selection": DOCUMENT_SELECTION,
}