from typing import Literal

from pydantic import BaseModel

from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class ContentReferencerSchema(BaseModel):
    decision: Literal["yes", "no"]


class ContentReferencerAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, context: str) -> str:
        prompt = f"<fact>\n{query}\n</fact>\n\n"
        prompt += f"<knowledge_context>\n{context}\n</knowledge_context>"

        return prompt

    def perform_action(self, query: str, context: str) -> str:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query, context=context),
            structured_output_schema=FactReferencerSchema,
        )

        return response.decision, usage_metadata