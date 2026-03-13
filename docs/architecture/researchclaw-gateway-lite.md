# ResearchClaw Gateway Lite 重构方案

## 结论

ResearchClaw **值得做一轮 gateway 化重构**，但**不值得照搬 OpenClaw 做一个同体量、独立进程级别的 Gateway 平台**。

推荐方向：

- **目标**：把现有单体服务重构成“有清晰 gateway 边界的单体”
- **不做**：现在就拆成独立 gateway 服务、独立协议栈、独立多节点控制平面

一句话：

> 学 OpenClaw 的职责分层，不学 OpenClaw 的系统体量。

---

## 1. OpenClaw 的 Gateway 在承担什么

从 `openclaw/src/gateway/*` 看，OpenClaw 的 gateway 是整个系统的运行时中枢，而不只是一个 HTTP 入口。

核心职责有六类：

1. 启动与总编排
   - server、channel manager、cron、control UI、plugin runtime、reload、health、tailscale 都由 gateway 启动和协调

2. 统一 auth 与接入策略
   - token/password/trusted-proxy/tailscale
   - auth surface 区分
   - rate limit

3. 统一 HTTP / WS / Hook / OpenAI-compatible 入口
   - health
   - control UI
   - hooks
   - OpenAI / OpenResponses endpoint
   - tools invoke

4. 统一 channel 生命周期与健康管理
   - 多账号 channel runtime
   - restart policy
   - runtime snapshot
   - manual stop / auto restart

5. 统一 method dispatch 层
   - send / talk / config / secrets / operator calls

6. 运维修复闭环
   - doctor
   - migration
   - startup repair
   - config/state integrity checks

这是一种“多客户端 + 多节点 + 多 surface + 多协议”的网关内核设计。

---

## 2. ResearchClaw 现在的真实结构

ResearchClaw 已经具备 gateway 的部分能力，但这些能力分散在多个层级，没有形成统一边界。

当前职责分布：

### 2.1 `app/_app.py`

负责：

- runner 启动
- chat manager 启动
- channel manager 启动
- mcp manager / watcher 启动
- cron manager 启动
- config watcher 启动
- API router 挂载
- console 静态资源托管

这意味着 `_app.py` 既是装配层，也是运行时拼装层。

### 2.2 `app/channels/manager.py`

负责：

- channel 生命周期
- queue / worker
- 同 session batching
- in-progress / pending
- send_text / send_event
- hot-swap

这已经接近 OpenClaw 的 channel runtime manager，只是还没被纳入统一 gateway 边界。

### 2.3 `app/routers/automation.py`

负责：

- automation token auth
- trigger ingress
- fanout dispatch
- hook payload mapping

这其实已经在做一部分 ingress gateway 的工作。

### 2.4 `app/routers/control.py`

负责：

- control plane status
- runtime snapshot 拼装
- channels / sessions / usage / bindings 等控制面接口

这其实已经承担了一部分 operator gateway 的职责。

### 2.5 结果

ResearchClaw 现在不是“没有 gateway 能力”，而是：

- **有 gateway 能力**
- **但没有 gateway 边界**
- **所以运行时职责被分散在 `_app.py` / routers / managers 中**

---

## 3. 为什么现在值得重构

不是为了“架构好看”，而是因为当前结构已经开始出现明显的扩展压力。

### 3.1 入口职责分散

现在外部接入面分散在：

- `/api/agent/*`
- `/api/automation/*`
- 各 channel ingress
- `/api/control/*`
- cron manual run / proactive send

问题：

- 每条路径都在各自处理 routing / auth / dispatch / runtime access
- 后续新增 webhook / trigger / IM channel / external automation 时，重复逻辑会继续增长

### 3.2 `_app.py` 过重

`_app.py` 当前既负责：

- 生命周期装配
- config shape normalization
- 组件依赖注入
- runtime startup ordering
- API route registration
- console hosting

这会导致后续任何 runtime 级重构都要优先改 `_app.py`。

### 3.3 dispatch 语义分散

