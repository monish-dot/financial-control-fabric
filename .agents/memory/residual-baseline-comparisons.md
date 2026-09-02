---
name: Residual baseline comparisons
description: Why residual baselines retain representative samples alongside summary statistics.
---

Exact KS, Wasserstein, and PSI comparisons cannot be reconstructed from summary
statistics alone.

**Why:** Residual intelligence must compare a current population with the
baseline distribution, not only compare means or variances. Persisting the
baseline's residual sample alongside its statistics keeps those comparisons
deterministic without introducing an ML model.

**How to apply:** When extending baseline storage or retention policies, keep
enough Decimal-preserving population information to recompute the required
distribution metrics; never silently substitute only mean/variance summaries.