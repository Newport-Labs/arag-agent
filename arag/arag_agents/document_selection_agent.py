from typing import List

from pydantic import BaseModel

from .decorators import register_action
from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class DocumentSelectionSchema(BaseModel):
    filename: str


class DocumentSelectionAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, files_metadata: List[dict]) -> str:
        prompt = f"<query>{query}</query>\n<documents>\n"

        for file_metadata in files_metadata:
            prompt += f"<document>\n<filename>{file_metadata['filename']}</filename>\n<summary>{file_metadata['summary']}</summary>\n</document>\n"

        prompt += "</documents>"
        return prompt

    @register_action(action_name="action-document-selection")
    def perform_action(self, query: str, files_metadata: List[dict]) -> List[str]:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query, files_metadata=files_metadata),
            structured_output_schema=DocumentSelectionSchema,
            temperature=0.0,
        )

        return response.filename, usage_metadata
