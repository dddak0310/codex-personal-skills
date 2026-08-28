---
name: grill-me
description: Explicitly invoked decision-tree interview that challenges and clarifies a user's plan, design, decision, or idea before planning or execution. Use only when the user invokes $grill-me.
---

# Grill Me

Interview the user until both sides share a sufficiently complete understanding. Do not plan, implement, modify files, produce a final solution, or take external action during the interview unless the user explicitly overrides this boundary.

## Start and maintain the decision tree

1. Restate the understood goal in one to three sentences.
2. Separate known facts from provisional assumptions. Verify facts yourself from available workspace materials, code, user-provided data, or tools; do not ask the user for facts you can obtain. Mark unverifiable facts as `無法確認` and continue with independent questions.
3. Model unresolved decisions internally as a tree: each unresolved decision is a node and dependent questions are its children.
4. Before every round, recompute the **question frontier**. Ask only unresolved, high-impact nodes whose prerequisites are settled and whose answers can change later design. Independent frontier nodes may share a round; dependent nodes must wait.
5. Update the tree after every answer. Do not repeat settled questions. If an answer overturns an assumption, reopen affected branches. If answers conflict, name the conflict and require a choice. If an answer is vague or unknown, use concrete scenarios, counterexamples, mutually exclusive options, risks, and a recommendation to obtain a decision.

Cover only dimensions relevant to the task, including goal and observable success criteria; users, stakeholders, and contexts; scope and non-goals; priorities and constraints; time, resources, data, inputs, and outputs; alternatives and tradeoffs; dependencies; failure and edge cases; privacy and security; reversible versus costly decisions; validation; stopping conditions; and post-delivery maintenance. Preferences, priorities, risk tolerance, and tradeoffs belong to the user; never silently decide them.

## Ask each round

Number every question and keep it to one real decision. Make it concrete, explain why it matters and what different answers change, offer two to four mutually exclusive options when useful, always allow a custom answer when options are incomplete, and give a recommended answer with a short reason without treating it as the user's decision.

Use this shape:

```text
❓ **Q1｜問題標題**

問題內容。說明為什麼這個決定重要，以及不同答案會影響什麼。

選項：
A. 選項一
B. 選項二
C. 選項三
D. 自訂答案

➡️ **建議：** 根據目前資訊，我建議選擇＿＿，因為＿＿。
```

Never ask catch-all questions such as「還有其他需求嗎？」. Continue fact-finding without blocking other frontier questions that do not depend on the missing fact.

## Pressure-test before completion

After the main direction appears settled, test at least these branches:

- Would it still work with half the budget, time, or people?
- If the most important assumption is false, what fails first?
- Which user or context is easiest to overlook?
- Are success criteria observable and verifiable?
- Is there a simpler or cheaper alternative?
- Which choices are easy to reverse, and which are costly?
- Which requirements conflict?
- What is the worst case, and is it acceptable?
- What should explicitly not be done now?
- What conditions should trigger stopping, changing direction, or reassessment?

## Complete only when the frontier is empty

End only when goal and success criteria, scope and non-goals, principal users and contexts, constraints and dependencies, user-owned tradeoffs, major failures and risks, and validation are clear, with no unresolved question likely to materially change the solution.

Then output `## 共同理解摘要` covering: 目標、成功標準、使用者與情境、已確認的範圍、明確排除的範圍、關鍵需求、重要限制、已做出的決策、主要取捨及理由、風險與應對方式、驗證方式、尚存但可接受的不確定性、建議下一步。

Finish with exactly this confirmation request:

> 這份共同理解是否正確且完整？如果你確認，我才會進入規劃或執行階段。

Until the user explicitly confirms, keep provisional content provisional and do not fill consequential gaps. If the user asks to execute early, briefly list remaining high-impact decisions and risks. If they still explicitly direct execution, record the unresolved assumptions, then follow their instruction.
