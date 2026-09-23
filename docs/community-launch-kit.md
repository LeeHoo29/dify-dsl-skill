# Community Launch Kit

These drafts are intentionally different by channel. Replace only the bracketed channel-specific details before posting.

## Dify Community / Discord

```text
I open-sourced dify-dsl-skill, a Codex/Claude Code Skill pack that turns natural-language requirements into Dify Workflow/Chatflow DSL with canonical Python Code sources, deterministic ELK layout, and static validation.

It also supports explicitly authorized Draft sync and Workflow publication to a user-controlled local Docker Compose Dify. The repository includes a model-free Customer Feedback Triage showcase and a 30-second demo.

Repository: https://github.com/LeeHoo29/dify-dsl-skill

Current automated baseline: Dify 1.17.1 / App DSL 0.7.0. I would especially value reproducible exports or import results from other Dify versions.
```

## V2EX / Chinese Developer Community

Suggested title:

```text
[开源] 用自然语言生成、自动排版并发布 Dify Workflow 的 Agent Skill
```

Suggested opening:

```text
最近把自己维护 Dify Workflow 的流程整理成了一个开源 Skill。它不是 DSL 模板集合，而是让 Agent 从自然语言需求开始设计 graph、维护独立 Python Code 源码、用 ELK 自动排版、做导入前校验，并可选同步到本地 self-hosted Dify。

仓库里放了 30 秒 GIF、一个无模型依赖的可导入 Showcase、中英文文档和完整测试。希望收集更多 Dify 版本的真实导入反馈。

GitHub: https://github.com/LeeHoo29/dify-dsl-skill
```

## X / LinkedIn

```text
Open-sourced: natural language -> maintainable Dify DSL -> canonical Python Code -> deterministic canvas layout -> validation -> optional local publication.

Includes a 30-second demo and a model-free importable showcase.

https://github.com/LeeHoo29/dify-dsl-skill

#Dify #AgentSkills #LLMOps #OpenSource
```

## Awesome-Dify-Workflow PR Description

```text
## Workflow

Customer Feedback Triage: a model-free portable Workflow that validates customer feedback, routes invalid/priority/standard cases, and converges all branches through Variable Aggregators.

## Evidence

- App DSL 0.7.0
- no model provider, plugin, dataset, credential, or external API required
- canonical Python Code sources included
- source synchronization passes
- ELK layout check passes with zero overlaps
- portable validator reports 0 errors and 0 warnings
- focused Python behavior tests included

Source and documentation:
https://github.com/LeeHoo29/dify-dsl-skill/tree/main/showcase/customer-feedback-triage
```
