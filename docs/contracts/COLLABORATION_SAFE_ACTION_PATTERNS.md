# COLLABORATION_SAFE_ACTION_PATTERNS — Phase 11.4

Маппинг сигналов/suggestion types на безопасные действия (action center).

| Signal / suggestion flavor | safe_action_key | Fallback |
|----------------------------|-----------------|----------|
| approval_bottleneck / approval_resolution | `open_decision_queue` | Ручной /approvals |
| runtime_escalation / degraded | `recheck_molt_health` | `retry_runtime_check` |
| owner_attention_gap | `send_digest_now` или `refresh_status` | Advisory only |
| review_execution_loop | `refresh_status` | Follow-up marker, manual |
| reviewer backlog | `open_decision_queue` | Manual |
| project domain unstable | — | Advisory: `/owner/project`, без forced apply |
| refinement-related hotspot | — | `/owner/refinement` hint only |

**Closure:** успешный safe action → `acknowledged`; bottleneck «снят» только после проверки owner (explicit `close`).
