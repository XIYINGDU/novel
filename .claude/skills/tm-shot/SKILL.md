---
name: tm-shot
description: 天幕红尘 视频镜头生成前的规则合成。写任何新镜头的提示词、i2i 首帧、Scout/HD 脚本、Flow 提示词之前使用；也用于改写旧镜头。
---

# tm-shot：生成前先编译规则

规则库：`天幕红尘/loop/rules/`。不要凭记忆写提示词。

0. 先打开剧本和 `build_*` 里的镜头定义，确认这一镜有没有台词、口型、字幕时长。提示词不能和台词冲突（例：写了 lips closed 但这一镜要说话）
1. 给每个镜头打标签（见 `天幕红尘/loop/README.md` 常用标签），再加 `char:<角色>`、`prop:<道具>`
2. 在 `novel/` 下运行：
   `uv run -q --with pyyaml python 天幕红尘/loop/tools/loop.py compile --kind video --tags <标签> --ep <NN>`
   台词镜头另跑一次 `--kind audio`，标签加 `lipsync`、`dialogue`
3. 把 `prompt 追加` 和 `neg 追加` 并入镜头定义，`参数` 写入脚本，`流程/红线清单` 逐条打勾后再开 G4
4. ［候选］规则照样执行，但在镜头定义里注释 `# candidate: <ID>`，便于回归对比
5. 如果某条规则和镜头需要冲突（比如有意违背），不要静默跳过：写进 `天幕红尘/loop/ledger/open_questions.md`，问 xiying
6. 新版本不要复制上一版的 build_vNN.py 整体改；能复用的 import，镜头差异放数据（hd_plan.json / 镜头定义）
