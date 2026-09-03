---
name: Controller safety
description: Guardrails for the evidence-grounded Finance Controller layer.
---

The controller may investigate and recommend, but only bounded read-only tools
and deterministic Decimal calculators may establish financial facts.

**Why:** An LLM must not become the source of financial truth or gain a path to
database writes, arbitrary code, payments, accounting entries, or approvals.
Separating retrieval, calculation, verification, and human approval makes
uncertainty explicit.

**How to apply:** Keep provider interfaces unable to execute tools directly,
require evidence and calculation references for supported findings, leave all
financial-impacting actions pending until an explicit controller decision, and
revalidate the deterministic control afterward.