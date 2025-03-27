from pydantic import BaseModel

from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class ImageReferencerSchema(BaseModel):
    enhanced_response: str


class ImageReferencerAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, answer: str, section: str) -> str:
        prompt = f"<answer>{answer}</answer>\n"
        prompt += f"<section>{section}</section>"

        return prompt

    def perform_action(self, answer: str, section: str) -> str:
        response, _ = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(answer=answer, section=section),
            structured_output_schema=ImageReferencerSchema,
            temperature=0.0,
        )

        return response.enhanced_response
    