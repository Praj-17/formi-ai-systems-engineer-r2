# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.286 | +21.5% | 0.207 | +14.5% | 0.485 | +3.6% | 17% | 94 (348) |
| nw_kyc | 0.372 | -0.4% | 0.236 | +0.6% | 0.603 | -1.0% | 16% | 19 (29) |
| nw_renewal | 0.447 | +3.3% | 0.265 | +1.2% | 0.565 | +1.8% | 18% | 76 (54) |
| ALL | 0.358 | +8.3% | 0.233 | +6.1% | 0.539 | +1.2% | 17% | 189 (431) |

## Changes applied by the controller

23 applied — neutral: 11, harmful: 5, beneficial: 7

- ks_cancel v2 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_kyc v2 (controller_approved) dims=['voice'] engageΔ=+0.009 didΔ=+0.000 → **neutral**
- ks_cancel v3 (controller_auto) dims=['voice'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- nw_renewal v2 (controller_approved) dims=['voice'] engageΔ=+0.005 didΔ=+0.000 → **neutral**
- ks_cancel v4 (controller_auto) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nw_renewal v3 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.016 didΔ=+0.000 → **harmful**
- ks_cancel v5 (controller_auto) dims=['welcome_message'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_approved) dims=['voice'] engageΔ=-0.021 didΔ=+0.000 → **harmful**
- ks_cancel v7 (controller_auto) dims=['welcome_message'] engageΔ=+0.010 didΔ=+0.000 → **neutral**
- nw_renewal v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.036 didΔ=+0.000 → **beneficial**
- ks_cancel v8 (controller_approved) dims=['prompt_version'] engageΔ=+0.102 didΔ=+0.000 → **beneficial**
- nw_renewal v6 (controller_approved) dims=['prompt_version'] engageΔ=+0.049 didΔ=+0.000 → **beneficial**
- nw_kyc v4 (controller_approved) dims=['prompt_version'] engageΔ=+0.030 didΔ=+0.000 → **beneficial**
- nw_renewal v7 (controller_approved) dims=['welcome_message'] engageΔ=-0.007 didΔ=+0.000 → **neutral**
- nw_renewal v8 (controller_approved) dims=['welcome_message'] engageΔ=+0.143 didΔ=+0.000 → **beneficial**
- nw_renewal v10 (controller_approved) dims=['voice'] engageΔ=-0.022 didΔ=+0.000 → **harmful**
- nw_renewal v11 (controller_approved) dims=['prompt_version'] engageΔ=-0.017 didΔ=+0.000 → **harmful**
- nw_renewal v12 (controller_approved) dims=['voice'] engageΔ=-0.000 didΔ=+0.000 → **neutral**
- ks_cancel v9 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.582 → **beneficial**
- nw_renewal v13 (controller_approved) dims=['voice'] engageΔ=-0.000 didΔ=+0.000 → **neutral**
- ks_cancel v10 (controller_approved) dims=['prompt_version'] engageΔ=-0.139 didΔ=+0.000 → **harmful**
- nw_renewal v14 (controller_approved) dims=['welcome_message'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 22,
  "decisions": {
    "rejected": 3,
    "approved": 18,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 3
  },
  "applied_via_approval": 18,
  "auto_applied": 5,
  "auto_apply_rejected": 1,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 3,
    "nw_kyc": 2,
    "ks_cancel": 1
  }
}
```

## Incidents

```
[
  {
    "type": "did_flagged",
    "workflow": "ks_cancel",
    "at": "D2 10:00",
    "flagged_did_share_by_day": {
      "2": 0.49,
      "3": 0.499,
      "4": 0.495,
      "5": 0.509,
      "6": 0.504,
      "7": 0.079,
      "8": 0.0,
      "9": 0.0
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D3 11:30",
    "mttr_minutes": 1410,
    "fixed_by": "controller_approved"
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D5 15:00"
  }
]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:welcome_message=W3": {
    "6": 1.0,
    "7": 1.0,
    "8": 1.0,
    "9": 0.834
  }
}
```

Credits used: 48 · validation runs: 6 · LLM fix calls: 6