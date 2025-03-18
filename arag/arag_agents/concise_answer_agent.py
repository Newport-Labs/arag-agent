from pydantic import BaseModel

from .decorators import register_action
from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class ConciseAnswerSchema(BaseModel):
    answer: str


class ConciseAnswerAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, knowledge: str) -> str:
        prompt = f"<query>\n{query}\n</query>\n\n"

        return prompt + knowledge

    @register_action(action_name="action-concise-answer")
    def perform_action(self, query: str, knowledge: str) -> str:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query, knowledge=knowledge),
            structured_output_schema=ConciseAnswerSchema,
        )

        return response.answer, usage_metadata
