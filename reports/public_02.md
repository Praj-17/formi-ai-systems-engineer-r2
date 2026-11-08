# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.241 | +2.3% | 0.179 | -0.9% | 0.481 | +2.8% | 10% | 313 (348) |
| nw_kyc | 0.370 | -1.0% | 0.238 | +1.6% | 0.595 | -2.2% | 12% | 34 (29) |
| nw_renewal | 0.429 | -1.0% | 0.262 | -0.1% | 0.548 | -1.1% | 0% | 62 (54) |
| ALL | 0.331 | +0.1% | 0.219 | -0.1% | 0.533 | -0.0% | 5% | 409 (431) |

## Changes applied by the controller

23 applied — neutral: 15, harmful: 5, beneficial: 3

- ks_cancel v2 (controller_auto) dims=['voice'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- nw_renewal v2 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_kyc v2 (controller_approved) dims=['voice'] engageΔ=+0.009 didΔ=+0.000 → **neutral**
- ks_cancel v3 (controller_auto) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nw_renewal v3 (controller_approved) dims=['voice'] engageΔ=-0.020 didΔ=+0.000 → **harmful**
- ks_cancel v4 (controller_auto) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.016 didΔ=+0.000 → **harmful**
- nw_renewal v4 (controller_approved) dims=['voice'] engageΔ=+0.010 didΔ=+0.000 → **neutral**
- nw_kyc v4 (controller_approved) dims=['voice'] engageΔ=+0.033 didΔ=+0.000 → **beneficial**
- ks_cancel v6 (controller_auto) dims=['welcome_message'] engageΔ=+0.009 didΔ=+0.000 → **neutral**
- nw_renewal v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_auto) dims=['welcome_message'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- nw_renewal v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.036 didΔ=+0.000 → **beneficial**
- ks_cancel v8 (controller_approved) dims=['welcome_message'] engageΔ=+0.039 didΔ=+0.000 → **beneficial**
- nw_renewal v8 (controller_approved) dims=['voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- nw_kyc v5 (controller_approved) dims=['voice'] engageΔ=-0.007 didΔ=+0.000 → **neutral**
- ks_cancel v9 (controller_auto) dims=['welcome_message'] engageΔ=-0.009 didΔ=+0.000 → **neutral**
- nw_renewal v9 (controller_approved) dims=['voice'] engageΔ=-0.023 didΔ=+0.000 → **harmful**
- ks_cancel v10 (controller_auto) dims=['welcome_message'] engageΔ=-0.007 didΔ=+0.000 → **neutral**
- nw_renewal v10 (controller_approved) dims=['voice'] engageΔ=+0.001 didΔ=+0.000 → **neutral**
- nw_kyc v6 (controller_approved) dims=['voice'] engageΔ=-0.031 didΔ=+0.000 → **harmful**
- nw_renewal v11 (controller_approved) dims=['welcome_message'] engageΔ=-0.082 didΔ=+0.000 → **harmful**
- nw_kyc v7 (controller_approved) dims=['voice'] engageΔ=+0.008 didΔ=+0.000 → **neutral**

## Governance

```
{
  "approval_requests": 34,
  "decisions": {
    "approved": 16,
    "rejected": 17,
    "expired": 0
  },
  "rejection_reasons": {
    "prompt changes need evidence.validation_run_id for this workflow and prompt": 14,
    "approver fatigue: more than 2 requests in 24h for this workflow \u2014 batch your changes": 2,
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 16,
  "auto_applied": 7,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 3,
    "nw_kyc": 3,
    "ks_cancel": 2
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
      "2": 0.504,
      "3": 0.483,
      "4": 0.508,
      "5": 0.507,
      "6": 0.507,
      "7": 0.51,
      "8": 0.506,
      "9": 0.503
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D3 11:30",
    "mttr_minutes": null,
    "fixed_by": null
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
    "7": 0.193,
    "8": 0.2,
    "9": 0.868
  }
}
```

Credits used: 117 · validation runs: 15 · LLM fix calls: 14