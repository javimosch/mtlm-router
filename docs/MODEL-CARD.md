---
license: apache-2.0
tags:
  - router
  - dispatcher
  - tool-use
  - tiny-llm
  - mfl
  - machin
pipeline_tag: text-generation
---

# mtlm-7m-router3s384

A **7M-parameter dispatcher/router** trained end-to-end in pure
[machin/MFL](https://github.com/javimosch/machin). It sits in front of your
tools and assistants and turns each natural-language request into a typed,
calibrated routing decision — in ~15ms on CPU, fully self-hosted — and knows
when to say "not my job".

Successor of
[mtlm-7m-router2s384](https://huggingface.co/javimosch/mtlm-7m-router2s384):
same architecture, retrained on an expanded corpus (new phrasing stems +
4k multi-turn conversations). Head↔trunk agreement went **0.9275 → 1.000**.

## What it does

Every request gets a structured decision, not a guess. Three tiny linear
heads (`mhd1` format) read the hidden state at the last prompt position —
one forward pass, no tokens generated:

| head | question | holdout |
|---|---|---|
| decide (16 routes) | which route? | **97.6%**, ECE 0.012 |
| noul (yes/no) | should this escalate? | **98.9%** |
| score (ordinal 1–4) | how complex is it? | **97.9%**, adjacent-tier errors only |

Generative path (800 probes): tool-name **98.75%**, arg-value **95.2%**,
call-correctness **93.25%**.

## Routes

`calculator`, `get_weather`, `get_time`, `web_search`, `wikipedia`,
`read_file`, `write_file`, `http_get`, `send_email`, `translate`,
`run_shell`, `convert_units`, `set_reminder`, `save_note`, `chat`,
and **`escalate`** — emitted for requests beyond a dispatcher's pay grade
(long-form writing, code, analysis, planning, professional advice).

## The dispatcher endpoint

Served by [machin-anvil](https://github.com/javimosch/machin-anvil)
(pure MFL, OpenAI-compatible). One call — assess → gate → dispatch:

```bash
curl localhost:8097/v1/route -d '{"state":"what is the weather in Paris?","execute":true}'
# {"action":"tool_call","route":"get_weather","confidence":1.0,"p_yes":1.7e-06,
#  "tier":"2","reason":"ok","call":{"name":"get_weather","arguments":{"city":"Paris"}}}
```

Delegates (`action:"delegate"`) on: low confidence, `escalate` route,
noul p(yes) ≥ 0.5, or head-vs-generation disagreement — a wrong dispatch
requires the typed head *and* the generative path to be wrong in the same
direction.

## Swappable customer heads

Per-deployment route tables are ~7 KB `.head` artifacts trained on the
frozen trunk — no fine-tuning. A customer's tool vocabulary is a JSON
config of example phrases; `tools/head_studio.py` (in the
[mtlm repo](https://github.com/javimosch/mtlm)) validates → synthesizes →
trains → evaluates → emits the artifact. Demo 6-route IT-helpdesk head:
**100%** on leakage-filtered holdout.

## Usage (transformers)

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
tok = AutoTokenizer.from_pretrained("javimosch/mtlm-7m-router3s384")
model = AutoModelForCausalLM.from_pretrained("javimosch/mtlm-7m-router3s384")
ids = tok.apply_chat_template([
    {"role": "user", "content": "remind me to call the dentist tomorrow"},
], add_generation_prompt=True, return_tensors="pt", return_dict=True)
out = model.generate(**ids, max_new_tokens=80, do_sample=False)
print(tok.decode(out[0][ids["input_ids"].shape[1]:]))
```

## Architecture

Llama-compatible: dim 288, 6 layers, 6 heads (head_dim 48), SwiGLU hidden
768, vocab 4096, seq 384, RMSNorm eps 1e-5, RoPE theta 10000, tied
embeddings. ~7.2M params; int8 export is 8.06 MB. The entire serving stack
(tokenizer, inference, HTTP API, heads) is pure MFL.

## Honest limits

- 7M params: argument values can be sloppy — validate platform-side before
  executing tool calls.
- `noul`/`score` answer their fixed trained questions, not arbitrary
  criteria text.
- Chat answers are TinyStories-grade — this is a dispatcher, not a chatbot.
- Heads cannot evaluate relational predicates; phrase state so the
  discriminative tokens appear in the text.

---

# mtlm-7m-router3s384(中文)

一个用纯 [machin/MFL](https://github.com/javimosch/machin) 端到端训练的
**7M 参数调度/路由模型**。它部署在你的工具和助手之前,把每个自然语言请求转化为
类型化、经过校准的路由决策 —— CPU 上约 15ms,完全自托管 —— 并且懂得什么时候
说"这不是我的活"。

[mtlm-7m-router2s384](https://huggingface.co/javimosch/mtlm-7m-router2s384)
的继任者:架构相同,在扩展语料上重新训练(新增措辞词干 + 4k 多轮对话)。
决策头与主干的一致性从 **0.9275 提升到 1.000**。

## 工作原理

每个请求得到一个结构化决策,而不是猜测。三个微型线性决策头(`mhd1` 格式)
直接读取最后一个提示位置的隐状态 —— 单次前向传播,不生成任何 token:

| 决策头 | 回答的问题 | 留出集准确率 |
|---|---|---|
| decide(16 路由)| 走哪条路由?| **97.6%**,ECE 0.012 |
| noul(是/否)| 是否应该升级?| **98.9%** |
| score(1–4 级)| 复杂度多高?| **97.9%**,误差仅在相邻层级 |

生成路径(800 探针):工具名 **98.75%**,参数值 **95.2%**,调用正确率 **93.25%**。

## 调度端点

由 [machin-anvil](https://github.com/javimosch/machin-anvil) 提供服务
(纯 MFL,兼容 OpenAI 接口)。一次调用完成 评估 → 门控 → 分发:

```bash
curl localhost:8097/v1/route -d '{"state":"巴黎天气怎么样?","execute":true}'
```

出现以下情况时委托上级(`action:"delegate"`):置信度不足、`escalate` 路由、
noul p(yes) ≥ 0.5,或决策头与生成路径不一致 —— 一次错误的分发要求
类型化头和生成路径朝同一方向同时出错。

## 可插拔的客户决策头

每个部署的路由表是约 7KB 的 `.head` 文件,在冻结主干上训练 —— 无需微调。
客户的工具词汇表就是一个 JSON 配置文件;`tools/head_studio.py` 完成
校验 → 合成 → 训练 → 评估 → 产出工件。演示用 6 路由 IT 服务台决策头在
防泄漏留出集上达到 **100%**。

## 架构

Llama 兼容:dim 288,6 层,6 头(head_dim 48),SwiGLU hidden 768,
词表 4096,序列长 384,RMSNorm eps 1e-5,RoPE theta 10000,权重共享。
约 7.2M 参数;int8 导出仅 8.06MB。整个服务栈(分词器、推理、HTTP API、
决策头)均为纯 MFL 实现。

## 局限性

- 7M 参数:参数值可能不够精确 —— 请在平台侧校验后再执行工具调用。
- `noul`/`score` 只回答训练时固定的问题,不支持任意标准文本。
- 聊天能力为 TinyStories 级别 —— 这是调度器,不是聊天机器人。
