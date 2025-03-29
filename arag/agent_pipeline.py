import concurrent.futures
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from openai import OpenAI

from arag.arag_agents import (AnswerAgent, DocumentSelectionAgent,
                              EvaluatorAgent, ImageReferencerAgent,
                              ImproverAgent, KnowledgeAgent, MissingInfoAgent,
                              ProcessAgent, QueryRewriterAgent)
from arag.prompts import PROMPTS
from arag.utils.citation_system import process_citations
from arag.utils.text_utils import (align_text_images, format_references,
                                   remove_almost_duplicates)
from arag.utils.vectordb_utils import (_get_chunks, _get_embeddings,
                                       _get_metadata)


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

        self.missing_info_agent = MissingInfoAgent(
            system_prompt=self.system_prompts["missing_info"],
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

    def _extract_knowledge(self, chunk, query):
        """Extract knowledge from a single chunk."""

        try:
            return self.knowledge_agent.perform_action(query=query, document_chunk=chunk)
        except:
            return chunk

    def extract_knowledge(self, retrieved_chunks: List[Any], query, max_workers=None):
        """
        Extract knowledge from chunks in parallel

        Args:
            retrieved_chunks: List of text chunks to process
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
                executor.submit(self._extract_knowledge, chunk, query): i for i, chunk in enumerate(retrieved_chunks)
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

    def _get_chunks_for_query(
        self, query: str, filename: str, num_chunks: int, section: str, extracted_knowledge: Set[str]
    ) -> List[str]:
        """Process a single search query and return unique chunks that aren't in extracted_knowledge and contain the section."""
        chunks = _get_chunks(
            vectordb_endopoint=self._vectordb_endpoint, query=query, filename=filename, num_chunks=num_chunks
        )
        chunks = chunks["chunks"]

        # Filter chunks that are already in extracted_knowledge or don't contain the section
        return [chunk for chunk in chunks if chunk not in extracted_knowledge and section in chunk]

    def _filter_and_process_chunk(self, args: Tuple) -> Optional[str]:
        """Process a single chunk with knowledge agent."""
        wilf, chunk = args

        try:
            extracted_knowledge = self.knowledge_agent.perform_action(query=wilf, document_chunk=chunk)
        except Exception as e:
            try:
                _knowledge_prompt = (
                    self.system_prompts["knowledge_extractor"]
                    + "\n\nYou MUST COMPRESS the information as MUCH as you can while PREVERVING THE MOST IMPORTANT PARTS!"
                )
                self.knowledge_agent.system_prompt = _knowledge_prompt
                extracted_knowledge = self.knowledge_agent.perform_action(query=wilf, document_chunk=chunk)
                self.knowledge_agent.system_prompt = self.system_prompts["knowledge_extractor"]
            except Exception as e:
                return chunk
        return extracted_knowledge

    def _process_queries_in_parallel(
        self, search_queries: List[str], filename: str, num_chunks: int, section: str, extracted_knowledge: Set[str]
    ) -> List[str]:
        """Process all search queries in parallel and return unique chunks."""
        # Create a list of tasks, each with its own argument
        tasks = []
        for query in search_queries:
            tasks.append((query, filename, num_chunks, section, extracted_knowledge))

        with concurrent.futures.ThreadPoolExecutor() as executor:
            chunks_results = list(executor.map(lambda args: self._get_chunks_for_query(*args), tasks))

        # Flatten results and remove duplicates
        _extracted = []
        for chunks in chunks_results:
            _extracted.extend(chunks)
        return list(set(_extracted))

    def _process_extraction_item(
        self, o: Any, chosen_metadata: Dict[str, Any], extracted_knowledge: Set[str], num_chunks: int
    ) -> List[str]:
        """Process a single extraction item and return extracted knowledge."""
        wilf = o.what_im_looking_for
        search_queries = self.rewrite_query(query=wilf, chosen_metadata=chosen_metadata, num_rewrites=7)
        section = o.section

        # First parallel operation: process all search queries concurrently
        _extracted = self._process_queries_in_parallel(
            search_queries, chosen_metadata["filename"], num_chunks, section, extracted_knowledge
        )

        # Second parallel operation: process all extracted chunks with knowledge agent
        if _extracted:
            # Create a list of tasks for the knowledge agent
            tasks = [(wilf, chunk) for chunk in _extracted]
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = list(executor.map(self._filter_and_process_chunk, tasks))

            return [result for result in results if result]  # Filter out empty results

        return []

    def _process_output_knowledge(self, new_knowledge: str) -> Optional[str]:
        """Process a single knowledge item and return it if valid."""
        try:
            if new_knowledge.split("\n")[1].startswith("#"):
                return new_knowledge
        except:
            pass
        return None

    def missing_info_extraction(
        self,
        missing_sections: List[Any],
        chosen_metadata: Dict[str, Any],
        extracted_knowledge: Set[str],
        num_chunks: int = 7,
    ) -> List[str]:
        """Main function to parallelize the entire knowledge extraction process."""
        # Process all extraction items in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            tasks = [(item, chosen_metadata, extracted_knowledge, num_chunks) for item in missing_sections]
            results = list(executor.map(lambda args: self._process_extraction_item(*args), tasks))

        # Flatten the results
        newly_extracted_knowledge = []
        for result_list in results:
            newly_extracted_knowledge.extend(result_list)

        # Remove duplicates and empty strings
        newly_extracted_knowledge = list(set([k for k in newly_extracted_knowledge if k != ""]))

        # Process output knowledge in parallel
        with concurrent.futures.ThreadPoolExecutor() as executor:
            processed_results = list(executor.map(self._process_output_knowledge, newly_extracted_knowledge))

        # Filter out None values and duplicates
        output_knowledge = []
        seen = set()
        for result in processed_results:
            if result and result.split("\n")[1] not in seen:
                seen.add(result.split("\n")[1])
                output_knowledge.append(result)

        return output_knowledge

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

    # Define the worker function
    def _rewrite_query(self, query, chosen_metadata):
        return self.query_rewriter.perform_action(
            query=query, summary=chosen_metadata["summary"], table_of_contents=str(chosen_metadata["table_of_contents"])
        )

    def rewrite_query(self, query, chosen_metadata, num_rewrites=5):
        """
        Parallelize the query rewriting process using ThreadPoolExecutor.

        Args:
            query (str): The original query to rewrite
            chosen_metadata (dict): Metadata containing summary and table of contents
            num_rewrites (int): Number of rewrites to perform

        Returns:
            list: Unique rewritten prompts
        """
        rewritten_prompts = []

        # Use ThreadPoolExecutor for parallel execution
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit all tasks
            future_results = [executor.submit(self._rewrite_query, query, chosen_metadata) for _ in range(num_rewrites)]

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_results):
                try:
                    result = future.result()
                    rewritten_prompts.extend(result)
                except Exception as e:
                    print(f"Error in parallel execution: {e}")

        # Return unique prompts
        return list(set(rewritten_prompts))

    def perform_action(self, query=None, action=None, outcome=None):
        """Generate narration messages for each step of the search process."""

        messages = {
            # Initialization and document selection phase
            "initialize_search": "Starting search process...",
            "extract_metadata": "Analyzing available documents...",
            "document_selection_successful": f"Selected most relevant document: {outcome}",
            # Query processing phase
            "query_rewrite_successful": "Reformulated query to better match document content",
            "retrieve_information_successful": f"Retrieved {outcome}",
            "information_extraction_successful": f"Extracted {outcome}",
            "generating_answer_successful": "Composing answer based on extracted information",
            # Evaluation and refinement phase
            "evaluate_answer_successful_iteration_1": f"Evaluating answer quality... {outcome}",
            "evaluate_answer_successful_iteration_2": f"Re-evaluating answer... {outcome}",
            "evaluate_answer_successful_iteration_3": f"Final answer evaluation... {outcome}",
            "improve_answer_successful_iteration_1": "Refining answer for accuracy and completeness",
            "improve_answer_successful_iteration_2": "Making additional improvements to answer",
            "improve_answer_successful_iteration_3": "Finalizing answer improvements",
        }

        return messages.get(action, f"Performing {action}...")

    def _process_missing_info(self, e, chosen_metadata):
        """Process a single knowledge item."""
        return self.missing_info_agent.perform_action(
            text_chunk=e,
            table_of_contents=chosen_metadata["table_of_contents"],
            file_summary=chosen_metadata["summary"],
        )

    def process_missing_info(self, extracted_knowledge, chosen_metadata, max_workers=None):
        """
        Process extracted knowledge items in parallel.

        Parameters:
        - extracted_knowledge: List of knowledge items to process
        - missing_info: The object with the perform_action method
        - chosen_metadata: Dictionary containing metadata
        - max_workers: Maximum number of worker threads (None = auto-determine based on system)

        Returns:
        - List of processed outputs
        """
        outs = []

        # Using ThreadPoolExecutor since this is likely an I/O-bound task
        # For CPU-bound tasks, use ProcessPoolExecutor instead
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create a future for each knowledge item
            future_to_item = {
                executor.submit(self._process_missing_info, e, chosen_metadata): e for e in extracted_knowledge
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_item):
                try:
                    result = future.result()
                    outs.extend(result)
                except Exception as exc:
                    item = future_to_item[future]
                    print(f"Processing of {item} generated an exception: {exc}")

        return outs

    def search(self, query: str) -> str:
        # Extract metadata from available documents
        self._update_status(
            "metadata_extract", self.process_agent.perform_action(query=query, action="extract_metadata")
        )

        metadata = _get_metadata(self._vectordb_endpoint)

        # Select the most relevant document
        chosen_file = self.document_selection_agent.perform_action(query=query, files_metadata=metadata)
        self._update_status(
            "doc_select",
            self.process_agent.perform_action(query=query, action="document_selection_successful", outcome=chosen_file),
        )

        for m in metadata:
            if m["filename"] == chosen_file:
                chosen_metadata = m
                break

        # Rewrite query for better retrieval
        rewritten_prompts = self.rewrite_query(query=query, chosen_metadata=chosen_metadata, num_rewrites=7)

        self._update_status(
            "query_refine",
            self.process_agent.perform_action(
                query=query, action="query_rewrite_successful", outcome=rewritten_prompts
            ),
        )

        # Retrieve relevant document chunks
        retrieved_chunks = self.retrieve_chunks(prompts=rewritten_prompts, filename=chosen_file, num_chunks=5)

        self._update_status(
            "chunk_retrieve",
            self.process_agent.perform_action(
                query=query, action="retrieve_information_successful", outcome=f"{len(retrieved_chunks)} chunks found"
            ),
        )

        # Extract knowledge from chunks
        extracted_knowledge = self.extract_knowledge(retrieved_chunks=retrieved_chunks, query=query, max_workers=8)

        self._update_status(
            "knowledge_extract",
            self.process_agent.perform_action(
                query=query,
                action="information_extraction_successful",
                outcome=f"{len(extracted_knowledge)} pieces of knowledge extracted",
            ),
        )

        # Check for missing information
        missing_sections = self.process_missing_info(
            extracted_knowledge=extracted_knowledge, chosen_metadata=chosen_metadata
        )

        missing_knowledge = self.missing_info_extraction(
            missing_sections=missing_sections,
            chosen_metadata=chosen_metadata,
            extracted_knowledge=extracted_knowledge,
            num_chunks=7,
        )

        extracted_knowledge.extend(missing_knowledge)
        extracted_knowledge = remove_almost_duplicates(extracted_knowledge)

        merged_knowledge = "\n".join(extracted_knowledge)

        # Generate initial answer
        answer = self.answer_agent.perform_action(query=query, document_chunks=extracted_knowledge)
        self._update_status(
            "answer_generate", self.process_agent.perform_action(query=query, action="generating_answer_successful")
        )

        answer = align_text_images(answer)

        try:
            answer = format_references(
                process_citations(
                    answer=answer, text_chunks=merged_knowledge, threshold=0.4, get_embeddings_func=_get_embeddings
                )
            ).strip()
        except Exception as e:
            pass

        return answer