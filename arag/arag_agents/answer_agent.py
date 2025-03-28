from typing import List

from pydantic import BaseModel

from .decorators import register_action
from .template_agent import BaseAgent
from .utils.agent_primitives import client_message, client_sturctured_message


class AnswerAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, document_chunks: List[str], conversation_summary: str = None) -> str:
        prompt = (
            f"<conversation_summary>{conversation_summary}</conversation_summary>\n"
            if conversation_summary is not None
            else ""
        )
        prompt += f"<user_query>{query}</user_query>\n<document_chunks>\n"

        for document_chunk in document_chunks:
            prompt += f"<document_chunk>{document_chunk}</document_chunk>\n"

        prompt += "</document_chunks>"

        return prompt

    @register_action(action_name="action-answer")
    def perform_action(self, query: str, document_chunks: List[str], conversation_summary: str = None) -> str:
        response, usage_metadata = client_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model + "-thinking-exp",
            user_message=self._message(
                query=query, document_chunks=document_chunks, conversation_summary=conversation_summary
            )
        )

        return response, usage_metadata