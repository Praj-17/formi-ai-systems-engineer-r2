# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.342 | +0.0% | 0.245 | +0.0% | 0.492 | +0.0% | 0% | 57 (57) |
| nw_kyc | 0.367 | +0.0% | 0.242 | +0.0% | 0.597 | +0.0% | 0% | 21 (21) |
| nw_renewal | 0.416 | +0.0% | 0.264 | +0.0% | 0.542 | +0.0% | 0% | 54 (54) |
| ALL | 0.372 | +0.0% | 0.251 | +0.0% | 0.530 | +0.0% | 0% | 132 (132) |

## Changes applied by the controller

0 applied — 


## Governance

```
{
  "approval_requests": 3,
  "decisions": {
    "rejected": 3,
    "expired": 0
  },
  "rejection_reasons": {
    "prompt changes need evidence.validation_run_id for this workflow and prompt": 3
  },
  "applied_via_approval": 0,
  "auto_applied": 0,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 1,
    "ks_cancel": 1
  }
}
```

## Incidents

```
[]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{}
```

Credits used: 24 · validation runs: 3 · LLM fix calls: 3