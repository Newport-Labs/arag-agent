from pydantic import BaseModel

from .decorators import register_action
from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class ImproverSchema(BaseModel):
    improved_answer: str


class ImproverAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, knowledge_chunks: str, original_answer: str, feedback: str) -> str:
        prompt = f"<query>{query}</query>\n"
        prompt += f"<knowledge_chunks>{knowledge_chunks}</knowledge_chunks>\n"
        prompt += f"<original_answer>{original_answer}/original_answer>\n"
        prompt += f"<feedback>{feedback}</feedback>"

        return prompt

    @register_action(action_name="action-improve")
    def perform_action(self, query: str, original_answer: str, knowledge_chunks: str, feedback: str) -> str:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(
                query=query, original_answer=original_answer, knowledge_chunks=knowledge_chunks, feedback=feedback
            ),
            structured_output_schema=ImproverSchema,
        )

        return response.improved_answer, usage_metadata