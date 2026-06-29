# Product PRD

## 1. Product Positioning

Personal Knowledge Hub is a local-first AI knowledge workspace for individuals who frequently use AI tools.

It helps users maintain personal knowledge, project context, historical decisions, documents, and web content, then turns that information into controllable context for AI conversations.

## 2. Target Users

Initial seed users:

- Knowledge workers who frequently use Doubao, Tongyi, DeepSeek, ChatGPT, Claude, or other Web AI tools
- Developers and technical managers
- Independent makers who need to manage ideas, project context, and decisions
- Users who care about local data ownership and privacy

## 3. Core Problems

Current Web AI tools often lack personal context:

- The AI does not know the user's background
- Important project decisions are scattered across notes, documents, chats, and web pages
- Users repeatedly explain the same context
- Retrieved context is hard to inspect and debug
- Personal knowledge is not connected as entities and relationships

## 4. MVP Scope

### Knowledge Library

- Create, edit, delete knowledge items
- Import manual notes, web pages, and files
- Parse TXT, Markdown, PDF, and Word documents
- Split content into chunks
- Maintain tags, source, summary, and status

### Processing Queue

- Show processing status
- Record imported document processing result
- Prepare for future pipeline steps such as summary, tags, entity extraction, relation extraction, and embeddings

### Knowledge Graph

- Display graph nodes and edges
- Show entity and relationship details
- Distinguish confirmed and pending relationships

### Context Debug Console

- Input a question
- Retrieve relevant knowledge
- Inspect hit reasons and scores
- Generate a final context prompt
- Copy or use the context in Web AI tools

### Model Configuration

- Configure Chat model and Embedding model separately
- Support OpenAI-compatible APIs
- Support local parser and MinerU parser switch
- Support keyword retrieval and vector retrieval switch

### Browser Extension

- Connect to local backend
- Save current page content
- Generate context from the local knowledge hub
- Insert context into Web AI input boxes
- Fall back to local IndexedDB when backend is unavailable

## 5. Non-goals for MVP

- Multi-user account system
- Cloud sync
- Payment
- Permission system
- Mobile app
- Enterprise deployment
- Full task queue framework

## 6. Success Criteria

- A user can run the full system locally within 10 minutes
- A user can import documents and web content
- A user can generate inspectable AI context from local knowledge
- A user can use the browser extension with existing Web AI tools
- No private local runtime data is required in the repository

## 7. Future Direction

- Real processing pipeline worker
- AI summary and tagging
- Entity and relation extraction
- Knowledge graph editing and review
- Better vector retrieval and hybrid retrieval
- Context compression and prompt templates
- Local LLM support
- Multi-device sync as an optional paid feature
