from diagnostics.orchestration_runtime_check import diagnose_flow_log, diagnose_pending_events, diagnose_transition_drift


def test_transition_drift_detects_mismatch():
    issues = diagnose_transition_drift({"a": {"b"}}, {"a": {"c"}})
    assert issues[0].code == "transition_drift"
    assert issues[0].severity == "critical"


def test_pending_event_diagnostics():
    issues = diagnose_pending_events([{"id": "e1", "idle_seconds": 400, "delivery_count": 6}])
    assert {i.code for i in issues} == {"stale_pending_event", "repeated_delivery"}


def test_flow_log_missing_for_non_initial_state():
    issues = diagnose_flow_log({"state": "running", "flow_log": []})
    assert issues[0].code == "missing_flow_log"
