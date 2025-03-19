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

    def _message(self, answer: str, evaluation: str, knowledge: str) -> str:
        prompt = f"<answer>\n{answer}\n</answer>\n\n" + knowledge + "\n\n"
        prompt += f"<evaluation>\n{evaluation}\n</evaluation>\n\n"

        return prompt

    @register_action(action_name="action-improve")
    def perform_action(self, query: str, answer: str, evaluation: str, knowledge: str) -> str:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(answer=answer, evaluation=evaluation, knowledge=knowledge),
            structured_output_schema=ImproverSchema,
        )

        return response.improved_answer, usage_metadata
