from typing import List

from pydantic import BaseModel

from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class MissingInfoSubSchema(BaseModel):
    reference_context: str
    what_im_looking_for: str
    extraction_query: List[str]
    section: str


class MissingInfoSchema(BaseModel):
    missing_information: List[MissingInfoSubSchema]


class MissingInfoAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, text_chunk: str, table_of_contents: str, file_summary: str) -> str:
        prompt = f"<text_chunk>{text_chunk}</text_chunk>\n"
        prompt += f"<table_of_contents>{table_of_contents}</table_of_contents>\n"
        prompt += f"<file_summary>{file_summary}</file_summary>"

        return prompt

    def perform_action(self, text_chunk: str, table_of_contents: str, file_summary: str) -> List[str]:

        response, _ = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(
                text_chunk=text_chunk, table_of_contents=table_of_contents, file_summary=file_summary
            ),
            structured_output_schema=MissingInfoSchema,
            temperature=0.0,
        )

        return response.missing_information
