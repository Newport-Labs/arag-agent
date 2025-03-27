from pydantic import BaseModel

from .decorators import register_action
from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class EvaluatorSchema(BaseModel):
    needs_improvement: bool
    improvement_areas: str


class EvaluatorAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(self, query: str, knowledge_chunks: str, answer: str) -> str:
        prompt = f"<query>{query}</query>\n"
        prompt += f"<knowledge_chunks>{knowledge_chunks}</knowledge_chunks>\n"
        prompt += f"<answer>{answer}</answer>\n"

        return prompt

    @register_action(action_name="action-evaluate")
    def perform_action(self, query: str, knowledge_chunks: str, answer: str) -> str:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(query=query, knowledge_chunks=knowledge_chunks, answer=answer),
            structured_output_schema=EvaluatorSchema,
        )

        return (response.needs_improvement, response.improvement_areas), usage_metadata