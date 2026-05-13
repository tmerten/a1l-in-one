"""Tests for configuration loading."""

from pathlib import Path

import pytest

from project_health.config.loader import Config, load_config


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    config = tmp_path / "project-health.yaml"
    config.write_text("""
team:
  - name: Alice
    github: alice-gh
    jira: "12345"

projects:
  github:
    - owner/repo-a
  jira:
    - key: PROJ
      board_id: 42

credentials:
  github_token: ${GITHUB_TOKEN}
  jira:
    base_url: https://test.atlassian.net
    email: test@example.com
    api_token: ${JIRA_TOKEN}

ingestion:
  interval_minutes: 15
  backfill_days: 90
""")
    return config


def test_load_config_with_env_vars(monkeypatch, sample_config):
    monkeypatch.setenv("GITHUB_TOKEN", "gh_test_token")
    monkeypatch.setenv("JIRA_TOKEN", "jira_test_token")

    cfg = load_config(sample_config)
    assert isinstance(cfg, Config)
    assert cfg.credentials.github_token == "gh_test_token"
    assert cfg.credentials.jira.api_token == "jira_test_token"
    assert len(cfg.team) == 1
    assert cfg.team[0].name == "Alice"
    assert cfg.all_github_repos == ["owner/repo-a"]


def test_missing_env_var_raises(monkeypatch, sample_config):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        load_config(sample_config)


def test_credentials_match_projects_validation(monkeypatch, tmp_path: Path):
    config = tmp_path / "project-health.yaml"
    config.write_text("""
projects:
  github:
    - owner/repo-a

credentials:
  github_token: ${GITHUB_TOKEN}
""")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    cfg = load_config(config)
    assert cfg.projects.github


def test_jira_without_creds_raises(monkeypatch, tmp_path: Path):
    config = tmp_path / "project-health.yaml"
    config.write_text("""
projects:
  jira:
    - key: PROJ
      board_id: 1

credentials:
  github_token: ${GITHUB_TOKEN}
""")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    with pytest.raises(ValueError, match="jira credentials"):
        load_config(config)
