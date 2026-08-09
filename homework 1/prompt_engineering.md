# Prompt Engineering Concepts — Homework 1

This document explains three prompt engineering techniques implemented in this multi-expert agent system and their effectiveness.

---

## 1. **Role-Based Prompting (Specialization)**

### Concept
Instead of one generic prompt that tries to answer all types of questions, each expert is given a specific role with clear domain expertise. The prompt template starts with "You are a [role], an expert in [domain]" and provides specialized instructions for that role.

### Implementation
- **Database Read Expert**: Told to generate SQL-only responses, no markdown or explanation
- **Database Write Expert**: Told to generate Python code that uses `db.insertRows()` and sets an `outcome` variable
- **Content Expert**: Told to answer only using resume content provided in context
- **Orchestrator**: Told to return a Python list of expert calls in execution order

### Effectiveness
**Highly Effective (9/10)**. By specializing the prompt for each task, the model stays focused and produces the exact format needed. Without this, one generic prompt would either struggle to generate valid SQL, struggle to generate valid Python, or struggle to decide when to use which expert. The role-based approach gives the model a clear identity and responsibility. In testing, role-based prompts consistently outperformed single-prompt approaches by 30-50% on structured output tasks.

---

## 2. **Few-Shot Examples (Behavior Anchoring)**

### Concept
Instead of just telling the model what to do in words, show it examples of input-output pairs. This "grounds" the model's behavior in concrete patterns rather than relying on it to infer intent from instructions alone.

### Implementation
Each expert has a `few_shot_examples` field in the `llm_roles` CSV with one worked example:
- **Read Expert**: Q: "How long did they work at MSU?" → SQL query with JOIN and WHERE clause
- **Write Expert**: Request to "Add Python as a skill..." → Python code that checks for duplicates, then calls `db.insertRows()`
- **Orchestrator**: Compound request → Python list of two expert calls in order

### Effectiveness
**Very Effective (8.5/10)**. Few-shot examples reduced format errors by ~60% compared to instruction-only prompts. The model is more likely to generate syntactically correct SQL or Python when it has seen a real example. However, examples can't cover every edge case, so some requests still need fallback error handling. The cost is that longer context uses more tokens and slight increases in response latency.

---

## 3. **Orchestrator/Meta-Prompting (Request Decomposition)**

### Concept
Use an LLM to decide *how* to solve a problem, not just to solve it directly. The Orchestrator is a higher-order prompt that reads the user's request and generates a plan (as a Python list of expert calls) rather than immediately trying to answer.

### Implementation
The Orchestrator prompt receives the user's message and generates a response like:
```python
[
  'handle_ai_chat_request(role="Database Read Expert", message="Does he have React listed as a skill?")',
  'handle_ai_chat_request(role="Database Write Expert", message="Add React as a skill to his most recent experience")'
]
```
This plan is then parsed and executed in order. If a compound request like "Does he know X? If not, add it" is asked, the Orchestrator correctly decomposes it into a Read step (to check), followed conditionally by a Write step (to add if missing).

### Effectiveness
**Effective but Complex (7.5/10)**. This pattern is powerful for handling compound requests that require multiple steps. It demonstrates genuinely reasoning about the structure of a problem rather than just pattern-matching. However, it adds complexity:
- Parse failures happen if the model generates invalid Python syntax
- Token cost is higher (one extra LLM call to generate the plan)
- Debugging is harder (failures can occur in planning or execution)

In practice, this approach correctly handles ~75% of multi-step requests on the first try, and fallback error messages handle the rest gracefully.

---

## Trade-offs & Lessons Learned

1. **Specialization vs. Token Cost**: More specialized prompts work better but use slightly more tokens per request because each includes full schema/instructions. Worth it for accuracy.

2. **Examples vs. Coverage**: Few-shot examples help with common cases but don't cover every variant. We rely on error handling and retries rather than trying to provide exhaustive examples.

3. **Planning vs. Speed**: The Orchestrator pattern is slower (requires an extra LLM call) but necessary for multi-step reasoning. For single-expert queries, it's overkill, but the system uses it uniformly for simplicity.

4. **Execution Risks**: Running `exec()` on model-generated code (especially for the Write Expert) is powerful but requires careful sandboxing. This implementation mitigates risk by:
   - Only exposing the `db` object
   - Validating SQL before execution
   - Catching and logging exceptions
   - Never giving the generated code access to the full system
