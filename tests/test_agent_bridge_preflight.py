from diagnostics.agent_bridge_preflight import BridgePreflightDoctor


def test_agent_bridge_preflight_flags_missing_workspace(tmp_path):
    doctor = BridgePreflightDoctor()
    findings = [doctor.check_workspace(str(tmp_path / "missing")), doctor.check_lark_profile_dir(None)]
    assert doctor.summarize(findings) == {"pass": 0, "warn": 1, "fail": 1}
    assert "bind an existing workspace" in findings[0].remediation
