from typing import Literal

from pydantic import BaseModel

from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class ImageReferencerSchema(BaseModel):
    image_reference_present: bool
    page: int
    type: Literal["Picture", "Figure"]
    type_number: int

class ImageReferencerAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, context: str) -> str:
        prompt = f"<query>\n{query}\n</query>\n\n"
        prompt += f"<text>\n{context}\n</text>"

        return prompt

    def perform_action(self, query: str, context: str) -> str:
        response, _ = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query, context=context),
            structured_output_schema=ImageReferencerSchema,
        )

        return response.image_reference_present, response.page, response.type, response.type_number
