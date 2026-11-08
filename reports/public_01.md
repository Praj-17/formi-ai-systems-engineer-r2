# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.345 | +1.1% | 0.243 | -0.8% | 0.502 | +2.0% | 14% | 53 (57) |
| nw_kyc | 0.373 | +1.8% | 0.245 | +1.3% | 0.600 | +0.5% | 9% | 32 (21) |
| nw_renewal | 0.437 | +5.0% | 0.263 | -0.4% | 0.567 | +4.7% | 19% | 47 (54) |
| ALL | 0.382 | +2.7% | 0.250 | -0.3% | 0.544 | +2.7% | 15% | 132 (132) |

## Changes applied by the controller

21 applied — neutral: 7, beneficial: 7, harmful: 7

- ks_cancel v2 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v2 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- nw_kyc v2 (controller_approved) dims=['voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_auto) dims=['voice'] engageΔ=+0.018 didΔ=+0.000 → **beneficial**
- nw_renewal v3 (controller_approved) dims=['voice'] engageΔ=-0.000 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- ks_cancel v4 (controller_auto) dims=['voice'] engageΔ=-0.004 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_approved) dims=['voice'] engageΔ=-0.000 didΔ=+0.000 → **neutral**
- nw_renewal v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.030 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_approved) dims=['voice'] engageΔ=+0.008 didΔ=+0.000 → **neutral**
- ks_cancel v6 (controller_auto) dims=['welcome_message'] engageΔ=-0.020 didΔ=+0.000 → **harmful**
- nw_renewal v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.004 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_auto) dims=['welcome_message'] engageΔ=+0.010 didΔ=+0.000 → **beneficial**
- nw_renewal v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.110 didΔ=+0.000 → **beneficial**
- ks_cancel v8 (controller_approved) dims=['welcome_message'] engageΔ=-0.013 didΔ=+0.000 → **harmful**
- ks_cancel v9 (controller_approved) dims=['voice'] engageΔ=+0.063 didΔ=+0.000 → **beneficial**
- nw_renewal v8 (controller_approved) dims=['welcome_message'] engageΔ=-0.017 didΔ=+0.000 → **harmful**
- ks_cancel v10 (controller_auto) dims=['voice'] engageΔ=-0.015 didΔ=+0.000 → **harmful**
- nw_renewal v9 (controller_approved) dims=['welcome_message'] engageΔ=-0.022 didΔ=+0.000 → **harmful**
- ks_cancel v11 (controller_auto) dims=['voice'] engageΔ=-0.013 didΔ=+0.000 → **harmful**
- ks_cancel v12 (controller_auto) dims=['voice'] engageΔ=-0.010 didΔ=+0.000 → **harmful**

## Governance

```
{
  "approval_requests": 20,
  "decisions": {
    "approved": 13,
    "rejected": 7,
    "expired": 0
  },
  "rejection_reasons": {
    "prompt changes need evidence.validation_run_id for this workflow and prompt": 7
  },
  "applied_via_approval": 13,
  "auto_applied": 8,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 3,
    "nw_kyc": 2,
    "ks_cancel": 2
  }
}
```

## Incidents

```
[]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:welcome_message=W3": {
    "6": 0.639,
    "7": 0.628
  }
}
```

Credits used: 61 · validation runs: 8 · LLM fix calls: 7