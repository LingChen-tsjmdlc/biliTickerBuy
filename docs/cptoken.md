# cptoken 模块分析

## 概述

`cptoken` 是本项目最核心的模块，负责生成 B 站会员购接口要求的 **ctoken** 参数。如果 ctoken 不合法，/prepare 和 /createV2 接口会直接拒绝请求（返回 100001）。

## ctoken 是什么

ctoken 是 B 站前端 JavaScript 中 `collect_token` 函数生成的一个 base64 字符串，本质是 **浏览器环境指纹 + 时间戳** 的编码。

请求时服务端用 ctoken 判断：

- 请求是否来自"真实浏览器"（而非脚本）
- 页面打开了多久（timer/timediff）
- 用户是否有操作行为（touchend/visibilitychange）

## 数据流

```
generate_browser_window_state()
  → BrowserWindowState（分辨率、滚动位置等）

init_ctoken_state(browser_window_state)
  → CTokenRuntimeState（m1~m9 派生 + base_timer + created_at_ms）

每次发请求前：
  runtime_state.snapshot(now_ms)     ← timer/timediff 随真实时间增长
    → CTokenSnapshot                 ← 冻结副本

snapshot.generate_prepare_ctoken()   ← /prepare 用（含 openWindow, beforeunload）
snapshot.generate_create_ctoken()    ← /createV2 用（不含上述两字段）
    → generate_ctoken(**kwargs)
      → base64 字符串
```

## 关键类

| 类                   | 职责                                    |
| -------------------- | --------------------------------------- |
| `BrowserWindowState` | TypedDict，模拟浏览器窗口/屏幕尺寸      |
| `CTokenRuntimeState` | 可变状态，timer/timediff 随时间自动增长 |
| `CTokenSnapshot`     | 某一时刻的不可变快照，可直接生成 ctoken |

## 编码格式

```
每个参数 → hex(1字节) + \x00 分隔
timer     → 2字节（高低位拆分）
timediff  → 2字节（高低位拆分）
最终      → base64 编码
```

参数顺序：`m1 → touchend → m2 → visibilitychange → m3 → m4 → beforeunload → m5 → timer[0] → timer[1] → timediff[0] → timediff[1] → m6 → m7 → m8 → m9`

## 参数含义

| 参数             | 来源                     | 说明                      |
| ---------------- | ------------------------ | ------------------------- |
| m1~m9            | 窗口状态派生（derive_d） | 浏览器指纹散列值          |
| touchend         | 随机 30~50               | 模拟用户触摸/点击事件计数 |
| visibilitychange | 随机 10~50               | 模拟页面可见性切换次数    |
| beforeunload     | =openWindow 或随机       | 模拟页面关闭事件          |
| openWindow       | 随机 1~3                 | 模拟 window.open 调用次数 |
| timer            | base_timer + 存活秒数    | 页面打开时长              |
| timediff         | 距开票时间秒数           | 时间偏移量                |

## 时间增长机制

这是 ctoken 最关键的逻辑：

- `CTokenRuntimeState.created_at_ms`：状态创建时的毫秒时间戳
- 每次 `snapshot(now_ms)` 时：
  - `timer = base_timer + (now_ms - created_at_ms) / 1000`
  - `timediff = (now_ms - ticket_collection_t) / 1000`
- 如果不模拟增长，服务端会检测到 ctoken 时间停滞 → 拒绝请求

## /prepare 与 /createV2 的差异

| 接口      | ctoken 方法                 | 包含字段                            |
| --------- | --------------------------- | ----------------------------------- |
| /prepare  | `generate_prepare_ctoken()` | 全部（含 openWindow, beforeunload） |
| /createV2 | `generate_create_ctoken()`  | 不含 openWindow, beforeunload       |

原因：createV2 阶段 B 站不再校验这两个前端事件字段。

## 关键函数

### `generate_ctoken(**kwargs)`

编码入口。参数为 -1 时自动填充随机值。timer 溢出取 0xff。

### `init_ctoken_state(...)`

从 BrowserWindowState 派生出 m1~m9。派生算法 `derive_d` 模拟了 B 站前端的散列逻辑：

```python
(values[index%16] + values[(3*index)%16] + 17*index) & 255
```

### `sim_ctoken_state(before_state)`

token 过期后重建用。相比直接 snapshot，touchend/openWindow/visibilitychange 有小概率递增，模拟用户持续操作。

## 调试

创建状态时自动打印 snapshot 到日志：

```python
logger.info(state.snapshot().to_dict())
```

可在日志中查看当前 ctoken 参数值，排查 100001 错误时对比较为方便。
