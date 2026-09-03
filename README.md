# LEDGER — Financial Document Intelligence Agent

LEDGER is an AI-powered financial document intelligence system designed to answer natural-language questions across a collection of financial reports.

The system ingests financial-report PDFs, understands their text and tables, retrieves relevant evidence, reasons over the retrieved information, performs numerical calculations when required, and produces answers grounded in specific document pages.

The main goal is to build a **reliable, evidence-grounded financial analyst**, rather than a simple RAG chatbot.

## System Overview

The system follows two main pipelines:

### Offline Ingestion

```text
Financial PDFs
     ↓
Document Processing
     ↓
Structured Representation
(text, tables, headings, pages, metadata)
     ↓
Chunking
     ↓
Indexing
(vector + non-vector)
```

### Online Question Answering

```text
User Question
     ↓
Orchestrator
     ↓
Reasoning Agent
     ↓
Retrieval / Table Search / Calculator
     ↓
Evidence Verification
     ↓
Structured Answer
     ↓
Answer Validator
     ↓
User
```

The system is implemented as independently runnable services:

* **Orchestrator API** — coordinates the question-answering workflow.
* **Document Processor API** — processes financial PDFs and extracts text, tables, structure, and page information.
* **Retrieval API** — performs hybrid retrieval using dense and non-vector retrieval mechanisms, followed by reranking.
* **Agent Service** — uses LangGraph to route questions, retrieve evidence, perform calculations, and generate answers.
* **Evaluation Service** — handles evaluation, experiments, and Langfuse observability.
* **UI Service** — provides the Gradio interface and dashboard.
* **Answer Validator API** — validates generated answers against the required answer schema and evidence requirements.

## Project Development

The project is organized into **two milestones**, representing two development iterations.

### Milestone 1 — Iteration 1: Foundation & Core Components

**Goal:** Build and test the major components independently while defining the interfaces and data contracts between them.

During this iteration, the team will establish:

* System architecture and service contracts
* Repository and development workflow
* PDF document processing
* Document and chunk schemas
* Chunking and indexing
* Hybrid retrieval
* Reranking
* LangGraph reasoning agent
* Strict answer schema
* Answer validation
* Gradio UI skeleton
* Langfuse observability
* TAT-DQA evaluation framework

By the end of Iteration 1, the major components should exist and be independently testable, even if some integrations still use mocks.

### Milestone 2 — Iteration 2: Integration & Final System

**Goal:** Integrate the components into a complete end-to-end LEDGER system and evaluate its performance.

During this iteration, the team will focus on:

* Integrating document processing with indexing
* Connecting the agent to retrieval
* Integrating calculation and validation
* Implementing the orchestrator
* Completing the end-to-end QA pipeline
* Completing the Gradio interface and dashboard
* Adding complete Langfuse tracing
* Running the TAT-DQA benchmark
* Running chunking, retrieval, and reranking experiments
* Performing failure analysis
* Preparing single-command startup
* Final documentation and demo preparation

The final system should support the complete workflow:

```text
Raw PDF
  → Document Processing
  → Chunking & Indexing
  → Hybrid Retrieval
  → Reranking
  → LangGraph Agent
  → Calculation / Reasoning
  → Evidence-Grounded Answer
  → Answer Validation
  → Gradio UI
```

## Dataset

The project uses the **TAT-DQA** dataset, which contains financial-report documents, questions, answers, and numerical derivations.

The original raw PDFs are used for the production ingestion pipeline. The provided parsed representations are used only as ground truth and for debugging/evaluation purposes.

## Key Requirements

LEDGER should provide:

* Corpus-wide question answering
* Understanding of both text and financial tables
* Dense and non-vector retrieval
* Reranking of retrieved evidence
* Conditional reasoning through LangGraph
* Deterministic calculation for numerical questions
* Evidence and page-level citations
* Structured and validated answers
* Handling of insufficient evidence
* Full pipeline observability through Langfuse
* Quantitative evaluation on held-out TAT-DQA data
* Failure analysis based on actual system traces

## Development Workflow

The project follows a lightweight collaborative development workflow:

```text
Issue
  ↓
Feature Branch
  ↓
Implementation
  ↓
Pull Request
  ↓
Review
  ↓
Merge into main
```

The `main` branch should remain stable, with development performed through feature branches and pull requests.

## Project Status

🚧 **Currently in Iteration 1 — Foundation & Core Components**

The immediate objective is to establish the architecture, service contracts, and independently testable components before moving into full system integration.
