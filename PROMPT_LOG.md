# Quantum Fingerprinting Project: Agent Prompt Log (chronological)

All prompts sent to the coding agent so far, in order. Use this as a running reference — paste the next one when the agent reports back, and append new ones to this file as the study continues.

---

## 0. Master implementation prompt (full rules + design)
See `MASTER_PROMPT_IMPLEMENTATION.md` — pasted once at the start as AGENTS.md/CLAUDE.md. Not repeated here; it's the standing ruleset the agent follows throughout. Key points it must keep honoring in every batch going forward: no fabricated data, provenance tags, chronological splits only, QPU budget guard, resumable/idempotent collection, stop-and-ask triggers.

---

## 1. IBM credentials handoff (sent after getting API key + CRN)
```
I now have my IBM Quantum API token and instance CRN (I will provide them via environment variables QISKIT_IBM_TOKEN and QISKIT_IBM_INSTANCE, channel="ibm_quantum_platform" — never print or log these values).

Proceed with the approved Stage 1 plan, with these required changes:
1. Run 01_select_backends.py: query MY instance for currently operational backends — do NOT hard-code ibm_kyiv/ibm_sherbrooke/ibm_brisbane, they may be retired. Report available backends, qubit counts, and the fixed 3-qubit physical layout chosen per backend (best-connected, lowest-error triple).
2. Before any hardware job, fetch and report my ACTUAL remaining Open Plan QPU allowance (not the nominal 600s).
3. Run 02_budget_probe.py as ONE job on ONE backend containing all 10 circuits at 2048 shots (a full round), job/batch mode only, no sessions. Report job.usage() quantum seconds, queue time, backend, and layout.
4. Fix circuit c10's delay: use ~20-50 microseconds of real delay time (check backend.dt and timing constraints), not 1000 dt. Report the dt and delay value used.
5. Recompute the full-study QPU projection from the measured probe (not the dry-run estimate), apply the 85% safety cap against my real remaining allowance, and propose a round schedule (target 10-12 rounds, ≥4 in the test split) that fits.
6. Stop and report all of the above for my approval before submitting any further hardware jobs.
```

---

## 2. Approve Schedule B conditional on cross-backend probe check
```
Approved: Schedule B (3 backends, 12 rounds, train 1-5 / val 6-7 / test 8-12), conditional on one more check.

Before updating study.yaml and starting Stage 2:
1. Run 02_budget_probe.py once on ibm_marrakesh and once on ibm_fez (same 10-circuit, 2048-shot round as the ibm_kingston probe). Report job.usage() seconds per round for each.
2. If both are within ~15% of the 8.0s/round measured on ibm_kingston, proceed with Schedule B as proposed and lock the schedule into study.yaml.
3. If either backend is notably slower, recompute the full-study projection using the SLOWEST measured per-round cost (not kingston's), re-check the 85% cap, and propose an adjusted schedule (fewer rounds, or 2 backends) before proceeding.
4. After locking the schedule, begin Stage 2 by launching round 1 across all 3 backends now, and report: job IDs, per-backend usage, and running total QPU time consumed so far vs the 510s cap.
5. Continue to halt and report after each day's rounds rather than running all 12 unattended — I want visibility before more than ~50% of the cap is consumed.
```

---

## 3. After Round 1: question the suspicious 0.00% variance, enforce real time gaps
```
Round 1 approved. Before continuing:

1. Confirm whether job.usage() is quantized/rounded by IBM's billing (e.g. rounded to the nearest second) or a true continuous measurement. Check the Runtime docs or the raw job metadata for a sub-second value. Note the answer in METHODS_NOTES.md — exact billing granularity affects how tightly we can trust the budget projection.

2. Do NOT launch Round 2 immediately. Wait at least 4-6 hours from Round 1's timestamp so rounds capture real time-of-day separation, per the study design (2 rounds/day at different times).

3. When the gap has passed, launch Round 2 (single round, all 3 backends), then halt and report: per-backend usage, cumulative QPU time vs the 510s cap, and the actual wall-clock gap from Round 1.

4. Going forward, batch report every 2 rounds (not 1) to reduce back-and-forth, but never submit a round until the minimum time gap from the previous round on that backend has passed. Keep halting for my check-in at each 2-round batch — do not run rounds 3-12 unattended in one go, even though budget headroom is large.
```

---

## 4. After billing-quantization resolved: adjust Round 2 timing for real diurnal spread
```
Round 2 timing: instead of firing at the earliest 4-hour mark (02:04 AM), push this one to the next convenient daytime slot (late morning or afternoon) so Round 1 (night) and Round 2 (day) actually span different parts of the calibration/usage cycle, not two adjacent night hours. The 4-hour minimum gap is a floor, not a target — for the rest of the study, aim rounds at roughly 12-hour offsets (e.g. morning + evening) rather than the soonest-allowed time, unless that's impractical for scheduling. Keep the 4-hour hard guard as the safety minimum regardless.

Otherwise proceed as planned: launch when ready, then report per-backend usage, actual wall-clock gap, and cumulative QPU vs the 510s cap. Continue batching reports every 2 rounds.
```

