---
name: lab-knowledge-base
description: Query and explain the CCU Bioinformatics Lab knowledge base for long-read cancer genomics, LongPhase tools, somatic benchmarking, phasing, purity/ploidy, copy number, LOH, local datasets, evaluator semantics, and related lab research context. Use when the user asks a question that may depend on this lab's domain knowledge, workflows, terminology, data locations, or implementation contracts.
---

# Lab Knowledge Base

Use the local read-only knowledge base at:

`/Users/wang/Documents/Codex/2026-09-09/1-x20/lab-knowledge-base`

## Workflow

1. Read `INDEX.md` and `catalog/topics.json` only as needed to identify the most relevant topic semantically. Do not rely solely on literal keyword matching; the user may ask in Chinese or use a full natural-language question.
2. Read the selected topic's `topics/<id>/INDEX.md` hub. Use its routing table to select the smallest relevant leaf node, then read that leaf. Read additional leaves or source nodes only when necessary to answer accurately.
3. For a quick alias lookup, `python3 scripts/kb.py find-topic <short-term>` is available. For branch resolution, use `python3 scripts/kb.py route <topic-id> <branch>`.
4. Ground the answer in the knowledge-base content. Preserve distinctions such as FACT, IMPLEMENTED CONTRACT, POLICY, PROPOSED, and UNKNOWN; do not present proposals or historical snapshots as current facts.
5. When useful, cite the relevant local Markdown files with absolute clickable paths.

## Safety and freshness

- Treat the repository as read-only unless the user explicitly asks to edit it.
- Never push, open a pull request, or otherwise change GitHub based merely on a knowledge-base question.
- Local filesystem locators may only work on the lab server. State that limitation when a referenced path cannot be accessed locally.
- If a question depends on current code, current external data, or a source marked stale/unverified, explain the boundary and inspect the authoritative source only when it is available and the user has authorized the required access.
