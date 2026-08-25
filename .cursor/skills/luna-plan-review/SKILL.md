---
name: luna-plan-review
description: >-
  Reviews and improves implementation plans with GPT 5.6 Luna 1m Max before
  coding, then restores the previously selected model for the build. Use when
  entering Plan mode, drafting an implementation plan, planning a feature,
  refactor, migration, or other build.
---

# Luna plan review

For every implementation plan, use **GPT 5.6 Luna 1m Max** as a second-pass plan reviewer before building. Keep planning and building separate.

## Model-switching rule

This skill describes a workflow; it cannot directly control Cursor's model picker. Record the model selected before the review, then use Cursor's model selector to choose **GPT 5.6 Luna 1m Max**. After the review, restore the recorded model before implementation.

If **GPT 5.6 Luna 1m Max** is not available in the model selector, stop and tell the user. Do not silently substitute another model or claim that the review was performed by Luna.

## Workflow

1. **Enter Plan mode.** Do not edit project files while drafting or reviewing the plan.
2. **Draft the initial plan** with:
   - goal and acceptance criteria;
   - affected files, systems, and dependencies;
   - ordered implementation steps;
   - test and verification strategy;
   - risks, assumptions, and unresolved decisions.
3. **Save the previous model selection** before switching models.
4. **Switch to GPT 5.6 Luna 1m Max.**
5. **Review and revise the plan.** Check for:
   - missing requirements, edge cases, and failure paths;
   - unnecessary complexity and simpler alternatives;
   - incorrect assumptions about the repository or APIs;
   - migration, compatibility, security, and rollback risks;
   - tests that prove the acceptance criteria;
   - ordering and dependencies between steps.
6. **Present the review** in this format:

   ```text
   Plan review
   - Strengths: ...
   - Risks or gaps: ...
   - Suggested improvements: ...

   Revised plan
   1. ...
   2. ...

   Verification
   - ...
   ```

7. **Restore the previous model selection.**
8. **Build only after the plan is accepted** or the user explicitly asks to proceed. Switch from Plan mode to Agent mode, follow the revised plan, and verify the result.

## Same-request planning and building

If the user asks for both a plan and implementation in one request, complete the Luna review first, restore the previous model, then build from the revised plan. If the user asks only for a plan, stop after presenting the review and revised plan.

## Quality rules

- The revised plan must be grounded in the actual repository, not generic advice.
- Do not hide disagreements between the initial plan and the review; call out material changes.
- Ask a focused question when an unresolved choice materially changes the implementation.
- Do not claim a model switch, review, or approval that did not happen.
- Keep the plan proportional to the task. Small changes still get a concise review.
