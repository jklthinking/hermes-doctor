from diagnostics.agent_sandbox_runtime_context import SandboxRuntimeContext, build_sandbox_info, diagnose_runtime_context, sandbox_health_endpoint_payload


def test_sandbox_info_redacts_secret_environment_values():
    info = build_sandbox_info(SandboxRuntimeContext("/tmp/work", "default", environment={"API_KEY": "abc", "MODE": "test"}))
    assert info["environment"]["API_KEY"] == "[REDACTED]"
    assert info["environment"]["MODE"] == "test"


def test_diagnostics_find_overbroad_writable_path():
    payload = sandbox_health_endpoint_payload(SandboxRuntimeContext("/tmp/work", "default", writable_paths=["/root/.hermes"]))
    assert payload["ok"] is False
    assert {f["code"] for f in payload["findings"]} == {"overbroad_writable_path"}


def test_network_without_web_toolset_is_nonblocking_context_finding():
    findings = diagnose_runtime_context({"workspace": "relative", "network_enabled": True, "toolsets": []})
    codes = {f["code"] for f in findings}
    assert "workspace_not_absolute" in codes
    assert "network_without_web_toolset" in codes
