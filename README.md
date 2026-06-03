# agent-skills

Canonical, agent-agnostic home for AI-agent skills on this machine — and the
version-controlled source of truth for the original ones.

## Layout

```
~/.agents/
  .skill-lock.json     # provenance of installer-managed third-party skills
  skills/
    <name>/SKILL.md    # one skill per directory
    <name>/scripts/    # bundled helpers the skill executes
```

Each agent tool (Claude Code, Codex, Gemini CLI, …) discovers skills through a
per-agent symlink farm pointing back here, e.g.:

```
~/.claude/skills/<name> -> ../../.agents/skills/<name>
```

This keeps a single copy of every skill while letting any agent load it.

## Two kinds of skills live here

**Third-party (untracked).** Installed by a skills CLI (see `.skill-lock.json`)
or skillfish (per-skill `.skillfish.json`). They are gitignored: the lock files
make them reproducible, and their licenses belong to their authors — this repo
does not redistribute them.

**Original (tracked).** Authored here. Each gets an explicit `!skills/<name>/`
allow-line in `.gitignore`.

| Skill | What it does |
|-------|--------------|
| `browser-screenshot` | Generic URL→PNG capture by driving a real browser via [browser-harness](https://github.com/browser-use/browser-harness) over CDP — viewport / full-page / element-crop modes, forced dark mode, host-aware credential resolution with a pluggable form-login. |
| `homepage-icon-finder` | Resolve correct icon values for [Homepage](https://gethomepage.dev) dashboard service tiles. |

## Authoring a new skill

1. Create `skills/<name>/SKILL.md` (+ `scripts/` if it bundles helpers) **here**,
   not in an agent's own skills dir.
2. Symlink it into each agent that should see it:
   `ln -s ../../.agents/skills/<name> ~/.claude/skills/<name>`
3. Privacy pass — this repo is public. No secrets, no personal paths
   (`/Users/<name>`), no private hostnames; use `*.example` hosts in examples.
4. Add `!skills/<name>/` to `.gitignore`, commit.
