# Agent Tuning Heuristics (Phase 11.2)

## Rule-based правила

### 1. Repeated fallback on same specialization/domain/step

- **Condition**: specialization_hotspots (domain, step) с fallback_count >= 2
- **Evidence**: fallback_count, domain_key, workflow_step
- **Likely change**: expand_specialization_keywords, review_specialization_profile
- **Severity**: medium если >= 3, иначе low
- **Verification metric**: снижение fallback_rate по этому (domain, step)

### 2. Override-heavy corrections tied to same execution lane

- **Condition**: override_hotspots по domain или project
- **Evidence**: override count, domain/project key
- **Likely change**: adjust_routing_keywords, review_domain_mapping
- **Severity**: medium если count >= 3
- **Verification metric**: снижение override count

### 3. Unstable execution lane (high fallback rate globally)

- **Condition**: fallback_rate >= 0.4, total_fallback_events >= 2
- **Evidence**: fallback_rate, total events
- **Likely change**: review_fallback_strategy, expand specialization profiles
- **Severity**: low
- **Verification metric**: fallback_rate

### 4. Frequent mismatch despite chosen specialization

- **Condition**: specialization selected часто, но downstream weak (rework, mismatch)
- **Evidence**: selected vs fallback ratio, rework signals
- **Likely change**: refine_expected_output_type, tighten_guardrails
- **Severity**: medium
- **Verification metric**: rework rate, mismatch signals
