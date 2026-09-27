# Primary demo script

The happy path is `deployment_regression`. The dashboard is the only console the interviewer needs. Button labels below match the UI.

1. Open the dashboard with no active incidents.
2. Run the `deployment_regression` scenario.
3. Show the alarm / event.
4. Show the created incident.
5. Start the investigation.
6. Show tool calls and evidence (`query_logs`, `query_metrics`, `get_recent_deployments`, `search_runbooks`).
7. Show the retrieved runbook.
8. Show the diagnosis and confidence.
9. Show correlation with the recent deployment.
10. Show the proposed simulated rollback.
11. Attempt remediation without approval → denied.
12. Approve from the UI.
13. Execute remediation.
14. Mark the incident resolved.
15. Show the trace.
16. Show tokens, tool calls, and estimated cost.
17. Show the case evaluation.

End-to-end flow this script proves:

```text
CloudWatch Alarm
    ↓
EventBridge
    ↓
Incident created
    ↓
Agent investigation
    ↓
Diagnosis
    ↓
Recommended remediation
    ↓
Human approval
    ↓
Safe remediation tool
    ↓
Incident resolved + audit trail
```
