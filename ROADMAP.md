# GitHub Issue Draft: ResearchClaw 全流程科研（CLI 对话式）路线图

> 建议 Issue 标题  
`[Roadmap] 实现科研全流程 CLI 对话化：从文献调研到实验与写作`

## 背景

目标是让 ResearchClaw 支持科研论文完整流程，仅通过命令行/对话完成主要工作：

1. 文献调研与筛选  
2. 问题提出与假设形成  
3. 实验设计与执行  
4. 统计验证与消融分析  
5. 论文写作与迭代修改  
6. 复现材料打包与提交前检查

## 总目标（Definition of Success）

- 用户可在终端完成从 topic 到 draft/package 的端到端流程。
- 核心步骤均有明确 CLI 命令、结构化产物和可追溯记录。
- 实验可重放、结论可追证、写作可回链到实验与引用证据。

## 产品原则

- CLI-first：每个核心步骤必须有显式命令。  
- Traceable：关键决策和结果必须结构化落盘。  
- Reproducible：实验结果可基于配置和元数据重放。  
- Human-in-the-loop：关键节点要求用户确认。  
- Local-first：数据隐私与模型控制权优先。  

## 目标命令面（V1）

```bash
# A. 文献调研
researchclaw survey search "topic"
researchclaw survey triage --from saved_results
researchclaw survey map --topic "..." --out evidence_matrix.md

# B. 问题提出
researchclaw propose gap --from evidence_matrix.md
researchclaw propose question --gap G1
researchclaw propose hypothesis --question Q1

# C. 实验验证
researchclaw exp design --hypothesis H1
researchclaw exp run --plan EXP-001
researchclaw exp analyze --run RUN-001
researchclaw exp ablation --run RUN-001

# D. 论文写作
researchclaw write draft --template conference
researchclaw write revise --mode reviewer2
researchclaw write export --format latex

# E. 提交前检查
researchclaw submit check
researchclaw submit package --out submission_bundle/
```

## 里程碑与验收标准

### M1（2026-03-07 ~ 2026-04-15）：基础模型与命令骨架
- [ ] 定义科研对象模型：`project/question/hypothesis/dataset/experiment/run/result/paper_draft`
- [ ] 完成结构化存储与 ID/时间戳/provenance 关联
- [ ] 完成 `survey/propose/exp/write/submit` 命令组骨架
- 验收标准
- [ ] CLI 能创建并读取核心对象
- [ ] 关键对象在磁盘可追踪、可回放

### M2（2026-04-16 ~ 2026-06-01）：文献到问题提出
- [ ] 文献去重、相关性排序、证据抽取
- [ ] claim-evidence matrix 生成
- [ ] gap/question/hypothesis 命令可用
- 验收标准
- [ ] 从一组文献可生成可验证研究问题（含证据来源）

### M3（2026-06-02 ~ 2026-08-01）：实验编排与复现
- [ ] 实验计划 schema 与 run tracking
- [ ] 自动记录 seed、超参、git hash、环境、数据版本、日志
- [ ] baseline/ablation 标准流程
- 验收标准
- [ ] 仅凭 artifact bundle 可重放实验

### M4（2026-08-02 ~ 2026-10-01）：写作与证据一致性
- [ ] 由结构化资产生成论文草稿（abstract/introduction/related/method/exp/conclusion）
- [ ] claim-evidence 一致性检查器
- [ ] reviewer-mode 修订流程
- 验收标准
- [ ] 生成完整初稿，且核心 claim 可回链到实验和引用

### M5（2026-10-02 ~ 2026-12-01）：提交前闭环
- [ ] 提交前自动检查（引用、证据、复现、TODO）
- [ ] 复现材料打包导出
- [ ] 一键端到端 pipeline 脚本
- 验收标准
- [ ] 从 topic 到 submission bundle 全流程跑通

## Epic 拆解（建议作为子 Issue）

- [ ] EPIC: Structured research object model and provenance graph
- [ ] EPIC: Literature triage and evidence matrix pipeline
- [ ] EPIC: Gap detection and hypothesis generation
- [ ] EPIC: Experiment plan/run tracking and replay
- [ ] EPIC: Statistical validation and ablation toolkit
- [ ] EPIC: Draft writing pipeline with claim-evidence checks
- [ ] EPIC: Submission readiness and reproducibility packaging

## 建议标签与里程碑

- Labels: `roadmap`, `epic`, `P0`, `P1`, `P2`, `cli`, `agents`, `experiments`, `writing`, `reproducibility`
- Milestones: `M1-Foundation`, `M2-SurveyQuestion`, `M3-Experiment`, `M4-Writing`, `M5-Submission`

## 成功指标（KPI）

- 端到端完成率（topic -> draft/package）>= 70%
- 实验重放成功率 >= 90%
- 生成稿件人工重写比例 <= 40%
- 提交前发现缺证据/缺引用问题覆盖率 >= 95%

## 风险与缓解

- [ ] 文献筛选质量不足 -> 混合检索+排序+人工 checkpoint
- [ ] 结论过度自信 -> submit 前强制 claim-evidence 校验
- [ ] 实验不可复现 -> 元数据强制采集，重放作为准入门槛
- [ ] 命令复杂度膨胀 -> 固定命令语法 + 默认模板 + 渐进式参数

## 未来 2 周优先项（可直接开工）

- [ ] 实现科研对象 schema 与持久化
- [ ] 落地 `survey` 命令组（triage + evidence matrix）
- [ ] 在 `exp run` 增加复现元数据自动采集
- [ ] 在 GitHub 建好 milestones、labels、epic 子 issue
