# 《天幕红尘》AI 短剧全流程制作经验总结（v0.2 → v0.13 实战沉淀）

> **2026-11-17 起，规则的唯一真相源是 [`天幕红尘/loop/rules/`](../loop/README.md)。** 本文保留为叙述版；新经验只进规则库（/tm-qa 入账 → /tm-retro 提案）。

> 适用范围：`天幕红尘/剧本/第01集.md` 等剧集 AI 影视制作管线（本地 macOS MPS + EasyColab G4 RTX PRO 6000 96GB）。  
> 底层算力调度与 API 接口规范详见：[EasyColab_自动化操作指南.md](file:///Users/duxiying/Documents/novel/EasyColab_自动化操作指南.md)。

---

## 一、剧本与分镜设计红线（决定成片上限）

1. **连续大动作必须拆镜，绝不塞进单一 AI 视频镜**：
   - Wan2.2 14B 约 `2–4s` 单镜无法可靠完成多段姿态转换。例如冷开场早先试图让背影一镜完成「下台阶 → 中第一枪 → 中第二枪 → 抬头看楼 → 倒地」，结果出现醉酒式晃动、向后蹲坐甚至 `orz` 磕头式蜷缩。
   - **正确做法（v0.13 实证有效）**：将复杂动作拆为因果咬合的短镜组——`01`（稳步直行 → 急顿微后仰）→ `02a`（胸前特写第二枪渗血 + 手掌压血）→ `02b1`（过肩仰望高楼说台词 + 失力微沉）→ `02b2`（中弹驻足起幅 → 双膝一软顺势侧扑瘫平）。
2. **邻镜景别、姿态、地标必须连续，消除「空间瞬移」**：
   - 当 `01` 末尾人已走出门口站在平坦石板地上，`02b2` 起幅就必须延续“站在平坦石板地上捂胸微顿”，不能凭空切回“跨上台阶”。
   - 严守剧作红线（详见 [影视改编方案_剧集版.md](file:///Users/duxiying/Documents/novel/天幕红尘/影视改编方案_剧集版.md)）：第 1 集叶子农严禁露正脸（用肩颈以下特写、背影与手部局部快切替代）；全剧核心道具（普通不锈钢打火机、纯金盔甲打火机、国旗贴章打火机、白色搪瓷大茶缸、全家福、名家题「见路不走」横幅）全片唯一锁定，严禁混用或重画。
3. **文字可读性红线**：
   - AI 视频禁止依赖多行小字阅读镜头（长传真、账单、合同文本），必须转化为人物动作与精炼对白；仅「见路不走」等少数大字视觉符号通过首帧固定或 8 参数单应透视贴图锁死。

---

## 二、视觉生成与防畸变规范（Qwen-Image-2.1 + Wan2.2 14B LightX2V）

1. **角色与核心道具的「唯一锚点」原则**：
   - **固定人脸/造型**：主要角色建立唯一规范参考图（如 [罗家明.png](file:///Users/duxiying/Documents/novel/天幕红尘/视频/ref/罗家明.png)、[still_08.png](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot/stills/still_08.png) 苏玉平、[still_05_ins2.png](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot/stills/still_05_ins2.png) 纽约裕香阁全家福），全部出场镜头通过 `Qwen-Image-2.1` `i2i_edit` 生成首帧，绝不靠纯文生图自由发挥换脸换衣。
   - **桌面小道具像素锁死**：如 `07` 桌面相框、`11a` 东墙「见路不走」横幅、05a/05c 桌角相框，分别在 [v06_patches.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v06_master/v06_patches.py) 用 8 参数透视变换（`Image.PERSPECTIVE`）把同一个高清源图贴入框内。
2. **「480p 极速探路 → 逐帧筛种 → 同机 720p 精修」两段式提速管线**：
   - 详见 [stage2_scout_hd_v10.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v10_fixes/stage2_scout_hd_v10.py) 与 [stage2_scout_hd_v13.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v13_fixes/stage2_scout_hd_v13.py)：
     1. 先开一台 G4 启动 ComfyUI 与 `wan22_i2v_flf2v` 包，按每镜 `2–3` 个种子跑 **`832×480` Scout 预览**（单条仅约 20 秒）。
     2. 在本地按 **`step=1`（逐帧接触表）** 用看图逐帧检查——**必须逐帧看**，普通隔 5 帧抽检会漏掉早帧掉落异物、多余手指、轻笑撇嘴或瞬间闭眼（如 `02a_s2` 早帧掉落红丝、`02b2_s1` 脚离地跳起、`05a/05c` 听电话时假笑或翻白眼）。
     3. 在 `hd_plan.json` 确认晋级种子后，复用**同一台已下载完 35GB 权重的温热 G4 会话**直接跑 `1280×720` HD，避免重复拉权重和无效废片计费。
3. **能用 `FLF2V` 首尾帧锁定，就不盲赌纯 `I2V`**：
   - 涉及精确动作起止点（如中弹前→中弹后胸口大面积洇红且五指直接压血、站立捂胸→向右侧四肢伸展平趴石地）时，先用 `i2i_edit` 由干净起幅图生成严格保持机位与背景的末帧图（至少出 `2–3` 个候选择优），再投入 Wan2.2 `FLF2V`（`WanFirstLastFrameToVideo`）。
4. **高频 AI 畸变与负向词库**：
   - 手部/器物特写（如 `10a` 左轮装弹）：明确写 `five-finger bare right hand, four fingers + one thumb`，负向词封死 `six fingers, extra finger, double cylinder, steel wristwatch, silver bracelet`。
   - 背影防转身：`strictly back view, back of short neat dark hair only, face NEVER visible`，负向词封死 `side profile, cheek visible, turning around`。
   - 动作防夸张/防变形：`sober steady walk`、`micro backward recoil arrest`、`collapse sideways-forward flat on pavement`；负向词封死 `drunk swaying, behind-back clasp, kneeling kowtow curl, crouching on steps, red string, blood droplet falling from chin`。

---

## 三、局部像素级修复与时序重映射（少重抽、快交付）

一旦主体表演、机位、眼神已对，**局部瑕疵一律优先在本地用 Python / NumPy / PIL / RIFE 手术解决**，不要轻易推翻整条镜头重抽：

1. **RIFE 时序曲线跳点（避开 AI 首段幻觉帧）**：
   - 若 HD 成片整体极佳但某连续 5–6 帧有微小伪影（如 `clip_02a_v13.mp4` `f3..f9` 出现细红丝），直接在 `build_v13.py` 的 piecewise `curve` 中做帧精确跳切：`(0.133, 2.0) -> (0.167, 10.0)`，配合声音顿挫点让剪辑平滑无缝。
2. **中段曝光/偏色稳定器（[build_v13.py `stabilize_hit_exposure`](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v13_fixes/build_v13.py#L1177-L1250)）**：
   - `Wan2.2 FLF2V` 中间帧常出现白衣发灰或画面整体泛暖。通过首尾帧建立线性亮度锚点曲线 + 自适应高光/暗部白平衡比，并用羽化外围遮罩锁稳背景。**坑点**：动态摆臂镜头的人物遮罩边界必须给足余量（`xx: 145..575, yy: 135..695, pad=36`），否则摆出手臂边缘会出现亮圈/暗圈（Halo）。
3. **局部画面手术（[v06_patches.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v06_master/v06_patches.py)）**：
   - `06b` 老式显像管关机：只对屏幕四边形内做荧光收缩亮线，绝不全屏叠加白光闪爆。
   - `10b` 手腕多出钢表：`i2i` 重绘容易弄花宣纸字体，直接只用相邻肤色遮罩平滑替换表带区域。
   - `11b` 深夜室内窗外过亮：只对右侧窗框蒙版压暗偏冷蓝，保留人物脸部暗黄台灯光影。
4. **RIFE v4.26 + macOS MPS 任意时刻插帧（禁止线性 `Image.blend`）**：
   - `16fps` 原片若直接 `Image.blend` 到 `24/30fps` 会明显重影拖泥。统一在 `RifeEngine`（Apple Silicon `mps` 加速）做光流 `render_positions` 输出 `30fps`，每个动作转折点精确对齐 `jolt_ms`、`crt_off_ms`、`gunflash_ms` 与拟音毫秒点。

---

## 四、配音、拟音、口型与音频母带规范

1. **VoxCPM2「先铸演员基准音、再克隆演单句情绪」**：
   - 见 [remote_voxcpm2_p2.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/ep01_p2/remote_voxcpm2_p2.py)：为每位核心角色固定 `seed`（如罗家明 `1991`、叶子农 `1992`、库格列夫 `1993`、苏玉平 `1994`、英语库格列夫 `1995`）生成参考音 `actor_<role>.wav`；合成各场台词时传入 `reference_wav_path` 锁声线，再用情绪提示词控制当场气息与语速（如「极度克制低沉」「惊恐破音」「近乎耳语」）。
   - 短促关键句（如`「我是罗。」`、`「还真他妈抬举我。」`）一次生成多个随机种子候选用人耳听选（`read_file` `.mp3` 验证停顿、气口和自然度）。
   - **禁止跨语种机械 `edge-tts` 错误参数**：已知 `ru-RU-Dmitry` 加 `+10%` 语速会返回空音频，且播音腔严重；一律以 `VoxCPM2` 主导对白、电视广播及多语种对白。
2. **ByteDance LatentSync-1.6 (`512×512`) 口型同步细节（[remote_latentsync_p2.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/ep01_p2/remote_latentsync_p2.py)）**：
   - 本地按 **`25fps`** 对原片做 RIFE 预变速，切出只包含本画面角色开口声音的纯净人声轨（`speaker_stem`），严禁把电话对面音或旁白混入 `stem`。
   - 暗夜低照度镜头必须在 `lipsync_pipeline.py` 加 `_preseed_det`（抽样扫通整段先缓存首个 `_last_det` 人脸框，避免第 0 帧过黑报错中断）。
   - 引导系数按演技幅度分级：日常清晰吐字 `guidance_scale = 1.6–1.8`，低沉呢喃/气声 `1.25–1.35`（防止大嘴开合）。
   - 回贴 `30fps` 时用 `build_perimeter_inner_mask(margin=36)` 羽化边缘消除 `512` 框边界痕迹；台词结束后的无声表演尾段做 `0.15s` 透明度平滑交接回原版高清 RIFE 帧。
3. **写实拟音与声场分寸（48kHz / 16-bit）**：
   - 电话听筒音做双阶滤波 + 轻度压缩 + `-45 dBFS` PSTN 线路底噪；同一空间镜头持续保留同一房间底噪（`room tone`），避免切换台词时出现“死寂断底噪”。
   - 动作拟音分层叠加且严控时长/频段：消音狙击弹只给高衰减低频胸腔闷击 + 布料轻裂，**绝无火药爆音**；重物倒地砍掉木鼓共振峰只留鞋底擦石 + 布料瘫落 + 短促低频顿响；不该响的声音（如巴黎街头轻步）果断删掉。
   - **全剧母带硬约束**：`apply_true_peak_limiter` / FFmpeg `alimiter=limit=0.84` 限制真峰值在 **`-1.5 dBFS` 以内**，实测成片整合响度约 **`-19.2 LUFS`**。
4. **单层内嵌字幕与目录卫生**：
   - 成片统一由 PIL 在封装最后一层渲染白字深灰描边字幕（`draw_subtitle_on_frame`）；`*_字幕归档.srt` 统一存放在各版本内部 `out/` 下，主成片目录保持 **0 个 `.srt` 伴随文件**，防止播放器双字幕叠字。

---

## 五、本地增量架构与 EasyColab 成本/稳定性铁律

1. **云端 `/dev/shm` 防爆铁律**：
   - G4 容器 `/dev/shm` 为 `88 GB`。`Qwen-Image-2.1`（~`30.8 GB`）与 `Wan2.2 14B`（~`35.4 GB` + 双模页缓存）**不可混跑**；即使 `unload_model` 也只清 GPU 显存不删 `/dev/shm`。正确流程：**阶段 1 生图 → 下载质检 → `stop_all` 清空 → 阶段 2 重启干净 G4 跑 Scout + 温热 HD**。
2. **高可用自动化三件套**：
   - 一切 HTTP 请求自带 **5 次指数退避重试**（应对 Cloudflare 502 / `SSLEOFError`）；本地产物存在即 `[skip]` 断点续传；长任务开 `70s` 后台 `keepalive` 线程；`try ... finally:` 必调 `stop_all` 并查 `auth_status` 确认 `burn_rate_hourly == 0.0`。
3. **本地秒级剪辑重编架构**：
   - 每镜按 `{spec, clip_sha256, wav_sha256, vf}` 计算 SHA-256 缓存并把调色颗粒烘焙进标准分辨率中间段 `seg_master_<id>.mov`，最终整集以 **`-c:v copy`** 流复制拼接（实测 `build_v13.py` 增量改动 4 镜全片重出片仅 **27.41 秒**）。
   - 多版本成片一律递增命名保留历史版本，方便前后盲测对比。
