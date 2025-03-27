from pydantic import BaseModel

from .decorators import register_action
from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class KnowledgeSchema(BaseModel):
    knowledge: str


class KnowledgeAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, document_chunk: str) -> str:
        prompt = f"<user_query>{query}</user_query>\n"
        prompt += f"<document_chunk>{document_chunk}</document_chunk>"

        return prompt

    @register_action(action_name="action-knowledge")
    def perform_action(self, query: str, document_chunk: str) -> str:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query, document_chunk=document_chunk),
            structured_output_schema=KnowledgeSchema,
            temperature=0.0,
        )

        return response.knowledge, usage_metadata
