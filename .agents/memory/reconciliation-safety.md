---
name: Reconciliation safety
description: Financial invariants for deterministic many-to-many settlement allocation.
---

Reconciliation must optimize only integer-scaled monetary units and must
reject mixed-currency batches before calculating totals.

**Why:** CP-SAT requires integer decision variables, while financial amounts
must remain exact; scaling Decimal values avoids float rounding. Aggregating
different currencies into one result would create a misleading financial
total without an explicit FX capability.

**How to apply:** Keep scale conversion lossless and deterministic, validate
capacity on both sides after solving, and run each currency as an isolated
reconciliation scope until explicit FX support is designed.