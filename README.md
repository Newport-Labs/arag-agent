# 🤖 ARAG - Advanced Retrieval Augmented Generation Agent

ARAG is an agent-based pipeline for retrieval-augmented generation (RAG) focused on technical documentation. It uses multiple specialized agents to analyze queries, retrieve relevant information, extract knowledge, and generate comprehensive answers.

## ✨ Features

- 🧠 **Multi-agent architecture**: Specialized agents for different parts of the RAG process
- 🔍 **Query rewriting**: Transforms user queries into multiple optimized search queries for better retrieval
- 📚 **Knowledge extraction**: Extracts relevant facts and information from retrieved documentation
- 🧩 **Knowledge gap identification**: Identifies missing information needed for complete answers
- ✅ **Answer evaluation and improvement**: Reviews answers for quality and accuracy, then improves them
- 📊 **Process visualization**: Provides real-time feedback about the system's internal processes

## 📦 Installation

### Requirements

- 🐍 Python 3.10 or newer
- 🔑 Google AI API key

### Install from PyPI

```bash
pip install arag
```

### Install from source

```bash
git clone https://github.com/Newport-Labs/arag-agent.git
cd arag-agent
pip install -e .
```

## 🚀 Quick Start

```python
from arag import ARag

# Initialize the ARag agent
arag_agent = ARag(
    api_key="your_google_ai_api_key",  # Google AI API key
    user_id="user123",                 # Unique user identifier
    vectordb_endopoint="http://localhost:5000/api/query",  # Vector database endpoint
    status_callback=optional_callback_function  # Optional callback for status updates
)

# Generate an answer
answer = arag_agent.search("How do I adjust the park brake on a CAT 320E excavator?")
print(answer)
```

## ⚙️ Configuration

ARAG requires the following configuration parameters:

- `api_key`: Your Google AI API key (using Gemini models)
- `user_id`: A unique identifier for the user (used for tracking and logging)
- `vectordb_endopoint`: The endpoint URL for your vector database service
- `status_callback`: (Optional) A function to receive real-time status updates

## 📡 Status Callback

You can provide a callback function to receive real-time updates on the agent's progress:

```python
def status_update(state, message):
    print(f"[{state}] {message}")

arag_agent = ARag(
    api_key="your_api_key",
    user_id="user123",
    status_callback=status_update
)
```

The callback will receive two parameters:
- `state`: The current state of the agent (e.g., "action-rewrite", "action-retrieve")
- `message`: A detailed message about what the agent is doing

## 🏗️ Architecture

ARAG uses a pipeline of specialized agents:

1. 🔄 **Query Rewriter Agent**: Transforms user questions into optimized search queries
2. 🧠 **Knowledge Agent**: Extracts factual information from retrieved documents
3. 🧩 **Missing Info Agent**: Identifies references to external information needed for completeness
4. 🔍 **Knowledge Gaps Agent**: Identifies what information is still missing from the knowledge base
5. 🤔 **Decision Agent**: Determines if enough information has been gathered to answer the question
6. 📝 **Answer Agent**: Creates comprehensive answers based on gathered knowledge
7. 🔍 **Evaluator Agent**: Assesses answer quality against predefined criteria
8. 🔧 **Improver Agent**: Enhances answers based on evaluation feedback
9. 📊 **Process Agent**: Provides narrative about the system's internal processes

## 💾 Vector Database Requirements

ARAG requires a vector database with the following API endpoints:

- GET `/api/query`: For retrieving chunks based on semantic search
  - Parameters: `query` (string), `num_returns` (int), optional `section` (string)
  
- POST `/api/embed`: For embedding text (used internally)
  - Parameters: `text` (string)

## 🔬 Advanced Usage

### 📜 Custom System Prompts

ARAG uses a set of default system prompts for each agent, but you can customize them by modifying the prompts in the `arag/prompts` directory.

### 🧠 Memory Management

ARAG includes an `AgentMemory` class that maintains the knowledge extracted throughout the session:

```python
# Access the agent's memory
knowledge = arag_agent.memory.retrieve()

# Reset the agent's memory for a new session
arag_agent.memory.reset()
```

## 📄 License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

---

🏢 Developed by Newport Solutions - https://newport.ro
