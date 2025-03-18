import concurrent.futures
import json
from typing import Any, Callable, List, Optional

from openai import OpenAI

from arag.arag_agents import (AnswerAgent, ConciseAnswerAgent, DecisionAgent,
                              EvaluatorAgent, FormatterAgent, ImproverAgent,
                              KnowledgeAgent, KnowledgeGapsAgent,
                              MissingInfoAgent, QueryRewriterAgent)
from arag.arag_agents.utils.memory_layer import AgentMemory
from arag.prompts import PROMPTS
from arag.utils.text_utils import (align_text_images, extract_section,
                                   fix_path_formatting, has_similar_vector,
                                   perform_similarity_search)


class ARag:
    def __init__(
        self,
        api_key: str,
        user_id: str,
        vectordb_endopoint: str = "http://localhost:5000/api/query",
        status_callback: Optional[Callable[[str, str], Any]] = None,
    ) -> None:
        self.system_prompts = PROMPTS
        self.model = "gemini-2.0-flash"
        self._vectordb_endpoint = vectordb_endopoint
        self.status_callback = status_callback
        self.user_id = user_id
        self._evaluator_decision = False
        self._evaluator_max_retry = 3
        self.memory = AgentMemory()
        self._retrieved_chunks_embeddings = []

        self._init_client(api_key=api_key)
        self._init_agents()

    def _update_status(self, state: str, message: str) -> None:
        """Send status updates to the frontend during processing"""
        if self.status_callback:
            self.status_callback(state, message)

    def _init_client(self, api_key: str):
        self.openai_client = OpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    def _init_agents(self) -> None:
        self.query_rewrite_agent = QueryRewriterAgent(
            system_prompt=self.system_prompts["query_rewrite"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.missing_info_agent = MissingInfoAgent(
            system_prompt=self.system_prompts["missing_info"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.knowledge_agent = KnowledgeAgent(
            system_prompt=self.system_prompts["knowledge"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.decision_agent = DecisionAgent(
            system_prompt=self.system_prompts["decision"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.answer_agent = AnswerAgent(
            system_prompt=self.system_prompts["answer"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.concise_answer_agent = ConciseAnswerAgent(
            system_prompt=self.system_prompts["concise_answer"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.evaluator_agent = EvaluatorAgent(
            system_prompt=self.system_prompts["evaluator"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.improver_agent = ImproverAgent(
            system_prompt=self.system_prompts["improver"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.knowledge_gaps_agent = KnowledgeGapsAgent(
            system_prompt=self.system_prompts["knowledge_gaps"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.formatter_agent = FormatterAgent(
            system_prompt=self.system_prompts["formatter"],
            openai_client=self.openai_client,
            model=self.model,
        )

    def _rewrite_queries(self, query: str) -> str:
        self._update_status(
            "action-rewrite",
            f"I understand your question: {query}. To help find the most relevant information, I'll break this down into multiple focused search queries. This approach increases our chances of finding useful results by targeting different aspects of your question.",
        )
        rewritten_queries = self.query_rewrite_agent.perform_action(query=query)
        self._update_status(
            "action-rewrite",
            f"I've analyzed your question and broken it down into {len(rewritten_queries)} different search queries. This should help us cover various aspects of your question and find more comprehensive information.",
        )

        return rewritten_queries

    def _retrieve_chunks(self, queries: List[str], num_chunks: Optional[int] = 3) -> List[str]:
        self._update_status(
            "action-retrieve",
            "I'm now going to retrieve data chunks that are conceptually similar to our target information. This involves using advanced matching techniques to find closely related pieces of data that can provide additional context, insights, or support the main query.",
        )

        chunks, chunks_embedding = perform_similarity_search(
            vectordb_endopoint=self._vectordb_endpoint, queries=queries, threshold=1.0, num_chunks=num_chunks
        )

        self._update_status(
            "action-retrieve",
            f"Great news! I've found {len(chunks)} relevant data chunks that closely match our search criteria. These chunks will help provide comprehensive insights and additional context to our original query.",
        )

        if len(self._retrieved_chunks_embeddings) == 0:
            self._retrieved_chunks_embeddings = chunks_embedding

            return chunks
        else:
            new_chunks = []

            for chunk, chunk_embedding in zip(chunks, chunks_embedding):
                if has_similar_vector(chunk_embedding, self._retrieved_chunks_embeddings, threshold=1.0):
                    continue

                self._retrieved_chunks_embeddings.append(chunk_embedding)
                new_chunks.append(chunk)

            return new_chunks

    def _fill_missing_sections(self, query: str, chunk: List[str]) -> bool:
        self._update_status(
            "action-missing-info",
            "I'll now extract and fill the gaps in the referenced sections from the retrieved data chunks to provide a more comprehensive understanding of our query.",
        )

        missing_sections = self.missing_info_agent.perform_action(query=query, chunk=chunk)
        missing_sections = [
            (m.referenced_section, extract_section(m.referenced_section), m.extraction_query) for m in missing_sections
        ]

        # Check if there are any missing sections to process
        if len(missing_sections) == 0:
            return False

        def process_missing_section(section_data):
            exact_section, section, section_query = section_data
            # Get the enriched chunk
            try:
                enriched_chunks, _ = perform_similarity_search(
                    vectordb_endopoint=self._vectordb_endpoint,
                    queries=[section_query],
                    threshold=1.0,
                    section=section,
                    num_chunks=1,
                )

                enriched_chunks = [
                    f"Section {exact_section} - {section_query}\n\n" + enriched_chunk
                    for enriched_chunk in enriched_chunks
                ]
                # Process the enriched chunk with knowledge extraction
                self._update_status(
                    "action-info-extraction",
                    "I'll now analyze the data chunks to extract meaningful insights, synthesize key information, and form a comprehensive knowledge base that provides deeper understanding of our query.",
                )
                self._knowledge(query=section_query, chunks=enriched_chunks)
            except Exception as e:
                pass

        # Process all missing sections in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_missing_section, section_data) for section_data in missing_sections]

            # Wait for all futures to complete
            _ = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Return True because we had missing sections to process
        return True

    def _knowledge(self, query: str, chunks: List[str]) -> None:
        def process_chunk(chunk):
            return self.knowledge_agent.perform_action(query=query, chunk=chunk)

        # Process all chunks in parallel
        extracted_knowledge = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_chunk, chunk) for chunk in chunks]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Flatten the list of lists into a single list
        for knowledge_items in results:
            extracted_knowledge.extend(knowledge_items)

        self.memory.update(extracted_knowledge)

    def _decision(self, query: str) -> str:
        knowledge = self.memory.retrieve()

        decision = self.decision_agent.perform_action(query=query, knowledge=knowledge)

        if decision == "answer":
            self._update_status(
                "action-decision",
                "The gathered information provides a comprehensive and robust understanding of our query, covering key aspects and offering substantive insights.",
            )
        else:
            self._update_status(
                "action-decision",
                "The current data chunks reveal gaps in our understanding. We'll need additional sources or more detailed information to develop a comprehensive view of the query.",
            )

        return decision

    def answer_loop(self, query: str):
        knowledge = self.memory.retrieve()
        draft_answer = self._answer(query=query, knowledge=knowledge)
        knowledge_added = self._fill_missing_sections(query=query, chunk=draft_answer)

        if knowledge_added:
            knowledge = self.memory.retrieve()
            answer = self._answer(query=query, knowledge=knowledge)
        else:
            answer = draft_answer

        current_idx = 0

        while not self._evaluator_decision and current_idx < self._evaluator_max_retry:
            self._update_status(
                "action-evaluate",
                "I'm carefully reviewing the drafted response, critically assessing its clarity, accuracy, and completeness against our original research goals.",
            )
            evaluation = self.evaluator_agent.perform_action(query=query, knowledge=knowledge, answer=answer)

            if json.loads(evaluation)["approval"] == "yes":
                break

            self._update_status(
                "action-improve",
                "I'll refine the current draft, incorporating insights and addressing any identified gaps to enhance the overall quality and depth of the response.",
            )
            answer = self.improver_agent.perform_action(
                query=query, answer=answer, evaluation=evaluation, knowledge=knowledge
            )

        answer = self.format_answer(query=query, text=answer)

        return fix_path_formatting(align_text_images(answer)).strip()

    def _fill_knowledge_gaps(
        self,
        query: str,
    ) -> None:
        knowledge = self.memory.retrieve()

        self._update_status(
            "action-knowledge-gaps",
            "I'll now systematically identify and fill the knowledge gaps by cross-referencing available information, seeking additional context, and exploring alternative sources to create a more comprehensive understanding.",
        )

        queries, _ = self.knowledge_gaps_agent.perform_action(query=query, knowledge=knowledge)

        def process_single_query(new_query):
            rewritten_query = self._rewrite_queries(query=new_query)
            chunks = self._retrieve_chunks(queries=rewritten_query, num_chunks=2)

            self._update_status(
                "action-info-extraction",
                "I'll now analyze the data chunks to extract meaningful insights, synthesize key information, and form a comprehensive knowledge base that provides deeper understanding of our query.",
            )
            return self._knowledge(query=new_query, chunks=chunks)

        # Run all queries in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(process_single_query, new_query) for new_query in queries]

            # Wait for all futures to complete
            _ = [future.result() for future in concurrent.futures.as_completed(futures)]

    def format_answer(self, query: str, text: str) -> str:
        self._update_status(
            "action-format",
            "I will make sure that the answer is correctly formatted.",
        )
        text = self.formatter_agent.perform_action(query=query, text=text)

        return text

    def _answer(self, query: str, knowledge: str) -> str:
        self._update_status(
            "action-answer",
            "I'll now draft an initial response based on the synthesized information, creating a comprehensive and coherent overview of our query.",
        )

        try:
            answer = self.answer_agent.perform_action(query=query, knowledge=knowledge)
        except Exception as e:
            answer = self.concise_answer_agent.perform_action(query=query, knowledge=knowledge)

        return answer

    def search(self, query: str) -> str:
        # For the moment, we clear the agent memory at the beggining of each asnwer.
        self.memory.reset()

        # Step 1: Rewrite query
        rewritten_queries = self._rewrite_queries(query=query)

        # Step 2: Retrieve relevant chunks
        chunks = self._retrieve_chunks(queries=rewritten_queries, num_chunks=3)

        # Step 3: Now, form knowledge/facts from retrieved chunks
        self._update_status(
            "action-info-extraction",
            "I'll now analyze the data chunks to extract meaningful insights, synthesize key information, and form a comprehensive knowledge base that provides deeper understanding of our query.",
        )
        self._knowledge(query=query, chunks=chunks)

        # Step 4: Decide to enrich or to respond
        decision = self._decision(query=query)

        if decision == "answer":
            return self.answer_loop(query=query)

        # Provide the final answer. This can be a while loop, but due to budget constrains, it's fine how it is now.
        return self.answer_loop(query=query)
