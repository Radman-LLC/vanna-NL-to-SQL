# Architecture Overview

This page provides a high-level overview of how Vanna processes natural language questions and generates SQL queries. Understanding the architecture helps you configure and customize Vanna effectively.

## How Vanna Works

Vanna uses an agent-based architecture to convert user questions into SQL. The agent coordinates multiple components, each with a specific responsibility, to produce accurate and secure results.

### Request Flow

When a user asks a question, the following steps occur:

1. **User submits a question** through the chat interface.
2. **The agent receives the question** and begins processing.
3. **Memory search** retrieves similar past queries for context.
4. **Context enhancement** adds relevant examples and business rules to the AI prompt.
5. **The AI model generates SQL** based on the enhanced prompt.
6. **Permission check** validates the user can execute the requested tool.
7. **SQL execution** runs the generated query against your database.
8. **Results are returned** to the user through the interface.

## Core Components

### Agent

The agent is the central orchestrator. It manages conversation flow, coordinates between components, and handles tool execution. You configure the agent with your choice of AI model, database connector, and optional enhancements.

### LLM Service

The LLM Service connects Vanna to an AI model provider. It sends the user's question (along with context) to the model and receives generated SQL. Vanna supports multiple providers including Anthropic Claude, OpenAI, Google Gemini, and others.

### SQL Runner

The SQL Runner executes generated SQL against your database and returns results. Each supported database has its own runner implementation. For production use, read-only runners are available to prevent accidental data modification.

### Agent Memory

Agent Memory stores training data and past successful queries in a vector database. When a new question arrives, the memory system performs similarity search to find relevant examples. These examples are injected into the AI prompt to improve accuracy.

### Tool Registry

The Tool Registry manages available tools and enforces user permissions. Each tool declares which user groups can access it. The registry validates permissions before allowing tool execution, ensuring secure operation.

## Customization Points

Vanna provides several ways to customize behavior without modifying code:

### Domain Configuration

Define business terms, SQL conventions, performance hints, and data quality rules in a configuration file. Vanna uses this context when generating SQL.

**Example:** Define what "active customer" means in your business so Vanna generates the correct WHERE clause.

### Training Data

Add question-and-SQL pairs to memory so Vanna can learn from proven examples. The more relevant examples you provide, the more accurate SQL generation becomes.

### Lifecycle Hooks

Attach hooks that run before or after specific events (for example, before a message is processed, after a tool executes). Use hooks for logging, monitoring, or custom validation.

### Context Enrichers

Add custom data to tool execution context. Use enrichers to inject user-specific information, environment details, or dynamic configuration.

### Error Recovery

Define custom error handling strategies. When a tool execution fails, the recovery strategy determines how Vanna responds (for example, retry, suggest corrections, or notify the user).

## Streaming Responses

Vanna supports streaming responses, which means results appear progressively in the user interface as they are generated. This provides a responsive experience, especially for complex queries that take time to generate.

The streaming system sends user interface components (text, charts, data tables, status cards) as they become available, rather than waiting for the entire response to complete.

## Security Model

Vanna implements multiple security layers:

- **User authentication**: Identify users through configurable resolvers.
- **Group-based access control**: Restrict tools to specific user groups.
- **Read-only database access**: Use read-only connectors to prevent data modification.
- **SQL validation**: Configurable validation rules for generated SQL.

## Related Topics

- [Getting Started with Vanna](getting-started.md): Initial setup and configuration.
- [Supported Integrations](supported-integrations.md): Available AI models, databases, and vector stores.
- [User Permissions and Access Control](user-permissions.md): Configure access control.
- [Configuring Vanna for Your Database](domain-configuration.md): Define business rules and conventions.
