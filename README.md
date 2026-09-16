# RS9 Skills

Agent skills we actually run.

Public clone: https://github.com/rs9io/skills  
Cursor Origin (login): https://cursor.com/codebase/rs9io/skills

## triple-escalator

The parent chooses a persistent coding worker: DeepSeek Pro by default, or Flash
for small mechanical work. The worker implements, tests and returns directly to
the parent for review or rescue. No Flash-to-Pro ladder. Sessions and cost logs
persist through the PR; no separate rescue API call or fixed final model.

[Install Triple Escalator](triple-escalator/README.md). Bring your own OpenRouter
API key and configure your allowed and blocked providers before running it.
The runner imposes no token cap and rejects truncated replies.

## graph

Graph outside. Loops inside.

Software decides where a job may go. The model judges inside the steps that need it. A loop is a cycle with a budget, not a strategy.

Use this when an agent workflow has branches, parallel work, retries, approvals, or more than one specialist. Skip it for a one-shot fix with an obvious stop.

### Install

Cursor:

```bash
mkdir -p ~/.cursor/skills
cp -R graph ~/.cursor/skills/graph
```

Claude Code / Codex / Kimi:

```bash
cp -R graph ~/.claude/skills/graph
cp -R graph ~/.codex/skills/graph
cp -R graph ~/.kimi-code/skills/graph
```

Then invoke `/graph` on a real workflow. Ask it for the diagram, the node contracts, and one executable tracer path. Do not accept a pretty flowchart as the deliverable.

## What this repo is

A public shelf for skills we would use on a client job tomorrow. Not a dump of every prompt we have bookmarked.
