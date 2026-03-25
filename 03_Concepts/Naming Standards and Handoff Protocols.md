---
id: 20260325021422-2146
title: "**Naming Standards and Handoff Protocols**"
created: 2026-03-25
type: atomic-concept
status: permanent
source: "[[source_document.md]]"
confidence: high
author: agentic-pipeline-v3
tags: [assimilated, granular-memory, legal-standard]
---

# **Naming Standards and Handoff Protocols**

While traditional Zettelkasten systems frequently utilize dense, numerical timestamps for file names to ensure uniqueness, these obscure strings severely impair a language model's ability to perform semantic retrieval based on file titles. The optimal approach is a composite naming convention that utilizes natural language titles paired with status indicators, while relegating unique identifiers to the YAML frontmatter.27

To solve the inherent statelessness of conversational artificial intelligence sessions, the vault must utilize a structured handoff protocol. At the conclusion of a session, the model must be prompted to write a structured summary to a dedicated handoff file in the vault root, detailing what tasks were completed, which files require human review, and the explicit next steps.16 The subsequent session begins by programmatically reading this exact file, enabling continuous, cross-session workflows without context degradation.

---
**Provenance**
Source: [[source_document.md]]
Processed: 2026-03-25T02:14:22.904792
Granularity: Level 3