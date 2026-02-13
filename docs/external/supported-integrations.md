# Supported Integrations

Vanna supports more than 30 providers across AI models, databases, and vector stores. This guide lists all available integrations and explains how to configure each type.

## Integration Types

Vanna uses three types of integrations:

- **LLM Services**: AI models that generate SQL from natural language.
- **SQL Runners**: Database connectors that execute generated SQL.
- **Vector Stores**: Memory backends that store training data for similarity search.

Each integration implements a standard interface, so you can swap providers without changing application logic.

## AI Model Providers (LLM Services)

Vanna supports the following AI model providers for SQL generation:

| Provider | Package | Description |
|----------|---------|-------------|
| Anthropic (Claude) | `vanna[anthropic]` | Claude models for high-quality SQL generation. |
| OpenAI | `vanna[openai]` | GPT models including GPT-4. |
| Google (Gemini) | `vanna[google]` | Google Gemini models. |
| Azure OpenAI | `vanna[azure]` | OpenAI models hosted on Azure. |
| AWS Bedrock | `vanna[bedrock]` | Multiple model providers via AWS Bedrock. |
| Mistral | `vanna[mistral]` | Mistral AI models. |
| Ollama | `vanna[ollama]` | Run open-source models locally. |

### Configuring an LLM Service

Each LLM service follows the same pattern:

```python
from vanna.integrations.anthropic import ClaudeLlmService

llm_service = ClaudeLlmService(
    api_key="your-api-key",
    model="claude-sonnet-4-5"
)
```

Replace the import and parameters with values specific to your chosen provider.

## Database Connectors (SQL Runners)

Vanna can connect to a wide range of databases:

| Database | Package | Description |
|----------|---------|-------------|
| MySQL | `vanna[mysql]` | MySQL 5.6 and later. |
| PostgreSQL | `vanna[postgres]` | PostgreSQL 10 and later. |
| Snowflake | `vanna[snowflake]` | Snowflake Data Warehouse. |
| BigQuery | `vanna[bigquery]` | Google BigQuery. |
| DuckDB | `vanna[duckdb]` | In-process analytical database. |
| SQLite | `vanna[sqlite]` | Embedded SQLite databases. |
| Oracle | `vanna[oracle]` | Oracle Database. |
| Microsoft SQL Server | `vanna[mssql]` | SQL Server and Azure SQL. |

### Configuring a SQL Runner

Each database connector follows the same interface:

```python
from vanna.integrations.mysql import MySQLRunner

sql_runner = MySQLRunner(
    host="localhost",
    database="mydb",
    user="user",
    password="password"
)
```

### Using Read-Only Access

For safety, use a read-only runner to prevent accidental data modification:

```python
from vanna.integrations.mysql import ReadOnlyMySQLRunner

sql_runner = ReadOnlyMySQLRunner(
    host="localhost",
    database="mydb",
    user="readonly_user",
    password="password"
)
```

Read-only runners wrap the standard runner and block any write operations. This is recommended for production environments.

## Vector Store Providers (Agent Memory)

Vector stores power Vanna's training data and similarity search:

| Provider | Package | Description |
|----------|---------|-------------|
| ChromaDB | `vanna[chromadb]` | Recommended local vector store with persistent storage. |
| Qdrant | `vanna[qdrant]` | High-performance vector database. |
| FAISS | `vanna[faiss]` | Facebook AI Similarity Search. |
| Pinecone | `vanna[pinecone]` | Managed vector database service. |
| Weaviate | `vanna[weaviate]` | Open-source vector search engine. |

### Configuring a Vector Store

ChromaDB is recommended for most deployments:

```python
from vanna.integrations.chromadb import ChromaAgentMemory

agent_memory = ChromaAgentMemory(
    persist_directory="./vanna_memory"
)
```

Data stored in ChromaDB persists across server restarts. The `persist_directory` controls where data are saved on disk.

## Installing Integration Packages

### Install All Integrations

To install Vanna with all available integrations:

```bash
pip install vanna[all]
```

### Install Specific Integrations

Install only the integrations you need:

```bash
# Install with MySQL and Anthropic support
pip install vanna[mysql,anthropic]

# Install with PostgreSQL and ChromaDB
pip install vanna[postgres,chromadb]

# Install with Snowflake, OpenAI, and Pinecone
pip install vanna[snowflake,openai,pinecone]
```

## Combining Integrations

A typical Vanna setup combines one provider from each category:

```python
from vanna import Agent, AgentConfig
from vanna.integrations.anthropic import ClaudeLlmService
from vanna.integrations.mysql import ReadOnlyMySQLRunner
from vanna.integrations.chromadb import ChromaAgentMemory

# AI model
llm_service = ClaudeLlmService(
    api_key="your-api-key",
    model="claude-sonnet-4-5"
)

# Database
sql_runner = ReadOnlyMySQLRunner(
    host="localhost",
    database="mydb",
    user="readonly_user",
    password="password"
)

# Memory
agent_memory = ChromaAgentMemory(
    persist_directory="./vanna_memory"
)

# Create agent with all three
agent = Agent(
    config=AgentConfig(
        name="SQL Assistant",
        model="claude-sonnet-4-5"
    ),
    llm_service=llm_service,
    sql_runner=sql_runner,
    agent_memory=agent_memory
)
```

## Choosing Integrations

### Selecting an AI Model

Consider the following factors:

- **Accuracy**: Claude and GPT-4 produce the highest quality SQL.
- **Speed**: Smaller models (for example, Claude Haiku) respond faster.
- **Cost**: Local models via Ollama eliminate API costs.
- **Privacy**: Local models keep data on your infrastructure.

### Selecting a Database Connector

Use the connector that matches your database. If you need read-only access (recommended for production), check that a read-only variant is available for your database.

### Selecting a Vector Store

- **ChromaDB**: Best for most deployments. Simple setup, persistent storage, no external service needed.
- **Pinecone**: Best for managed, scalable deployments without infrastructure management.
- **Qdrant**: Best for high-performance requirements.
- **FAISS**: Best for in-memory use cases where persistence is not required.

## Related Topics

- [Getting Started with Vanna](getting-started.md): Initial setup and configuration.
- [Training Vanna with Query Examples](training-data.md): Add training data to improve accuracy.
- [Configuring Vanna for Your Database](domain-configuration.md): Define business rules and conventions.
