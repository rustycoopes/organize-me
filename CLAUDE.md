# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

This repository is currently empty. Update this file as the project is built out to document build/test commands, architecture, and any non-obvious conventions.















\## Git Workflow \& Security Rules





\- \*\*Strict Environment Security\*\*:

&#x20; - Never stage or commit `.env` or `.env.local` files. Make sure they are listed in `.gitignore`.

&#x20; - Never commit files containing active API keys or credentials.

\- \*\*Minor changes\*\* (docs, small fixes): commit directly to the current branch with a meaningful message.

\- \*\*Major changes\*\* (new features, structural refactors, significant behaviour changes): create a new branch before starting work. Name the branch descriptively (e.g. `feature/prompt-versioning`, `refactor/file-storage`, `fix/gemini-error-handling`). Commit locally with a meaningful message once the changes are finalised. Do not push or merge without being asked.





\## GitHub Issues

\- When creating GitHub issues, always use the **OrganizeMe** project within GitHub (the GitHub Projects board linked to this repository).

\- Assign issues to the OrganizeMe project when creating them via `gh issue create`.



\## Documentation

\- \[README] (README.md) — project overview, setup, and run instructions; keep this accurate after every change

\- \[ChangeLog] (docs/changelog.md)

\- \[Technical Approach] (docs/technical-approach.md)

\- \[PRD] (docs/prd.md) 

\- \[Project Status] (docs/project-status.md)

\- Update the files in the docs folder after any  changes, updates or milestones.