当前有多套相似语义：

- channel send
- automation dispatch
- cron dispatch
- heartbeat last-dispatch
- session / agent routing

问题不是功能缺失，而是“同类语义没有同层统一”。

### 3.4 runtime snapshot 缺统一 contract

虽然已经有 `/api/control/status`，但：

- runner runtime
- channel runtime
- cron runtime
- automation runtime

还是由不同地方 best-effort 拼装，不是统一 runtime model。

### 3.5 未来路线图会继续放大这个问题

根据 `ROADMAP.md`，你后面要继续做：

- IM 主入口
- 多通道稳定运行
- 调度与主动推进
- 实验编排
- 可观测控制面

这些都天然更适合放在一个 gateway runtime boundary 内，而不是继续散在 router + manager 中。

---

## 4. 为什么现在不该照搬 OpenClaw

OpenClaw 的 gateway 是为它自己的产品边界服务的。ResearchClaw 现在直接照搬，会明显过度设计。

### 4.1 OpenClaw 的复杂度来源并不完全适用于你

OpenClaw 当前处理了大量 ResearchClaw 还没进入的场景：

- 多客户端协议面
- WebSocket method protocol
- trusted proxy / tailscale auth matrix
- mobile node / remote node
- plugin HTTP auth surface
- doctor / migration / restart sentinel
- OpenAI-compatible gateway APIs

这些都不是 ResearchClaw 现阶段的主增长点。

### 4.2 你的产品主线不是“通用 AI 网关”

ResearchClaw 的主线是：

- 科研工作流
- 持续研究线程
- 自动化调度
- 结果沉淀
- 可观测控制台

不是：

- 通用消息网关
- 多节点 agent fabric
- 通用客户端协议平台

所以如果现在按 OpenClaw 的规模去重构，会带来明显副作用：

- 目录复杂度上升
- 测试面扩大
- 运维语义变复杂
- 对核心科研功能迭代反而减速

---

## 5. 推荐目标：Gateway Lite

### 5.1 目标定义

在不改变当前部署方式的前提下，把 ResearchClaw 调整成：

- 一个 FastAPI 单体服务
- 一个清晰的 gateway runtime boundary
- 一个统一 ingress / dispatch / health contract

### 5.2 非目标

当前阶段不做：

- 独立网关进程
- 独立 WS 协议层
- device auth / tailscale auth
- OpenAI-compatible gateway façade
- doctor 平台
- 完整多节点控制平面

---

## 6. 推荐目录结构

建议新增：

```text
src/researchclaw/app/gateway/
  __init__.py
  runtime.py
  ingress.py
  dispatch.py
  health.py
  auth.py
  schemas.py
```

职责划分如下。

### 6.1 `gateway/runtime.py`

统一持有和暴露运行时依赖：

- runner
- chat_manager
- channel_manager
- mcp_manager
- cron_manager
- automation_store
- config_watcher

建议抽象：

- `GatewayRuntime`
- `GatewayRuntimeBuilder`
- `GatewayRuntimeSnapshot`

作用：

- 把 `_app.py` 的组件装配降成更薄的一层
- 让 router 不直接去碰 `req.app.state` 的每一个字段

### 6.2 `gateway/ingress.py`

统一定义“外部进入系统”的入口语义：

- automation trigger
- hook mapping
- future webhook ingress
- future IM/native ingress normalization

建议抽象：

- `IngressRequest`
- `IngressRoute`
- `IngressResult`
- `normalize_ingress_request()`

作用：

- 避免 automation / hook / future ingress 各自定义一套 request 语义

### 6.3 `gateway/dispatch.py`

统一定义“系统如何把输出送到外部”的语义：

- single dispatch
- fanout dispatch
- default last-dispatch
- session / user / channel / agent route resolution
- proactive send

建议抽象：

- `DispatchTarget`
- `DispatchPlan`
- `DispatchResult`
- `GatewayDispatcher`

作用：

- 把 cron、automation、heartbeat、manual send 的 dispatch 逻辑统一

