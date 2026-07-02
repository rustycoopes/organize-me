---
name: to-implementation
description: Implement the new feature onto a branch. Ensure there is a loop to confirm implementation.   When the user asks to implement a PRD
---



Implement the work described by the issues.
When starting the issue, move the status to inprogress.


Use /tdd where possible, at pre-agreed seams.

Ensure to ask any questions if there is any lack of clarity in what needs doing. 
Interview the user for any questions and show the plan.

Treat this chnage as a major feature and follow the steps defined in claude.md to create a new branch and update documentation. 

Assume mulitple agents are running so use a seperate directory / worktree for this work

Implement this feature as efficiently as possible using multiple agents. When finished compare the changes to the original PRD and suggest at least 5 changes that would improve the code or align better with what is required. 

Once done, compare the work done to the original issue.  Suggest and implement 5 improvements.

Once done, use /review to review the work.

After the implementation, ensure all changes are commited to local git using a meaningful message. 

Commit all outstanding changes to GitHub with a meaningful message. Push the changes to remote. Then raise a PR to merge this all into main. Make sure that the Git Hub build completes correctly and any deployment is successful.

Once the build and deployment is successful, Mark the issue as done and add the branch name into the comments. 