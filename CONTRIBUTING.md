## GitHub Workflow

We use a simple **Issue → Branch → PR → Review → Merge** workflow.

```text
Issue → Feature Branch → Pull Request → Review → main
```

### 1. Issues

Every task must have a GitHub Issue and belong to one of the two milestones:

- **Iteration 1 — Foundation & Core Components**
- **Iteration 2 — Integration & Final System**

Issue format:

```text
[Service] Short description
```

Examples:

```text
[Retrieval] Implement BM25 retrieval
[Agent] Implement LangGraph router
[UI] Build document dashboard
[Integration] Connect agent to retrieval
```

Each Issue should include a short description, requirements, acceptance criteria, and dependencies if any.

---

### 2. Branches

Create **one branch per Issue/feature**, not one branch per team member or service.

Format:

```text
feature/<short-description>
```

Examples:

```text
feature/bm25-retrieval
feature/langgraph-router
feature/pdf-processing
feature/answer-validator
```

Bug fixes:

```text
fix/<short-description>
```

Create branches from the latest `main`.

---

### 3. Commits

Keep commits small and descriptive.

Format:

```text
<type>: <description>
```

Examples:

```text
feat: add BM25 retrieval
fix: preserve page metadata
test: add retrieval tests
docs: update API contract
```

---

### 4. Pull Requests

Every branch must be merged through a PR.

PR title:

```text
[Service] Short description
```

Example:

```text
[Retrieval] Implement BM25 retrieval
```

PRs must:

- Link to the Issue
- Explain what changed
- Mention how it was tested
- Have **at least one team-member review**
- Contain no unrelated changes

---

### 5. `main` Integrity

`main` is protected.

```text
❌ No direct pushes
❌ No force pushes

✅ PR required
✅ Review required
```

Only merge working, tested changes into `main`.

After merging, delete the feature branch.

---

### 6. Dependencies

If an Issue depends on another Issue, document it:

```text
Depends on: #12
```

Dependencies should not unnecessarily block development. If the interface is agreed upon, use mocks/stubs and work in parallel.

---


### 7. Keeping Your Branch Updated

If `main` changes while you are working, update your branch before opening or merging your PR.

Recommended:

```bash
git checkout main
git pull origin main

git checkout feature/<your-feature>
git merge main
```

Resolve any conflicts locally, test again, and push the updated branch.

For this short project, prefer simple Git operations over complicated branching strategies.

---


### Golden Rule

> **Every change is traceable to an Issue, every Issue has its own branch, and nothing goes directly into ****main****.**