### 6.4 `gateway/health.py`

统一定义 runtime snapshot contract：

- runner
- channels
- cron
- automation
- skills
- heartbeat

建议抽象：

- `build_gateway_status_snapshot()`
- `build_runner_snapshot()`
- `build_channel_snapshot()`
- `build_cron_snapshot()`

作用：

- control/status 和后续 observability 共享同一个核心模型

### 6.5 `gateway/auth.py`

先只做轻量 auth 收口：

- automation token check
- future webhook token check
- optional origin / IP policy
- optional rate limit

建议抽象：

- `GatewayAuthPolicy`
- `verify_gateway_token()`
- `verify_ingress_request()`

作用：

- 不再让 auth 逻辑散落在 router 里

### 6.6 `gateway/schemas.py`

统一定义 gateway 层核心模型：

- ingress request
- dispatch target
- runtime snapshot
- delivery result
- route binding result

作用：

- 避免这些关键模型散在 router / manager / types 中各自定义

---

## 7. 推荐迁移映射

这部分最重要：不是“以后可以考虑迁”，而是当前代码该怎么收口。

### 第一批：必须迁移

#### 从 `src/researchclaw/app/_app.py`

迁出到 `gateway/runtime.py`：

- runtime 组件创建顺序
- runner / chat manager / channel manager / mcp / cron / config watcher 的装配逻辑
- 组件状态注册到 `app.state` 的逻辑封装

保留在 `_app.py`：

- FastAPI app 定义
- CORS
- 路由挂载
- console 静态资源托管
- lifespan 调用 runtime builder

#### 从 `src/researchclaw/app/routers/automation.py`

迁出到：

- `gateway/auth.py`：automation token 校验
- `gateway/ingress.py`：trigger / hook payload normalization
- `gateway/dispatch.py`：dispatch dedupe / fanout expansion

router 保留：

- HTTP request -> Pydantic body
- 调 gateway service
- 返回 HTTP response

#### 从 `src/researchclaw/app/routers/control.py`

迁出到 `gateway/health.py`：

- runtime snapshot 拼装
- runner/channels/cron/automation 的状态收集

router 保留：

- HTTP route 暴露
- 参数处理
- 结果序列化

### 第二批：应该迁移

#### 从 `src/researchclaw/app/channels/manager.py`

不建议整体迁走，但建议补一层适配：

- 在 `gateway/dispatch.py` 中包一层 `ChannelManager` 的发送语义
- 在 `gateway/health.py` 中统一读取 channel runtime stats

也就是说：

- `ChannelManager` 继续做 channel runtime core
- `GatewayDispatcher` 负责把高层 dispatch 语义映射到 channel manager

#### 从 `src/researchclaw/config/watcher.py`

建议后续把“配置变更影响到哪些 runtime 组件”的 orchestration 逻辑收敛到：

- `gateway/runtime.py`
- 或 `gateway/runtime_reload.py`

否则 config watcher 容易继续成长成第二个 `_app.py`

### 第三批：暂时不要迁移

这些先不要动：

- `app/channels/<channel>/channel.py`
- `app/runner/manager.py`
- `app/runner/multi_manager.py`
- `app/crons/executor.py`

原因：

- 它们属于业务/执行核心
- 现在优先解决“边界问题”，不是“所有逻辑集中到 gateway”

---

## 8. 渐进式重构顺序

必须按这个顺序做，才能尽量不影响现有功能。

### Phase 1：建壳，不改行为

新增：

- `app/gateway/runtime.py`
- `app/gateway/health.py`
- `app/gateway/schemas.py`

做法：

- 先只是把 `_app.py` 和 `control.py` 里的拼装逻辑搬过去
- router / manager 对外行为不变

验收：

- `/api/health`
- `/api/control/status`
- 服务启动 / 停止
- 前端状态页

都不变

### Phase 2：收 ingress / dispatch

新增：

- `app/gateway/ingress.py`
- `app/gateway/dispatch.py`
- `app/gateway/auth.py`

