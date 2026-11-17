---
name: tm-script-review
description: 天幕红尘 剧本审稿（agy 写，vm 审）。审 天幕红尘/剧本/第NN集.md 或给 agy 写提示时使用。
---

# tm-script-review

1. 编译规则（在 `novel/` 下）：
   `uv run -q --with pyyaml python 天幕红尘/loop/tools/loop.py compile --kind script --tags <出场角色 char:… / 道具 prop:… / flashback / gunshot> --ep <NN>`
2. 给 agy 写提示时，把命中的红线和对应原著章节原文一起给它，不要只给改编方案
3. 审稿按清单逐条过，另外做两件事：
   - 史实：地点、服装、人物关系回原著章节核对，引用章号
   - 可拍性：按 S-SCRIPT-TO-SHOT-FILMABLE 预检，不可拍处标 `[拍摄注]`
4. 发现的每个问题入账，用 `loop.py qa`，--stage script，--layer 剧本 或 史实，--shot 填场号
5. agy 出现新的常犯错误，没有对应规则的，不要自己加 active 规则，留给 /tm-retro 提案
