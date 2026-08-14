#!/usr/bin/env python3
"""Validate the review repository without third-party dependencies."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
CLAUDE_MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
SKILL = ROOT / "skills" / "polish-open-source-prose"

SEMVER = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"

REQUIRED_PLUGIN_FIELDS = {
    "name",
    "version",
    "description",
    "author",
    "license",
    "skills",
    "interface",
}
REQUIRED_CLAUDE_PLUGIN_FIELDS = {
    "name",
    "version",
    "description",
    "author",
    "license",
}
REQUIRED_INTERFACE_FIELDS = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "defaultPrompt",
}
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".toml"}


def validate_plugin(errors: list[str]) -> None:
    try:
        manifest = json.loads(PLUGIN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot load plugin manifest: {exc}")
        return

    missing = REQUIRED_PLUGIN_FIELDS - manifest.keys()
    if missing:
        errors.append(f"Plugin manifest is missing: {sorted(missing)}")
    if manifest.get("name") != ROOT.name:
        errors.append("Plugin name must match the repository folder name")
    if not re.fullmatch(SEMVER, manifest.get("version", "")):
        errors.append("Plugin version must use strict semantic versioning")
    if manifest.get("license") != "Apache-2.0":
        errors.append("Plugin license must identify the repository's Apache-2.0 license")
    if manifest.get("skills") != "./skills/":
        errors.append("Plugin skills path must be ./skills/")
    if not isinstance(manifest.get("author"), dict) or not manifest["author"].get("name"):
        errors.append("Plugin author.name is required")

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("Plugin interface must be an object")
        return
    missing_interface = REQUIRED_INTERFACE_FIELDS - interface.keys()
    if missing_interface:
        errors.append(f"Plugin interface is missing: {sorted(missing_interface)}")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3:
        errors.append("Plugin defaultPrompt must contain one to three prompts")
    elif any(not isinstance(prompt, str) or not prompt or len(prompt) > 128 for prompt in prompts):
        errors.append("Each plugin defaultPrompt must be a non-empty string of at most 128 characters")


def validate_claude_plugin(errors: list[str]) -> dict:
    """Check the Claude Code plugin manifest that exposes skills/ to Claude."""
    try:
        manifest = json.loads(CLAUDE_PLUGIN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot load Claude plugin manifest: {exc}")
        return {}

    missing = REQUIRED_CLAUDE_PLUGIN_FIELDS - manifest.keys()
    if missing:
        errors.append(f"Claude plugin manifest is missing: {sorted(missing)}")
    if manifest.get("name") != ROOT.name:
        errors.append("Claude plugin name must match the repository folder name")
    if not re.fullmatch(SEMVER, manifest.get("version", "")):
        errors.append("Claude plugin version must use strict semantic versioning")
    if manifest.get("license") != "Apache-2.0":
        errors.append("Claude plugin license must identify the repository's Apache-2.0 license")
    if not isinstance(manifest.get("author"), dict) or not manifest["author"].get("name"):
        errors.append("Claude plugin author.name is required")
    # Claude discovers skills/ at the plugin root; a custom path would bypass it.
    if "skills" in manifest and manifest["skills"] not in ("./skills/", "."):
        errors.append("Claude plugin skills path must stay at the repository skills/ directory")
    return manifest


def validate_claude_marketplace(errors: list[str], plugin: dict) -> None:
    """Check the marketplace entry used by /plugin marketplace add."""
    try:
        marketplace = json.loads(CLAUDE_MARKETPLACE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Cannot load Claude marketplace manifest: {exc}")
        return

    if not marketplace.get("name"):
        errors.append("Claude marketplace name is required")
    owner = marketplace.get("owner")
    if not isinstance(owner, dict) or not owner.get("name"):
        errors.append("Claude marketplace owner.name is required")

    entries = marketplace.get("plugins")
    if not isinstance(entries, list) or len(entries) != 1:
        errors.append("Claude marketplace must list exactly the repository's one plugin")
        return

    entry = entries[0]
    if not isinstance(entry, dict):
        errors.append("Claude marketplace plugin entry must be an object")
        return
    if entry.get("name") != ROOT.name:
        errors.append("Claude marketplace plugin name must match the repository folder name")
    # A relative source resolves against the marketplace root, which is this repository.
    if entry.get("source") != "./":
        errors.append("Claude marketplace plugin source must be ./ for a root-level plugin")
    if plugin and entry.get("version") and entry["version"] != plugin.get("version"):
        errors.append("Claude marketplace version must match the Claude plugin version")


def validate_manifest_parity(errors: list[str], claude: dict) -> None:
    """Keep the Codex and Claude manifests describing the same release."""
    if not claude:
        return
    try:
        codex = json.loads(PLUGIN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for field in ("name", "version", "license", "description"):
        if codex.get(field) != claude.get(field):
            errors.append(f"Codex and Claude manifests disagree on {field}")


def validate_files(errors: list[str]) -> None:
    required = [
        ROOT / "README.md",
        ROOT / "README.zh-Hant-TW.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "LICENSE",
        ROOT / "NOTICE",
        ROOT / "THIRD_PARTY_NOTICES.md",
        SKILL / "SKILL.md",
        SKILL / "LICENSE.stop-slop",
        CLAUDE_PLUGIN,
        CLAUDE_MARKETPLACE,
    ]
    for path in required:
        if not path.exists():
            errors.append(f"Missing required file: {path.relative_to(ROOT)}")

    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    scaffold_marker = "[TO" + "DO:"
    local_home_prefix = "/" + "Users" + "/"
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        is_text = path.suffix in TEXT_SUFFIXES or path.name in {"NOTICE", "LICENSE"}
        if not is_text:
            continue
        text = path.read_text(encoding="utf-8")
        if scaffold_marker in text:
            errors.append(f"Unresolved scaffold placeholder in {path.relative_to(ROOT)}")
        if local_home_prefix in text:
            errors.append(f"Local absolute path in {path.relative_to(ROOT)}")
        if path.suffix == ".md":
            for target in link_pattern.findall(text):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                local_target = target.split("#", 1)[0]
                if not (path.parent / local_target).resolve().exists():
                    errors.append(f"Broken local link in {path.relative_to(ROOT)}: {target}")

    upstream_license = (SKILL / "LICENSE.stop-slop").read_text(encoding="utf-8")
    if "MIT License" not in upstream_license or "Hardik Pandya" not in upstream_license:
        errors.append("Upstream stop-slop license or attribution is incomplete")


def validate_skill(errors: list[str]) -> str:
    validator = SKILL / "scripts" / "validate_skill.py"
    result = subprocess.run(
        [sys.executable, str(validator)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode:
        errors.append(f"Skill validation failed:\n{output}")
    return output


def main() -> int:
    errors: list[str] = []
    validate_plugin(errors)
    claude_plugin = validate_claude_plugin(errors)
    validate_claude_marketplace(errors, claude_plugin)
    validate_manifest_parity(errors, claude_plugin)
    validate_files(errors)
    skill_output = validate_skill(errors)

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository validation passed.")
    if skill_output:
        print(skill_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
