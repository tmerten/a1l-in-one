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


def test_launchpad_config_parses_decoupled_targets(tmp_path: Path):
    config = tmp_path / "project-health.yaml"
    config.write_text("""
credentials:
  github_token: token

launchpad-bugs:
  - maas

launchpad-repos:
  - ~maas-committers/maas/+git/maas-release-tools
""")

    cfg = load_config(config)

    assert [target.name for target in cfg.launchpad_bugs] == ["maas"]
    repo = cfg.launchpad_repos[0]
    assert repo.path == "~maas-committers/maas/+git/maas-release-tools"
    assert repo.owner == "~maas-committers"
    assert repo.context == "maas"
    assert repo.repository == "maas-release-tools"


def test_launchpad_base_url_config_rejected(tmp_path: Path):
    config = tmp_path / "project-health.yaml"
    config.write_text("""
credentials:
  github_token: token

launchpad:
  base_url: https://api.launchpad.test/1.0
""")

    with pytest.raises(ValueError, match="base_url"):
        load_config(config)


def test_launchpad_credentials_parse_oauth_tuple(tmp_path: Path):
    config = tmp_path / "project-health.yaml"
    config.write_text("""
credentials:
  github_token: token
  launchpad:
    consumer_key: project-health-dashboard
    access_token: ${LAUNCHPAD_ACCESS_TOKEN}
    access_token_secret: ${LAUNCHPAD_ACCESS_TOKEN_SECRET}
""")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("LAUNCHPAD_ACCESS_TOKEN", "access-token")
    monkeypatch.setenv("LAUNCHPAD_ACCESS_TOKEN_SECRET", "access-secret")
    try:
        cfg = load_config(config)
    finally:
        monkeypatch.undo()

    assert cfg.credentials.launchpad is not None
    assert cfg.credentials.launchpad.consumer_key == "project-health-dashboard"
    assert cfg.credentials.launchpad.access_token == "access-token"
    assert cfg.credentials.launchpad.access_token_secret == "access-secret"


def test_launchpad_duplicate_repositories_rejected(tmp_path: Path):
    config = tmp_path / "project-health.yaml"
    config.write_text("""
credentials:
  github_token: token

launchpad-repos:
  - ~maas-committers/maas/+git/maas-release-tools
  - ~maas-committers/maas/+git/maas-release-tools
""")

    with pytest.raises(ValueError, match="Duplicate Launchpad repository"):
        load_config(config)


def test_invalid_launchpad_repository_path_rejected(tmp_path: Path):
    config = tmp_path / "project-health.yaml"
    config.write_text("""
credentials:
  github_token: token

launchpad-repos:
  - maas-release-tools
""")

    cfg = load_config(config)
    assert cfg.launchpad_repos[0].path == "maas-release-tools"
    assert cfg.launchpad_repos[0].repository == "maas-release-tools"


def test_nested_launchpad_targets_under_projects_are_supported(tmp_path: Path):
    config = tmp_path / "project-health.yaml"
    config.write_text("""
projects:
  launchpad-repos:
    - ~maas-committers/maas/+git/maas-release-tools
    - django-piston3
  launchpad-bugs:
    - maas

credentials:
  github_token: token
""")

    cfg = load_config(config)

    assert [target.name for target in cfg.launchpad_bugs] == ["maas"]
    assert [repo.path for repo in cfg.launchpad_repos] == [
        "~maas-committers/maas/+git/maas-release-tools",
        "django-piston3",
    ]
