from typing import List

from pydantic import BaseModel

from .decorators import register_action
from .template_agent import BaseAgent
from .utils.agent_primitives import client_sturctured_message


class QueryRewriterSchema(BaseModel):
    rewritten_queries: List[str]


class QueryRewriterAgent(BaseAgent):
    def __init__(self, system_prompt: str, openai_client, model: str = "gemini-2.0-flash") -> None:
        self.system_prompt = system_prompt
        self.openai_client = openai_client
        self.model = model

    def _message(
        self,
        query: str,
        table_of_contents: str,
        summary: str,
        previous_queries: List[str] = None,
        conversation_summary: str = None,
    ) -> str:
        prompt = f"<user_query>{query}</user_query>\n<table_of_contents>{table_of_contents}</table_of_contents>\n<summary>{summary}</summary>"

        if previous_queries is not None:
            for previous_query in previous_queries:
                prompt += f"\n<previous_queries>{str(previous_query)}</previous_queries>"

        if conversation_summary is not None:
            prompt += f"\n<conversation_summary>{conversation_summary}</conversation_summary>"

        return prompt

    @register_action(action_name="action-rewrite")
    def perform_action(
        self,
        query: str,
        table_of_contents: str,
        summary: str,
        previous_queries: List[str] = None,
        conversation_summary: str = None,
    ) -> List[str]:
        response, usage_metadata = client_sturctured_message(
            system_message=self.system_prompt,
            openai_client=self.openai_client,
            model=self.model,
            user_message=self._message(
                query=query,
                table_of_contents=table_of_contents,
                summary=summary,
                previous_queries=previous_queries,
                conversation_summary=conversation_summary,
            ),
            structured_output_schema=QueryRewriterSchema,
            temperature=0.0,
        )

        rewritten_queries = response.rewritten_queries
        rewritten_queries.append(query)

        return rewritten_queries, usage_metadata
