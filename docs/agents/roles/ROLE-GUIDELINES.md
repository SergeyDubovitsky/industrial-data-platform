# Role Prompt Guidelines

Use these rules for every role prompt.

## Required Shape

- Mission: why this role exists.
- Use when: when to invoke it.
- Inputs: files or context to read first.
- Checklist: ordered actions.
- Escalate when: cases where the role should stop and ask.
- Definition of Done: how the role knows it is finished.
- Output contract: exact handoff content.

## Rules

- Keep role prompts small and direct.
- Separate context, task, constraints, and expected output.
- Read first, narrow scope, then act.
- If a contract, architecture boundary, or write owner is unclear, escalate.
- Do not mix multiple roles in one handoff unless the task is explicitly small.
- Do not write vague output such as "looks good" without evidence.

## Skills

Use specialized skills only when they reduce risk:

- Use `documentation-engineer` for docs systems and navigation.
- Use `likec4-dsl` for LikeC4 edits or reviews.
- Use `python-clean-architecture` for Python layering and dependency direction.
- Use `context7` for version-sensitive external libraries or APIs.
- Use `solution-architect` for architecture trade-offs and ADR decisions.
