# Financial Control Fabric

## AI Finance Controller — Razorpay Buildathon Track 04

**Detect → Investigate → Approve → Revalidate → Prove**

Financial Control Fabric is a production-oriented prototype for closing finance-control loops across reconciliation, settlement, merchant payouts, revenue recognition, and cross-entity accounting.

The core principle is:

> **AI investigates financial exceptions, but deterministic financial controls and humans remain authoritative.**

## The Problem

Finance teams can detect a reconciliation mismatch, but the difficult part begins afterward:

- Why did the mismatch happen?
- Which financial records explain it?
- Is it a missing event, duplicate, timing difference, fee, tax, or another root cause?
- What evidence supports the conclusion?
- Who approved the recommended action?
- Did the financial control actually pass after remediation?
- Can the final control outcome be independently verified?

Financial Control Fabric closes this loop instead of stopping at exception detection.

## What I Built

The system combines five deterministic finance controls with residual intelligence, constrained reconciliation, an evidence-grounded AI investigation controller, human approval, deterministic revalidation, and tamper-evident cryptographic control proofs.

### Five finance-control domains

1. **Nodal / Escrow reconciliation**
2. **Multi-bank / partner settlement reconciliation**
3. **Merchant payout reconciliation**
4. **Revenue recognition reconciliation**
5. **Cross-entity reconciliation**

## Control Architecture

```text
50+ / 1000+ Synthetic Financial Events
              │
              ▼
       Canonical Event Layer
              │
              ▼
      Financial Control Kernel
              │
              ▼
   Control Result + Residual Vector
              │
              ▼
   Residual Distribution Intelligence
              │
              ▼
        AI Controller
     ┌────────┴────────┐
     │                 │
 Evidence Retrieval  Hypotheses
     │                 │
     └────────┬────────┘
              ▼
          Verification
              │
              ▼
       Human Approval
              │
              ▼
   Deterministic Revalidation
              │
              ▼
             PASS
              │
              ▼
     SHA-256 Merkle Proof
              │
              ▼
          Verification
