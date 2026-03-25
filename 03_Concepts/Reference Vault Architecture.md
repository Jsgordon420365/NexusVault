---
id: 20260325021422-89fa
title: "**Reference Vault Architecture**"
created: 2026-03-25
type: atomic-concept
status: permanent
source: "[[source_document.md]]"
confidence: high
author: agentic-pipeline-v3
tags: [assimilated, granular-memory, legal-standard]
---

# **Reference Vault Architecture**

| Directory/Layer | Function and Content | Machine Utility |
| :---- | :---- | :---- |
| **01\_Inbox / Raw** | The initial landing zone for raw web clips, unprocessed transcripts, and untriaged fleeting thoughts.30 | Low. Usually excluded from vector indexing to prevent context pollution and noise generation. |
| **02\_Sources** | Immutable Markdown representations of external media, including books, podcasts, and research PDFs. | Medium. Indexed for deep factual retrieval, but heavily weighted to ensure models cite the source rather than summarizing it. |
| **03\_Evergreen / Concepts** | Atomic, highly synthesized knowledge notes. These are heavily linked and represent the core persistent memory.17 | Very High. The primary target for semantic retrieval and cross-tool reasoning via the Model Context Protocol. |
| **04\_Working Context** | Domain-specific project files containing the current state, active tasks, and recent architectural decisions.16 | Critical. Actively read by the agent at the initialization of every session to establish current state and eliminate amnesia.16 |
| **05\_System / Metadata** | Storage for templates, Dataview querying scripts, automation logs, and prompt libraries. | Low for contextual reasoning, high for deterministic pipeline execution. |

---
**Provenance**
Source: [[source_document.md]]
Processed: 2026-03-25T02:14:22.902051
Granularity: Level 3