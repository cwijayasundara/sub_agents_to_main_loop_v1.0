import pytest
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

CAPTURED: list = []  # module-level: pydantic models resist instance attributes


class CapturingFakeModel(GenericFakeChatModel):
    """Records SystemMessage content seen during generate."""

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        for m in messages:
            if isinstance(m, SystemMessage):
                CAPTURED.append(m.content)
        return super()._generate(messages, stop, run_manager, **kwargs)


def test_skills_directory_has_wellformed_skills():
    """Skills exist, frontmatter names match directory names (deepagents spec)."""
    import pathlib
    import yaml

    root = pathlib.Path("workspace/skills")
    assert root.exists()
    found = {}
    for skill_dir in root.iterdir():
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.exists(), f"{skill_dir} missing SKILL.md"
        meta = yaml.safe_load(skill_md.read_text().split("---")[1])
        assert meta["name"] == skill_dir.name, f"name must match dir: {meta['name']!r}"
        assert meta.get("description")
        found[meta["name"]] = skill_dir
    assert {"paid-media-analysis", "paid-media-report", "paid-media-writes"} <= set(found)


def test_skills_are_portable_and_wiki_is_company_specific():
    """A skill must not contain our campaign names (PMA rule: skills work at another company)."""
    import pathlib

    for skill_md in pathlib.Path("workspace/skills").glob("*/SKILL.md"):
        text = skill_md.read_text().lower()
        for company_term in ("langchain", "our q1 campaign", "acme corp"):
            assert company_term not in text


def test_wiki_is_company_specific_reference():
    import pathlib

    wiki = pathlib.Path("workspace/wiki")
    pages = {p.name for p in wiki.glob("*.md")}
    assert {"source-of-truth.md", "campaign-goals.md"} <= pages
    sot = (wiki / "source-of-truth.md").read_text().lower()
    assert "warehouse" in sot and "ad platform" in sot


def test_agent_discloses_skills_in_system_prompt():
    """Progressive disclosure: skill names+descriptions appear in the system prompt."""
    from pmf_agent.agent import create_agent

    CAPTURED.clear()
    model = CapturingFakeModel(messages=iter([AIMessage("ok")]))
    agent = create_agent("slack", model=model, skills_root="workspace")
    agent.invoke(
        {"messages": [{"role": "user", "content": "hi"}]},
        config={"configurable": {"thread_id": "skills-test"}},
    )
    system_text = " ".join(str(c) for c in CAPTURED)
    assert "paid-media-analysis" in system_text
    assert "paid-media-report" in system_text


def test_prompt_points_to_wiki():
    from pmf_agent.prompts import system_prompt

    text = system_prompt("slack")
    assert "wiki" in text.lower()
