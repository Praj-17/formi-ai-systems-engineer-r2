# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.240 | +2.0% | 0.181 | +0.2% | 0.474 | +1.4% | 4% | 276 (348) |
| nw_kyc | 0.377 | +0.8% | 0.245 | +4.4% | 0.588 | -3.3% | -6% | 27 (29) |
| nw_renewal | 0.423 | -2.4% | 0.259 | -1.4% | 0.548 | -1.1% | 0% | 65 (54) |
| ALL | 0.330 | -0.2% | 0.220 | +0.4% | 0.529 | -0.7% | 1% | 368 (431) |

## Changes applied by the controller

18 applied — neutral: 11, harmful: 4, beneficial: 3

- ks_cancel v2 (controller_auto) dims=['voice'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- nw_renewal v2 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_kyc v2 (controller_approved) dims=['voice'] engageΔ=+0.009 didΔ=+0.000 → **neutral**
- ks_cancel v3 (controller_auto) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nw_renewal v3 (controller_approved) dims=['voice'] engageΔ=+0.005 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.016 didΔ=+0.000 → **harmful**
- ks_cancel v4 (controller_auto) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_approved) dims=['voice'] engageΔ=-0.021 didΔ=+0.000 → **harmful**
- ks_cancel v5 (controller_auto) dims=['welcome_message'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.036 didΔ=+0.000 → **beneficial**
- ks_cancel v7 (controller_auto) dims=['welcome_message'] engageΔ=+0.010 didΔ=+0.000 → **neutral**
- nw_renewal v6 (controller_approved) dims=['welcome_message'] engageΔ=-0.007 didΔ=+0.000 → **neutral**
- nw_renewal v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.144 didΔ=+0.000 → **beneficial**
- nw_renewal v8 (controller_approved) dims=['welcome_message'] engageΔ=-0.027 didΔ=+0.000 → **harmful**
- nw_renewal v10 (controller_approved) dims=['voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- nw_renewal v11 (controller_approved) dims=['voice'] engageΔ=-0.004 didΔ=+0.000 → **neutral**
- nw_renewal v12 (controller_approved) dims=['voice'] engageΔ=-0.023 didΔ=+0.000 → **harmful**
- nw_renewal v13 (controller_approved) dims=['welcome_message'] engageΔ=+0.017 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 13,
  "decisions": {
    "approved": 13,
    "expired": 0
  },
  "rejection_reasons": {},
  "applied_via_approval": 13,
  "auto_applied": 5,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 2,
    "nw_kyc": 2
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
      "2": 0.495,
      "3": 0.502,
      "4": 0.498,
      "5": 0.501,
      "6": 0.508,
      "7": 0.497,
      "8": 0.508,
      "9": 0.495
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
    "5": 0.862,
    "6": 0.795,
    "7": 0.811,
    "8": 0.725,
    "9": 0.64
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0