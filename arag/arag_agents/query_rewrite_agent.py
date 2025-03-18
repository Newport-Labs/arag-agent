from typing import List

from decorators.agent_registry import register_action
from pydantic import BaseModel

from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class QueryRewriterSchema(BaseModel):
    rewritten_queries: List[str]


class QueryRewriterAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str) -> str:
        return f"<query>\n{query}\n</query>"

    @register_action(action_name="action-rewrite")
    def perform_action(self, query: str) -> List[str]:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query),
            structured_output_schema=QueryRewriterSchema,
        )

        rewritten_queries = response.rewritten_queries
        rewritten_queries.append(query)

        return rewritten_queries, usage_metadata
