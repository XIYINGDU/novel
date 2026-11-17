# 天幕红尘 制作闭环（loop/）

规则库是唯一真相源。`视频/AI短剧制作经验总结.md` 退为叙述版，新经验只进 `rules/`。

## 一个环

```
 ┌──── rules/*.yaml ◄──────── 复盘 /tm-retro（提案 → 回归 → xiying 批）
 │         │                              ▲
 │   /tm-shot compile（按标签合成）        │
 │         ▼                              │
 │   剧本 / 镜头 → 生成 → /tm-qa 判定 → ledger/defects.jsonl
 └── 剧本线 /tm-script-review 也读同一库
```

## 四个工序（各落在环上哪一步）

| 工序 | 做什么 | 落点 |
|---|---|---|
| 去粗取精 | 合并重复负向词、退役闲置/失效规则、经验文档只留叙述 | `lint` 重复词告警；复盘「闲置规则」 |
| 去伪存真 | 每条规则必须有证据路径；平台规则 30 天过期重验；史实回原著章节；候选必须过回归才能转正 | `lint` 证据检查；`ledger/golden.yaml` |
| 由此及彼 | 规则按 `scope` 标签命中，一镜的教训自动作用到同类镜头、别的角色、别的集，甚至反推到剧本 | `compile`；`S-SCRIPT-TO-SHOT-FILMABLE` |
| 由表及里 | 每条缺陷归到根因层（剧作/分镜/锚点/提示词/参数/模型/后期/平台/史实）；识别「治标」（重抽、换种、堆负向词） | `retro` 根因统计与 ⚠ 治标标记 |

## 三层递归

1. 镜头层：每次 Scout/HD 出片 → `/tm-qa` 记判定
2. 集层：一集（或一段）交付 → `/tm-retro` 复盘 → 规则提案
3. 管线层：复盘也审视规则库和工具本身（字段不够、标签缺失、工具误判）→ 改 `loop/` 自身。改动同样走「提案 → xiying 批」

## 自我升级的闸门

- 新规则一律以 `candidate` 进库，写 `regress` 回归镜头
- 在 `ledger/golden.yaml` 相关镜头重跑 Scout，与旧判定对比；变好才提 `active`
- 每次升级都由 xiying 批准（vm 只提案，不自批）
- 平台规则 `last_checked` 超过 30 天，`lint` 告警，需重验

## 规则字段

`id`  `status`(active|candidate|deprecated)  `layer`  `symptom`  `root_cause`  `scope`(标签，`ep:NN` 为约束)
`action.{prompt,neg,params,process}`  `evidence`(相对 loop/ 或 天幕红尘/)  `regress`  `last_checked`  `note`

常用标签：`face_closeup` `emotion_negative` `back_view` `hands` `prop_closeup` `text_sign` `action_multi_pose`
`precise_end_state` `flf2v` `gunshot` `fall` `dialogue` `keyline` `lipsync` `phone_call` `night_lowlight` `scene_change`
`flow` `colab` `qwen_i2i` `wan` `char:<名>` `prop:<名>` `flashback` `deliver`

## 命令

```
L() { uv run -q --with pyyaml python 天幕红尘/loop/tools/loop.py "$@"; }   # 在 novel/ 下
L lint
L compile --kind video --tags face_closeup,emotion_negative,crying,char:罗慧娟 --ep 01
L qa --ep 01 --shot 25 --version p3-v0.1 --stage scout --tag wrong_expression --symptom "..." --layer 提示词 --rule V-GRIEF-AU-PROMPT
L retro --since 2026-11-17
python3 天幕红尘/loop/tools/mine_history.py 天幕红尘/视频 > 天幕红尘/loop/ledger/mined.json   # 挖历史负向词：这是「担心」的证据，不是「缺陷」的证据
uv run -q --python 3.11 --with mediapipe==0.10.21 --with opencv-python-headless python 天幕红尘/loop/tools/face_metrics.py <clip...>   # 表情量尺
```

## ledger/

- `defects.jsonl`：判定流水（`source: backfill` 为 v0.2–p2 补录）
- `mined.json`：历史脚本里追加的负向词统计（只说明当时担心什么，不能当缺陷证据）
- `golden.yaml`：回归镜头
- `experiments/`：每次回归实验的假设、前测、结论（回归产物在 `视频/regress/<日期>_<名>/`）
- `open_questions.md`：要 xiying 定的事
- `retro/YYYY-MM-DD.md`：复盘记录
