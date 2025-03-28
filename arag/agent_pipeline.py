import concurrent.futures
from typing import Any, Callable, List, Optional

from openai import OpenAI

from arag.arag_agents import (AnswerAgent, DocumentSelectionAgent,
                              EvaluatorAgent, ImageReferencerAgent,
                              ImproverAgent, KnowledgeAgent, ProcessAgent,
                              QueryRewriterAgent)
from arag.prompts import PROMPTS
from arag.utils.citation_system import process_citations
from arag.utils.text_utils import (align_text_images, fix_markdown_tables,
                                   format_references)
from arag.utils.vectordb_utils import _get_chunks, _get_metadata


class ARag:
    def __init__(
        self,
        api_key: str,
        user_id: str,
        vectordb_endopoint: str = "http://localhost:5000/api",
        status_callback: Optional[Callable[[str, str], Any]] = None,
    ) -> None:
        self.system_prompts = PROMPTS
        self.model = "gemini-2.0-flash"
        self._vectordb_endpoint = vectordb_endopoint
        self.status_callback = status_callback
        self.user_id = user_id

        self._retrieved_knowledge = []

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
        self.query_rewriter = QueryRewriterAgent(
            system_prompt=self.system_prompts["query_rewrite"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.knowledge_agent = KnowledgeAgent(
            system_prompt=self.system_prompts["knowledge_extractor"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.answer_agent = AnswerAgent(
            system_prompt=self.system_prompts["answer"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.evaluator_agent = EvaluatorAgent(
            system_prompt=self.system_prompts["improver"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.improver_agent = ImproverAgent(
            system_prompt=self.system_prompts["improver"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.process_agent = ProcessAgent(
            system_prompt=self.system_prompts["process"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.image_referencer_agent = ImageReferencerAgent(
            system_prompt=self.system_prompts["images_integrator"],
            openai_client=self.openai_client,
            model=self.model,
        )

        self.document_selection_agent = DocumentSelectionAgent(
            system_prompt=self.system_prompts["document_selection"],
            openai_client=self.openai_client,
            model=self.model,
        )

    def _extract_knowledge(self, chunk, query, knowledge_agent):
        """Extract knowledge from a single chunk."""

        try:
            return knowledge_agent.perform_action(query=query, document_chunk=chunk)
        except:
            return chunk

    def extract_knowledge(self, output_chunks: List[Any], query, knowledge_agent, max_workers=None):
        """
        Extract knowledge from chunks in parallel

        Args:
            output_chunks: List of text chunks to process
            query: Query to use for knowledge extraction
            knowledge_agent: Agent that extracts knowledge
            max_workers: Maximum number of worker threads for chunk processing

        Returns:
            List of extracted knowledge chunks
        """
        extracted_knowledge = []

        # Use ThreadPoolExecutor for chunk processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit extraction tasks for each chunk
            future_to_chunk = {
                executor.submit(self._extract_knowledge, chunk, query, knowledge_agent): i
                for i, chunk in enumerate(output_chunks)
            }

            # Collect results as they complete (maintains original order)
            for future in concurrent.futures.as_completed(future_to_chunk):
                chunk_idx = future_to_chunk[future]
                try:
                    result = future.result()
                    # Ensure we maintain the original order
                    while len(extracted_knowledge) <= chunk_idx:
                        extracted_knowledge.append(None)
                    extracted_knowledge[chunk_idx] = result
                except Exception as exc:
                    print(f"Chunk {chunk_idx} generated an exception: {exc}")

        # Remove any None values (in case some chunks failed)
        extracted_knowledge = [k for k in extracted_knowledge if k is not None]
        extracted_knowledge = [k.strip() for k in extracted_knowledge if k != ""]

        return extracted_knowledge

    def _retrieve_chunks(self, prompt, filename, num_chunks):
        chunks = _get_chunks(
            vectordb_endopoint=self._vectordb_endpoint, query=prompt, filename=filename, num_chunks=num_chunks
        )
        return chunks["chunks"]

    def retrieve_chunks(self, prompts, filename, num_chunks):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Create a list of futures
            future_to_prompt = {
                executor.submit(self._retrieve_chunks, prompt, filename, num_chunks): prompt for prompt in prompts
            }

            # Collect results as they complete
            all_chunks = []
            for future in concurrent.futures.as_completed(future_to_prompt):
                chunks = future.result()
                all_chunks.extend(chunks)

        # Remove duplicates
        return list(set(all_chunks))

    def search(self, query: str) -> str:
        # Add initialization action
        self._update_status(
            "action-initialize", self.process_agent.perform_action(query=query, action="initialize_search")
        )

        # Continue with extract metadata
        self._update_status(
            "action-extract-metadata", self.process_agent.perform_action(query=query, action="extract_metadata")
        )

        metadata = _get_metadata(self._vectordb_endpoint)

        chosen_file = self.document_selection_agent.perform_action(query=query, files_metadata=metadata)
        self._update_status(
            "action-document-selection",
            self.process_agent.perform_action(query=query, action="document_selection_successful", outcome=chosen_file),
        )

        for m in metadata:
            if m["filename"] == chosen_file:
                chosen_metadata = m
                break

        # Add status update for query rewriting
        rewritten_prompts = self.query_rewriter.perform_action(
            query=query, summary=chosen_metadata["summary"], table_of_contents=str(chosen_metadata["table_of_contents"])
        )
        self._update_status(
            "action-rewrite",
            self.process_agent.perform_action(
                query=query, action="query_rewrite_successful", outcome=rewritten_prompts
            ),
        )

        # Add status update for chunk retrieval
        retrieved_chunks = self.retrieve_chunks(prompts=rewritten_prompts, filename=chosen_file, num_chunks=3)
        self._update_status(
            "action-retrieve",
            self.process_agent.perform_action(
                query=query, action="retrieve_information_successful", outcome=f"{len(retrieved_chunks)} chunks found"
            ),
        )

        # Add status update for knowledge extraction
        extracted_knowledge = self.extract_knowledge(
            output_chunks=retrieved_chunks, query=query, knowledge_agent=self.knowledge_agent, max_workers=4
        )
        self._update_status(
            "action-info-extraction",
            self.process_agent.perform_action(
                query=query,
                action="information_extraction_successful",
                outcome=f"{len(extracted_knowledge)} pieces of knowledge extracted",
            ),
        )

        merged_knowledge = "\n".join(extracted_knowledge)

        # Add status update for answer generation
        answer = self.answer_agent.perform_action(query=query, document_chunks=extracted_knowledge)
        self._update_status(
            "action-answer", self.process_agent.perform_action(query=query, action="generating_answer_successful")
        )

        _loop_count = 0

        # Add evaluation and improvement loop
        while _loop_count <= 3:
            improvement_decision, feedback = self.evaluator_agent.perform_action(
                query=query, knowledge_chunks=merged_knowledge, answer=answer
            )
            self._update_status(
                "action-evaluate",
                self.process_agent.perform_action(
                    query=query,
                    action=f"evaluate_answer_successful_iteration_{_loop_count + 1}", 
                    outcome=f"Improvement needed: {not improvement_decision}"
                ),
            )

            # Add status update for improvement
            answer = self.improver_agent.perform_action(
                query=query, original_answer=answer, knowledge_chunks=merged_knowledge, feedback=feedback
            )

            if improvement_decision and _loop_count != 0:
                break

            self._update_status(
                "action-improve",
                self.process_agent.perform_action(
                    query=query,
                    action=f"improve_answer_successful_iteration_{_loop_count + 1}", 
                    outcome="Answer improved based on feedback"
                ),
            )
            _loop_count += 1

        _answer = answer

        for knowledge in extracted_knowledge:
            a = self.image_referencer_agent.perform_action(answer=_answer, section=knowledge)

            if a != "":
                _answer = a
        answer = fix_markdown_tables(align_text_images(_answer))

        return format_references(process_citations(answer=answer,
                                                   text_chunks=merged_knowledge,
                                                   threshold=0.5))
