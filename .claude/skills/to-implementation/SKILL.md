---
name: to-implementation
description: Implement the new feature onto a branch. Ensure there is a loop to confirm implementation.   When the user asks to implement a PRD
---



Implement the work described by the issues.
When starting the issue, move the status to inprogress.

Read only the relevant per-slice spec for this issue — `docs/platform-restructure/WBS/slice-R<N>.md` (each embeds
the schema, endpoints, and utilities that slice needs). Don't load the full
`docs/platform-restructure/platform-restructure-prd.md`, PRD, or technical-approach unless a specific question requires it.

Use /tdd where possible, at pre-agreed seams.

Ensure to ask any questions if there is any lack of clarity in what needs doing. 
Interview the user for any questions and show the plan.

Treat this chnage as a major feature and follow the steps defined in claude.md to create a new branch and update documentation. 

Assume mulitple agents are running so use a seperate directory / worktree for this work

Implement this feature as efficiently as possible, use sub-agents where appropriate.

Once the implementation is working, do a compare the work against the to ensure all item are accounted for
Once done, perform a through code review the work.  use the code-review-master and code-quality-guardian agents to find improvements.
If chnages are recommended, implement them now. 
For all other suggested improvements Create a GitHub issue with the status of intake. And a label with the slice name. Also add a label  "modelsuggested". 

Commit all outstanding changes to GitHub with a meaningful message. Push the changes to remote. Then raise a PR to merge this all into main. Make sure that the Git Hub build completes correctly and any deployment is successful.

Once the build and deployment is successful, Mark the issue as done and add the branch name into the comments. 