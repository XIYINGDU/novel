# 待 xiying 定的问题（复盘产出，定了就转成规则或删掉）

- [2026-11-17] ~~冷开场是否回原著~~：vm 首轮把托头的人错写成老九（实为戴梦岩），且没查改编方案。方案本就有意拆分 第1集/第18集（C-COLDOPEN-SPLIT）。xiying 基于错误前提选了「回原著」，已暂停执行、重新确认 → **xiying 定：照方案拆开**，第 1 集素材不动
- [2026-11-17] ✔ 已批：V-ANCHOR-STATE-LEAK 回归：给 苏玉平/林雪红/罗慧娟 各做一张中性锚点，重跑 21b、24c 的 Scout（约 2 次 G4 启动）；V-NEG-SCENE-BLEED 回归同机合跑；停止 fork build 脚本
- [2026-11-08] 21 号 InfiniteTalk A/B 未定案（脸稳口型对，但 480p 偏糊、跟定妆照走）
- [2026-11-17] ✔ 24c「礼貌假笑」：xiying 不记得，量尺测 smile_max 0.086 → 定为未观测，已从 golden.yaml 移除
- [2026-11-17] 续段（p2）母带比开篇响 4 LU（-15.1 对 -19.2 LUFS），v0.1 起就有。要不要把 p2 统一到 -19.2 LUFS，再出 v0.3 / v0.16？（纯本地操作，不花算力）
- [2026-11-17] ✔ 21b 已替换：续段 v0.2、试片 v0.15。旧版 clips_alt/clip_21b_v01.mp4、sync_21b_v01.mp4。等 xiying 看片
- [2026-11-17] ✔ 已批并已改：p3 分镜（`视频/ep01_p3/分镜表.md`）compile 时发现两条规则作用域过宽：① C-COLDOPEN-SPLIT「第 1 集不出戴梦岩」与方案第 1 集「戴梦岩片场改道」冲突，原意只指冷开场 → 建议改为冷开场限定；② V-GRIEF-AU-PROMPT 仅凭 face_closeup 就命中，非哭戏近景也被加 lips closed → 建议 scope 改为需 crying/emotion_negative
- [2026-11-19] **V-SCOUT-THEN-HD 修订提案**（状态：待主公批）：现行规则默认“Scout 定种子，HD 照搬”，这个前提在 ep01 p3 被推翻——`s7c`、`s7j` 在同一种子下 HD 与 Scout 动作不一致（均已在 `ledger/defects.jsonl` 核实：defect #47［第 47 行］`s7c` Scout s2 未举机，同种子 HD 却把传呼机举到耳边当电话；defect #48［第 48 行］`s7j` Scout s4 闭嘴，同种子 HD 第 3–4 段张大 O 嘴、表演过火；defect #50［第 50 行］`s7c` 提示词写死传呼机别在腰带、手不过胸并重出 HD s3/s4，两条均未举机；defect #51［第 51 行］`s7j` 重出 4 种子仍在中段张 O 嘴，`stunned/freezes/eyes widen` 一类词诱发惊呼）。提案三点：
  1. 动作或道具敏感的镜头，HD 至少出 2 个种子再做 QA；
  2. “怔住”一类描写改写成 `goes quiet, face still` 这类可见动作；
  3. 回归方法：用 `s7c`、`s7j` 复测，看 HD 与 Scout 动作是否一致。
