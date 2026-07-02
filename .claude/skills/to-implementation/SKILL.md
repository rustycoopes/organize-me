---
name: to-implementation
description: Implement the new feature onto a branch. Ensure there is a loop to confirm implementation.   When the user asks to implement a PRD
---



Implement the work described by the issues.
When starting the issue, move the status to inprogress.

Read only the relevant per-slice spec for this issue — `docs/slices/slice-N.md` (each embeds
the schema, endpoints, and utilities that slice needs). Don't load the full
`docs/implementation-plan.md`, PRD, or technical-approach unless a specific question requires it.

Use /tdd where possible, at pre-agreed seams.

Ensure to ask any questions if there is any lack of clarity in what needs doing. 
Interview the user for any questions and show the plan.

Treat this chnage as a major feature and follow the steps defined in claude.md to create a new branch and update documentation. 

Assume mulitple agents are running so use a seperate directory / worktree for this work

Implement this feature as efficiently as possible.

Once the implementation is working, do a SINGLE improvement pass: compare the work against the
original issue (and the slice spec) and list up to 3 concrete improvements that would improve the
code or align better with what is required. Get the user's approval, then implement only the
approved ones — do not implement improvements the user hasn't confirmed.

Once done, use /review to review the work.

After the implementation, ensure all changes are commited to local git using a meaningful message. 

Commit all outstanding changes to GitHub with a meaningful message. Push the changes to remote. Then raise a PR to merge this all into main. Make sure that the Git Hub build completes correctly and any deployment is successful.

Once the build and deployment is successful, Mark the issue as done and add the branch name into the comments. 