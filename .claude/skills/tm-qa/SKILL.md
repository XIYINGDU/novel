---
name: tm-qa
description: 天幕红尘 出片质检与判定入账。Scout/HD/口型/配音/成片出来后、xiying 看片给反馈后使用，把每个问题记到 defects.jsonl。
---

# tm-qa：每个判定都入账

1. 视频按 step=1 出接触表逐帧看（V-QA-EVERY-FRAME）；音频听关键句
   有人脸的情绪镜头，再跑机器量尺（V-QA-FACE-METRIC）：
   `uv run -q --python 3.11 --with mediapipe==0.10.21 --with opencv-python-headless python 天幕红尘/loop/tools/face_metrics.py <clip...> --step 2`
   悲恸/冷硬镜头 `读成笑` 必须为 0。量尺和人眼不一致时，以人眼为准，并把分歧记下来（量尺本身也要校准）
2. xiying 的看片意见原话也要入账，一条问题一行，加 `--source xiying`（计入分数卡「打回」）
   出片脚本已自动跑量尺：情绪镜头读成笑 >0 会自动记一行 `source: machine, verdict: pending`。
   逐条人眼复核：确认是问题 → 另记一行 open；量尺误报 → 记一行 verdict=rejected 并写原因（量尺校准用）
3. 每条问题先「由表及里」问一次：这是哪一层的错？
   剧作 / 史实 / 分镜 / 锚点 / 提示词 / 参数 / 模型 / 后期 / 平台。
   如果是重抽或换种子才好的，fix 里要如实写「重抽」「换种子」，复盘靠它识别治标
4. 记账（在 `novel/` 下）：
   ```
   uv run -q --with pyyaml python 天幕红尘/loop/tools/loop.py qa --ep 01 --shot 25 --version p3-v0.1 \
     --stage scout --frames f3-f9 --tag wrong_expression --symptom "悲恸镜头嘴角上扬" \
     --layer 锚点 --rule V-ANCHOR-STATE-LEAK --fix "" --verdict open
   ```
   - tag 用短英文，同类问题沿用已有 tag（先 `grep -o '"tag": "[^"]*"' 天幕红尘/loop/ledger/defects.jsonl | sort | uniq -c`）
   - 对不上任何规则就不填 --rule，复盘会把它列为盲区
   - 修好后再记一行 verdict=fixed，写清怎么修的
5. 选种 / 晋级时同样记一行 verdict=accepted，写选中的种子和理由

## 只记观测到的
推断（比如「负向词里有 X，所以当时出过 X」）不是判定。要记也只能记成 `source: inferred-from-neg`、`verdict: unverified`。
2026-11-17 首轮补录犯过这个错，把预防性的负向词当成了缺陷。
