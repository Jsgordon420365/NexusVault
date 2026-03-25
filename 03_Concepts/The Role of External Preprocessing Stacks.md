---
id: 20260325021422-1e44
title: "**The Role of External Preprocessing Stacks**"
created: 2026-03-25
type: atomic-concept
status: permanent
source: "[[source_document.md]]"
confidence: high
author: agentic-pipeline-v3
tags: [assimilated, granular-memory, legal-standard]
---

# **The Role of External Preprocessing Stacks**

A critical architectural principle is that significant extraction and transformation workloads should occur outside Obsidian before the data is imported. Obsidian is a text editor, not an extraction pipeline. Python scripts orchestrating tools like Whisper for audio transcription, layout-aware optical character recognition models for document parsing, and LangChain for structural formatting act as the necessary gatekeepers of the vault.30 Similarly, heavy embedding indexing for vector databases should run as an external daemon watching the vault directory, ensuring that the core Obsidian application remains lightweight and responsive.51

---
**Provenance**
Source: [[source_document.md]]
Processed: 2026-03-25T02:14:22.962254
Granularity: Level 3