---

## Status as of last report
- Credentials working, 3 operational Heron r2 backends identified (`ibm_kingston`, `ibm_marrakesh`, `ibm_fez`), fixed layouts locked.
- Billing confirmed: exactly 8 integer seconds charged per 10-circuit/2048-shot round on every backend (rounded up from ~5.4-5.6s real execution) — budget is deterministic, not estimated.
- Schedule B locked: 12 rounds, 3 backends, train 1-5 / val 6-7 / test 8-12, projected 288s total (48% of 600s), 222s safety buffer.
- Batch 1 (Rounds 1 & 2) complete on all 3 backends:
  - Round 1 (Oct 4 Evening baseline): jobs `db17vf9b694s73dru660` (fez), `db17vjrid5ic73eqpc30` (kingston), `db17vrhb694s73dru6qg` (marrakesh).
  - Round 2 (Oct 5 Daytime slot): jobs `db1jjfhb694s73dscdk0` (fez, 13.22h gap), `db1jp32vog1s73fi7s60` (kingston, 13.41h gap), `db1jq71b694s73dscqbg` (marrakesh, 13.44h gap).
- Cumulative QPU consumed: **72.000 s** across 9 total jobs (24.0s probes + 24.0s R1 + 24.0s R2) = **14.1%** of 510.0s safety cap (438.0s safe budget remaining; 528.0s of 600.0s Open Plan allowance remaining).
- Diurnal separation verified: ~13.3 hours wall-clock gap between Round 1 and Round 2, spanning day/night calibration cycles.
- Reporting cadence: batched every 2 rounds, halting for check-in each time. Batch 1 complete; awaiting user instructions for Batch 2 (Rounds 3 & 4).

## 5. Deadline constraint (MARC 2027 by Oct 15): Maximum Compression Cadence & Autonomous Pipeline Execution
```
Deadline constraint: this paper must be submitted to MARC 2027 by Oct 15. Switch from diurnal-alternation cadence to MAXIMUM COMPRESSION cadence effective immediately:

1. Run every remaining round (3 through 12) back-to-back, each launched the moment the 4.0h hard-floor guard clears per backend — no more waiting for morning/evening slots. Keep the 4h floor as a hard minimum (do not remove it — it's what makes the chronological claim valid at all).
2. Keep all existing halt conditions active (backend failure, job error, >15% usage deviation from 8.0s/round baseline, cumulative QPU >60% of the 510s cap). Report every 2 rounds as before, but do not wait for my approval between batches unless a halt condition fires — proceed autonomously through Round 12.
3. The moment Round 12 completes, automatically continue into Stage 3 (simulate S0/S1/S2) and Stage 4 (features + experiments E1-E7) without waiting for my sign-off — log everything to METHODS_NOTES.md as you go, but don't halt for approval at each sub-step anymore given the deadline.
4. After Stage 4, STOP and report: total QPU consumed, actual observation window (first round timestamp to last — report this honestly, it will be ~2 days not ~5), and the claims_audit.md summary. Wait for my review before Stage 5 (figures/tables/handoff).
5. In METHODS_NOTES.md and LIMITATIONS_OBSERVED.md, record plainly that the compressed ~2-day collection window (vs. the originally planned ~5-day diurnal-alternating window) is a deadline-driven limitation — this must appear in the paper's Limitations section later, not be hidden.

IMPLEMENTATION ONLY — do not write any paper, abstract, related work, or citations at any point in this run. Stop after Stage 4 (experiments complete) and report; do NOT proceed to Stage 5, figures, or a handoff narrative beyond the raw results/claims_audit.md.
```

---

## Status as of last report
- Credentials working, 3 operational Heron r2 backends identified (`ibm_kingston`, `ibm_marrakesh`, `ibm_fez`), fixed layouts locked.
- Billing confirmed: exactly 8 integer seconds charged per 10-circuit/2048-shot round on every backend — deterministic budget.
- Schedule B locked: 12 rounds, 3 backends, train 1-5 / val 6-7 / test 8-12, projected 288s total (48% of 600s), 222s safety buffer.
- Batch 1 (Rounds 1 & 2) complete on all 3 backends:
  - Round 1: Oct 4 Evening baseline.
  - Round 2: Oct 5 Daytime slot (~13.3h gap).
- Cumulative QPU consumed: **72.000 s** across 9 total jobs (14.1% of 510.0s safety cap).
- Switched to Maximum Compression cadence: remaining rounds 3–12 to be launched as soon as 4.0h hard floor clears per backend.
- Autonomous pipeline progression through Stage 3 (simulations) and Stage 4 (features + experiments E1–E7) authorized; hard stop at Stage 4 report / claims audit.


