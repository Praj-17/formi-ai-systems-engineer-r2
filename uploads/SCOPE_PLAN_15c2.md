# Agentic Universe Round 2 — weekend scope plan
Deadline: Monday 9 Nov 2026
Repo: https://github.com/AryamannNingombam/sde-assignment-2026
Submit: https://forms.cloud.microsoft/r/9q1p6YzBVy
Round 1 form (only if not already submitted): https://forms.cloud.microsoft/r/izyxftq6m9

## Mandatory floor
- Controller runs public_01 and public_02 end-to-end via ./run.sh with no manual steps
- Audit trail answering "why did workflow X change" (C12, even minimal)
- Never break governance / KPI-separation / population-only / crash-safety constraints
- Complete SUBMISSION.md from the template
- Grade reports for public_01 and public_02
- Crash-recovery evidence (kill mid-run, restart, finish correctly)

## Recommended build (fits ~12–16h)
- C1 Event ingestion (idempotent, restartable) — needed for load story
- C2 One shared cohort object — used everywhere
- C6 Variant experiments (welcome + voice) with min sample sizes
- C7 Winner promotion + decay rollback
- C9 Governance client (proposal lifecycle, auto-apply within policy)
- C12 Audit store
- C13 Crash recovery demo
- C5 Caller-ID health (public_02 has this incident) — at least detect + rotate proposal
- C8 Hallucination path (public_02) — detect → propose; LLM suggest if credits allow

## Cut (say so in SUBMISSION.md)
- C3 Bootstrapping from history (partial: warm from available API history only)
- C4 Fancy per-person call-time (simple per-cohort hour bands instead)
- C10 Perfect dry runs (honest but simplified impact score)
- C11 Full supervisor UI (JSON API endpoint is enough)
- C14/C15 Rich multi-tenant credit fairness (basic credit budget + metrics logs)

## Principle
Ship a correct learning loop with governance and audit on the two public scenarios. Prefer statistical winner selection over LLM decisions. Defend every dependency.
