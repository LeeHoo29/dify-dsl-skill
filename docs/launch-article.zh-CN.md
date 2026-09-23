# 告别在 Dify 画布里拖节点：用自然语言生成、排版、校验并发布工作流

使用 Dify 搭建 Workflow 时，真正花时间的通常不只是写节点逻辑。

你还需要处理节点连线、变量选择器、Code 输入输出契约、画布位置、版本字段、插件绑定和导入后的 Draft/Published 状态。工作流一复杂，重复拖动节点和手工维护 YAML 很快就会变成主要成本。

我把这套流程整理成了一个开源 Skill 项目：

https://github.com/LeeHoo29/dify-dsl-skill

它的目标很直接：

> 用自然语言描述需求，生成可用、合理、可维护、自动排版的 Dify DSL，并在明确授权后同步到本地 Dify，不再依赖日常鼠标拖动来整理画布。

![30 秒演示](https://raw.githubusercontent.com/LeeHoo29/dify-dsl-skill/main/assets/demo.gif)

## 从一句需求到 Workflow

例如下面这段自然语言：

```text
创建一个客户反馈分流 Workflow，接收客户 ID、1-5 星评分和反馈正文。
识别低评分和退款、破损、缺失、延迟等风险词，将风险反馈安排优先跟进，
其余反馈进入标准归档；无效输入返回可操作的修改建议。
```

Agent 不只是输出一份 YAML，而是执行一条完整流水线：

```text
自然语言需求
-> 图结构和节点契约
-> 独立 Python Code 源码
-> Code 嵌入同步
-> ELK 自动布局
-> DSL 与 portable 校验
-> 可选的本地 Draft 导入
-> 显式 Workflow 发布
-> Draft/Published 严格验证
```

项目中提供了可以直接导入的 Showcase：

https://github.com/LeeHoo29/dify-dsl-skill/tree/main/showcase/customer-feedback-triage

它不依赖模型提供商、插件、Dataset 或外部 API，包含输入校验、两级判断、三条结果分支和 Variable Aggregator 汇合，适合用来理解这套工作方式。

## 为什么 Code 不能只写在 YAML 里

Dify 导出的 DSL 必须把 Code 节点代码写进 `data.code`，但这不意味着 YAML 应该成为源码仓库。

项目采用的规则是：

```text
独立 .py 文件 = 唯一源码
DSL data.code = 生成产物
```

每个受管理的 Code 节点都会在 `data.desc` 中声明：

```text
Code source: docs/dify-code-nodes/example.py
```

同步器会检查：

- Python `main(...)` 参数是否与 Code 节点输入一致；
- 返回字段是否与 DSL 输出声明一致；
- 源码路径是否越界；
- YAML 内嵌代码是否发生漂移。

这样 Code 可以使用正常的编辑器、单元测试和代码审查，而不是在长 YAML 字符串里维护两份实现。

## 自动排版不是装饰

“YAML 可以导入”不等于“Workflow 可以交付”。

如果节点重叠、Iteration 子节点位置错误、边被容器遮挡，用户仍然要回到 Dify 画布中手工整理。

项目使用固定版本的 ELK 布局器，负责：

- 左到右的 DAG 排版；
- 条件分支；
- Loop/Iteration 子图；
- 节点尺寸和绝对位置；
- viewport；
- 重叠检测和幂等检查。

相同 DSL 重复执行布局不会继续漂移，检测到重叠则直接失败。

## 本地 Dify 同步与发布

第三个 Skill `dify-local-sync` 面向用户自己控制的本地 Docker Compose Dify。

它可以：

- 安全配置 `INNER_API_KEY`；
- 默认 dry-run；
- 创建或覆盖 Draft；
- 显式发布 Workflow 版本；
- 校验 Workspace、DSL SHA、导出的 graph 和 Published Workflow 指针。

Inner API 是 Dify 官方源码中的内部可信接口，但不是面向第三方的稳定公开 API。因此该能力被限制为本地 self-hosted Docker，不支持任意远程主机，也不会把 `/inner/api` 暴露到公共 nginx。

Dify Cloud 或远程 Draft 同步应优先使用官方 `difyctl`。

## 安装

为 Codex 和 Claude Code 安装三个 Skill：

```bash
npx skills add LeeHoo29/dify-dsl-skill \
  --skill dify-dsl \
  --skill dify-python-code-node \
  --skill dify-local-sync \
  -g -a codex -a claude-code -y
```

也可以直接对 Agent 说：

```text
请从 https://github.com/LeeHoo29/dify-dsl-skill 安装 dify-dsl、
dify-python-code-node 和 dify-local-sync。
本次只安装 Skill，不修改 Dify，不导入 DSL，也不发布 Workflow。
```

## 当前边界

- 自动兼容审计基线是 Dify 1.17.1、App DSL 0.7.0；
- Workflow 和 Chatflow 是主要支持范围；
- Agent/model-config 和 RAG Pipeline 仍属于实验性支持；
- 本地发布依赖 Dify 内部接口，因此跨版本使用前必须先 dry-run；
- 真实本地 Dify 1.15.0 已完成过导入和发布演示，但其导出 DSL 为 0.6.0，当前严格版本一致性检查会主动拒绝。

项目采用 MIT License。如果你正在维护复杂 Dify Workflow，欢迎试用、提交版本兼容案例或改进建议。

GitHub： https://github.com/LeeHoo29/dify-dsl-skill
