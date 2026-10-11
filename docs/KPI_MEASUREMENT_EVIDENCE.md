# KPI evidence and missing measurements

The old numeric owner_minutes/owner_hours_saved/action/rework fields remain
compatible for existing API consumers. They are estimates/defaults and must not
be presented as verified saved time without the new metadata.

New fields:
- owner_minutes_status: recorded, partial, missing. Explicit zero is recorded;
  absent duration is missing. Audit-based coverage refers to recorded actions,
  not a promise that off-platform effort was captured.
- baseline_minutes / baseline_status: declared, estimated, partial, missing.
  Partial action estimates cannot become a full task baseline.
- business_outcome_verified: requires task DONE, a nonempty result, explicit
  boolean business_outcome_verified=true and business_outcome_evidence_ref.
- savings_status: unmeasured, needs_evidence, awaiting_outcome, verified.
- verified_owner_hours_saved: null unless the above inputs and evidence refs
  exist; otherwise (baseline_minutes - owner_minutes) / 60. Negative values
  expose extra owner effort rather than silently clamping it to zero.

Authorized owner measurement data belongs in business_action_json.outcome_metrics
(or existing root business-action metadata). Record total owner effort, including
SSH/manual operations/rework outside the app, and a defensible manual baseline.
Add owner_time_evidence_ref and baseline_evidence_ref. Evidence refs are provenance
links supplied by the owner; this pure calculator does not fetch or independently
validate their contents. Approval feedback alone does not attest a business result.
Keep reference data accurate and attach review evidence before declaring verified.

The panel uses the new fields: missing measurements display “Не измерено”, partial
time is marked, estimates without evidence are not displayed as verified savings,
and unverified outcome text is labelled. Action counts are audit proxies; rework
counts reflect owner returns. This change does not repair historical records or
invent a baseline for tasks 38/39, nor does it authorize merge/deploy.

Verification from the repository root:
`python -m pytest tests/test_outcome_metrics.py -q`
`node --check app/dashboard/static/game.js`

Rollback is reverting the code release. There is no migration or record rewrite.
