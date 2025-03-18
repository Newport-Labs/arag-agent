from typing import List

import tiktoken


class AgentMemory:
    def __init__(self) -> None:
        self._memories = []
        self._tokenizer = tiktoken.get_encoding("o200k_base")

    def update(self, memories: List[str]) -> None:
        for memory in memories:
            if memory != "" or len(self._tokenizer.encode(memory)) < 4096:
                self._memories.append(memory)

    def _memory_pattern(self, memories: List[str]) -> str:
        output_memories = ""

        for memory in memories:
            output_memories += f"<knowledge>\n{memory}\n</knowledge>\n\n"

        return output_memories.strip()

    def retrieve(self) -> str:
        return self._memory_pattern(self._memories)

    def reset(self) -> None:
        self._memories = []
