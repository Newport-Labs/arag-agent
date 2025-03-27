from typing import Optional

from pydantic import BaseModel

from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class ProcessSchema(BaseModel):
    narration: str


class ProcessAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, action: str, outcome: Optional[str] = None) -> str:
        prompt = ""

        prompt += f"<action>\n{action}\n</action>\n\n"
        prompt += f"<input>\n{query}\n</input>\n\n"

        if outcome is not None:
            prompt += f"<outcome>\n{outcome}\n</outcome>"

        return prompt.strip()

    def perform_action(self, query: str, action: str, outcome: Optional[str] = None) -> str:
        response, _ = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query, action=action, outcome=outcome),
            structured_output_schema=ProcessSchema,
        )

        return response.narration
