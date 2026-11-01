import pytest


def test_main_runs_one_off_query(monkeypatch, capsys):
    """main(['question']) builds an agent, runs it, prints the answer."""
    from pmf_agent import main as m

    captured = {}

    class StubAgent:
        def invoke(self, state, config):
            captured["state"] = state
            captured["config"] = config
            from langchain_core.messages import AIMessage

            return {"messages": [AIMessage("spend went up 49%")]}

    monkeypatch.setattr(m, "_build_agent", lambda **kw: StubAgent())
    rc = m.main(["--no-stream", "How did google spend move last week?"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "spend went up 49%" in out
    assert "google" in captured["state"]["messages"][-1]["content"] or (
        captured["state"]["messages"][-1].get("content")
        and "google" in str(captured["state"]["messages"][-1]["content"])
    )
    assert captured["config"]["configurable"]["thread_id"]


def test_main_repl_loops_until_quit(monkeypatch, capsys):
    from pmf_agent import main as m

    class StubAgent:
        def invoke(self, state, config):
            from langchain_core.messages import AIMessage

            return {"messages": [AIMessage("echo: " + str(state["messages"][-1]))]}

    monkeypatch.setattr(m, "_build_agent", lambda **kw: StubAgent())
    monkeypatch.setattr("builtins.input", lambda prompt="": "hello")
    # second input raises EOFError to end the loop
    calls = {"n": 0}

    def fake_input(prompt=""):
        calls["n"] += 1
        if calls["n"] > 1:
            raise EOFError
        return "hello"

    monkeypatch.setattr("builtins.input", fake_input)
    rc = m.main(["--no-stream"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "hello" in out  # the question reached the agent and its answer printed


def test_main_entry_point_and_arch_flags_validated(monkeypatch):
    from pmf_agent import main as m

    monkeypatch.setattr(m, "_build_agent", lambda **kw: None)
    with pytest.raises(SystemExit):
        m.main(["--entry-point", "email", "q"])


def test_build_agent_uses_flags():
    """_build_agent wires entry_point/arch/skills_root to the right factory."""
    from conftest import make_fake_model

    from pmf_agent import main as m

    agent = m._build_agent(entry_point="slack", arch="folded", skills_root=None, model=make_fake_model())
    assert agent is not None
    agent2 = m._build_agent(
        entry_point="slack", arch="hierarchical", skills_root="workspace", model=make_fake_model()
    )
    assert set(agent2.pmf_subagents) == {
        "google-ads-specialist", "meta-ads-specialist", "reddit-ads-specialist"
    }
