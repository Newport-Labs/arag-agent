from typing import List

from decorators.agent_registry import register_action
from pydantic import BaseModel

from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class KnowledgeSchema(BaseModel):
    knowledge: List[str]


class KnowledgeAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, chunk: List[str]) -> str:
        prompt = f"<query>\n{query}\n</query>\n\n"
        prompt += f"<documentation_text>\n{chunk}\n</documentation_text>"

        return prompt

    @register_action(action_name="action-knowledge")
    def perform_action(self, query: str, chunk: str) -> str:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query, chunk=chunk),
            structured_output_schema=KnowledgeSchema,
        )

        return response.knowledge, usage_metadata
