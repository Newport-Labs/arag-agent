from typing import List

from decorators.agent_registry import register_action
from pydantic import BaseModel

from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class MissingInfoSubSchema(BaseModel):
    referenced_section: str
    extraction_query: str


class MissingInfoSchema(BaseModel):
    sections: List[MissingInfoSubSchema]


class MissingInfoAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, content: str) -> str:
        return f"<content>\n{content}\n</content>"

    @register_action(action_name="action-missing-info")
    def perform_action(self, query: str, chunk: str) -> List[str]:

        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(content=chunk),
            structured_output_schema=MissingInfoSchema,
        )

        return response.sections, usage_metadata
