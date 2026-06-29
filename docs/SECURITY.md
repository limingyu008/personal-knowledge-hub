# Security Notes

## Local-first Assumption

The current MVP is designed for personal local use. It does not include authentication, authorization, multi-user isolation, or public network hardening.

Do not expose the backend service directly to the public internet.

## Secrets

Do not commit:

- API keys
- `.env` files
- model provider credentials
- personal documents
- SQLite runtime database
- Chroma runtime data

Use `.env.example` as a template only.

## Data Privacy

Runtime knowledge data is stored under `backend/data/` by default and is excluded from Git. Before publishing screenshots or demo data, make sure they do not contain private personal information.

## Browser Extension

The extension can read page content to save selected knowledge and insert generated context into AI input boxes. Review extension permissions before publishing to a browser extension store.

## Network Access

External network calls may happen when:

- Using Chat model test or future Chat features
- Using Embedding model for vector retrieval
- Using MinerU service for document parsing

Always verify the configured service endpoint before sending private documents or knowledge.