做法：

- `automation.py` 只保留 route shell
- 把 token 校验、payload normalize、fanout expansion、dispatch 计划收走

验收：

- automation trigger
- hook
- cron manual run
- proactive send

行为不变

### Phase 3：统一 runtime context

做法：

- 定义 `GatewayRuntime`
- router 统一通过 dependency / `req.app.state.gateway_runtime` 访问运行时
- 逐步减少直接读 `req.app.state.runner/channel_manager/cron/...`

验收：

- 关键 router 无行为变化
- `_app.py` 复杂度下降

### Phase 4：补统一 runtime snapshot contract

做法：

- 统一 snapshot schema
- control/status 与其他 runtime 页面都用这一套 snapshot

验收：

- `StatusPage`
- `CronJobsPage`
- `ChannelsPage`
- `SessionsPage`

不会再各自拼一套状态口径

---

## 9. 预期收益

### 工程收益

1. `_app.py` 变薄
2. router 逻辑变浅
3. automation / hook / dispatch 不再分散重复
4. runtime snapshot 口径统一
5. 后续加 channel / webhook / external trigger 成本下降

### 产品收益

1. IM 主入口更容易继续做强
2. 自动化与主动推进更容易统一
3. 控制台可观测更稳定
4. 后续如果真要独立 gateway，也有清晰演进路径

---

## 10. 风险与控制

### 风险 1：边界重构碰到运行核心

控制：

- 不碰 runner / channel adapter / cron executor 的核心执行逻辑
- 先只抽 orchestration 和 schema

### 风险 2：状态口径改变导致前端异常

控制：

- 先保留原响应结构
- 在内部统一 snapshot，再由 router 做兼容映射

### 风险 3：automation / cron / channel dispatch 行为漂移

控制：

- Phase 2 前先补 regression tests
- 重点覆盖：
  - dispatch fanout
  - default last-dispatch
  - cron -> channel send
  - automation -> channel send

---

## 11. 建议补的测试

在开始重构前，先补这些测试最值：

1. gateway runtime startup/shutdown smoke test
2. control status snapshot contract test
3. automation ingress auth + dispatch expansion test
4. cron dispatch route resolution test
5. channel send via dispatcher parity test

优先覆盖这些文件附近：

- `src/researchclaw/app/_app.py`
- `src/researchclaw/app/routers/automation.py`
- `src/researchclaw/app/routers/control.py`
- `src/researchclaw/app/channels/manager.py`

---

## 12. 最终建议

### 现在建议做

- 做 `Gateway Lite`
- 先抽边界，再抽语义
- 保持单体部署方式不变

### 现在不建议做

- 独立 gateway 进程
- 独立 WS method protocol
- 仿 OpenClaw 的 auth matrix
- doctor / restart sentinel / multi-node 控制面

### 判断标准

只有当 ResearchClaw 后续明确进入这些场景，才考虑继续向 OpenClaw 式 gateway 演进：

- 多客户端并存
- 多节点 agent runtime
- 更强的 operator protocol
- 更复杂的 external integration surface
- 远程管理与租户隔离

在那之前，`Gateway Lite` 已经足够支撑：

- IM 主入口
- 自动化触发
- 多渠道接入
- 主动推送
- 控制台可观测
- 科研工作流持续推进

---

## 13. 推荐执行清单

可以直接按这个顺序开工：

1. 新增 `src/researchclaw/app/gateway/schemas.py`
2. 新增 `src/researchclaw/app/gateway/health.py`
3. 新增 `src/researchclaw/app/gateway/runtime.py`
4. `_app.py` 改成使用 `GatewayRuntimeBuilder`
5. `control.py` 改成使用 `gateway.health`
6. 新增 `src/researchclaw/app/gateway/dispatch.py`
7. 新增 `src/researchclaw/app/gateway/auth.py`
8. 新增 `src/researchclaw/app/gateway/ingress.py`
9. `automation.py` 改成薄 router
10. 补 regression tests

如果资源有限，至少先做前 5 项。

