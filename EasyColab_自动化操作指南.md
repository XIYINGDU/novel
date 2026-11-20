# EasyColab.app 无头自动化操作指南（macOS）

本文档记录如何在不依赖 GUI 鼠标点击的情况下，通过 macOS 本地安装的 **EasyColab.app** 内置桥接层、云端 REST API、ComfyUI 隧道接口及 `colab` CLI，全自动调度 Google Colab 云端 GPU（如 G4 / RTX PRO 6000 96GB、A100、H100、L4、T4）完成生图、生视频与自定义大模型推理，并在任务结束后**零残留关闭算力**。

---

## 一、核心路径与环境清单

| 组件 | 本地绝对路径 | 作用 |
| :--- | :--- | :--- |
| **桥接专用 Python** | `/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python` | 内置 `colab_cli`、`google-auth`、`requests` 等依赖 |
| **无头桥接脚本** | `/Applications/EasyColab.app/Contents/Resources/colab_bridge.py` | 查余额、申请/复用 GPU、部署服务端、内核保活、一键全停 |
| **云端服务端源码** | `/Applications/EasyColab.app/Contents/Resources/app.py` | `wake` 时自动上传至云端运行，暴露 `/minimax_api/*` 接口 |
| **Colab CLI 工具** | `/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/colab` | 底层会话管理、执行自定义 Python 脚本（`exec` / `run`）、上传下载文件 |
| **OAuth 凭证缓存** | `~/.config/colab-cli/token.json` | 复用 EasyColab 已登录的 Google 账号授权，无需重复扫码 |

---

## 二、四层自动化架构总览

1. **第 1 层 · 算力生命周期控制（`colab_bridge.py`）**：负责查 CU 余额、唤醒 GPU 容器、上传拉起 `app.py`、定时 `keepalive` 保活、以及任务结束时释放实例。
2. **第 2 层 · 图像/多模态生成控制（`/minimax_api/*`）**：通过 `wake` 返回的 `https://<id>.gradio.live` 地址，用标准 HTTP JSON 调用 `Qwen-Image-2.1` 等内置模型进行文生图（`t2i`）或参考图精修（`i2i_edit`）。
3. **第 3 层 · 动态视频生成控制（ComfyUI API）**：通过 `/minimax_api/comfyui/*` 一键拉起云端 ComfyUI 与 `trycloudflare.com` 公网隧道、自动下载预设权重包（如 `wan22_i2v_flf2v`），再直接调用 ComfyUI 原生 `/upload/image`、`/prompt`、`/history`、`/view` 接口批量渲染视频。
4. **第 4 层 · 任意开源模型扩展（`colab` CLI）**：对面板未内置的模型（如 `OpenBMB/VoxCPM2` 配音克隆），直接用 `colab exec --file` 在同一台云端 GPU 内核中跑自定义脚本，并用 `colab download` 拉回产物。

---

## 三、第 1 层：算力生命周期控制命令

建议在 Shell 中先定义别名变量：

```bash
BRIDGE_PY="/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python"
BRIDGE="/Applications/EasyColab.app/Contents/Resources/colab_bridge.py"
```

### 1. 查询登录状态、CU 余额与当前烧费速率
```bash
"$BRIDGE_PY" "$BRIDGE" auth_status
```
返回 JSON 示例：
```json
{
  "ok": true,
  "logged_in": true,
  "email": "xxx@gmail.com",
  "paid_balance": 2318.63,
  "burn_rate_hourly": 0.0,
  "active_assignments": 0,
  "sessions": []
}
```
> 多任务共用账号时，记录本任务的会话和 endpoint，退出后检查后端完整会话清单。最后一个任务退出后再核对账号的 `active_assignments` 和 `burn_rate_hourly` 是否归零。

### 2. 唤醒 GPU 并部署云端服务端（`wake`）
支持 `--gpu G4`（RTX PRO 6000 96GB，性价比与显存最优）、`H100`、`A100`、`L4`、`T4`：
```bash
"$BRIDGE_PY" "$BRIDGE" wake --gpu G4
```
标准输出末尾会打印公网入口：
```text
WAKE_URL:https://xxxxxxxxxxxxxxxxxx.gradio.live
```
用正则 `https://[a-zA-Z0-9]+\.gradio\.live` 提取即可作为后续 API 的 `BASE_URL`。

### 3. 运行期间定时保活（`keepalive`）
长时间通过 Cloudflare 隧道跑 ComfyUI 时，Colab 原生 Jupyter 通道若长时间无流量可能被判定闲置回收。需在后台线程每 **60–90 秒** 调用一次：
```bash
"$BRIDGE_PY" "$BRIDGE" keepalive
```

### 3b. 双开 G4（多会话版 bridge，2026-11-17 实测可用）
原版 `wake` 写死单会话并复用已有实例，无法双开。用仓库里的多会话副本（云端 app.py 仍用应用包原版）：
```bash
MULTI="/Users/duxiying/Documents/novel/天幕红尘/loop/tools/colab_bridge_multi.py"
"$BRIDGE_PY" "$MULTI" wake --gpu G4 --session A   # 各得一个 WAKE_URL
"$BRIDGE_PY" "$MULTI" wake --gpu G4 --session B
"$BRIDGE_PY" "$MULTI" keepalive                    # 会触达所有会话
"$BRIDGE_PY" "$MULTI" stop --session A
"$BRIDGE_PY" "$MULTI" stop --session B
"$BRIDGE_PY" "$MULTI" auth_status                  # 确认 A、B 的实例均已释放
```
扣费按台数叠加（G4 单台 10.05 CU/h）。两台挂同一个 EasyColab_Drive，避免同时写同名文件。详见 `天幕红尘/loop/ledger/experiments/2026-11-17_dual_g4.md`。

### 4. 需要释放账号全部实例时使用 `stop_all`
```bash
"$BRIDGE_PY" "$BRIDGE" stop_all
```
自动化任务使用 `with ColabPool(...)` 管理自己的实例。单台释放失败时，池会按会话重试，并在无法核实时报告对应实例。

---

## 四、第 2 层：通过 `/minimax_api/*` 自动化生图（以 `Qwen-Image-2.1` 为例）

设 `BASE="https://xxxxxxxxxxxxxxxxxx.gradio.live"`。

### 1. 下载并加载模型至显存
1. **选择模型**：`POST $BASE/minimax_api/select_model` → `{"model_id": "qwen_image_21"}`
2. **拉取权重至云端 `/dev/shm` 内存盘**：`POST $BASE/minimax_api/download_model` → `{"model_id": "qwen_image_21"}`
   - 轮询 `GET $BASE/minimax_api/status?model_id=qwen_image_21`，注意：**顶层无 `weights_downloaded` 字段**，应判断 `not s["is_downloading"] and all(f["exists"] for f in s.get("files", []))`。
3. **装载进 GPU 显存**：`POST $BASE/minimax_api/load_model` → `{"model_id": "qwen_image_21"}`
   - 轮询 `GET $BASE/minimax_api/status?model_id=qwen_image_21` 直至 `s["model_loaded"] == True and not s["is_loading_vram"]`。

### 2. 提交文生图（`t2i`）或参考图一致性编辑（`i2i_edit`）
请求：`POST $BASE/minimax_api/generate`
```json
{
  "model_id": "qwen_image_21",
  "task_mode": "t2i",
  "visual_prompt": "1991 Kodak Vision 35mm cinema film still ...",
  "negative_prompt": "cartoon, anime, watermark, subtitle, deformed hands",
  "width": 1280,
  "height": 720,
  "num_inference_steps": 30,
  "seed": 199301,
  "randomize_seed": false,
  "batch_count": 1
}
```
- 若锁脸或改局部道具，将 `"task_mode"` 设为 `"i2i_edit"`，并附带 `"first_frame_base64": "<PNG图片纯Base64字符串>"`。
- 提交后返回 `{"job_id": "..."}`。
- 每 2 秒轮询 `GET $BASE/minimax_api/job/{job_id}`，当 `status == "completed"` 时取 `filename`，从 `GET $BASE/minimax_api/media/{filename}` 下载高清原图。
- 全部生图完毕后调用 `POST $BASE/minimax_api/unload_model`（`{"model_id": "qwen_image_21"}`）释放显存。

---

## 五、第 3 层：通过云端 ComfyUI 批量生成动态视频（以 `Wan2.2 14B` 为例）

### 1. 启动 ComfyUI 与安装预设权重包
1. **启动服务与隧道**：`POST $BASE/minimax_api/comfyui/start` → `{}`
   - 轮询 `GET $BASE/minimax_api/comfyui/status`，待 `comfyui.is_running == True` 且 `comfyui.public_url` 非空，记下 `CF_URL = comfyui["public_url"]`（形如 `https://xxx-xxx.trycloudflare.com`）。
2. **安装预设视频包**：检查 `comfyui.preset_packs` 中目标包（如 `wan22_i2v_flf2v`）的 `ready` 状态；若为 `False`：
   - 调用 `POST $BASE/minimax_api/comfyui/install_pack` → `{"pack_id": "wan22_i2v_flf2v"}`
   - 每 5 秒轮询 `/minimax_api/comfyui/status`，直至该包 `ready == True` 且 `not comfyui["is_downloading_weight"]`。
   - 可选预设包 ID：`wan22_i2v_flf2v`（万相 Wan2.2 14B 4步极速）、`minimax_h3_i2v_flf2v`、`ltx23_flf2v`、`hunyuan15_i2v_1080p`。

### 2. 直接调用 ComfyUI 原生接口跑批处理
拿到 `CF_URL` 后，无需打开网页画布，直接按标准 ComfyUI 协议通信：
1. **上传首帧图**：`POST $CF_URL/upload/image`（`multipart/form-data`，字段 `image` + `overwrite=true`），返回云端文件名。
2. **提交节点图**：`POST $CF_URL/prompt`，Body 为 `{"prompt": <节点拓扑JSON>, "client_id": "<uuid>"}`，返回 `prompt_id`。
3. **轮询渲染结果**：`GET $CF_URL/history/{prompt_id}`，当 `outputs["108"]`（`VHS_VideoCombine` 节点）出现 `.mp4` 信息时，拼接参数请求 `GET $CF_URL/view?filename=...&subfolder=...&type=output` 将视频流写入本地文件。

---

## 六、第 4 层：用 `colab` CLI 跑面板外的自定义开源模型（如 `VoxCPM2`）

当需要运行 EasyColab 界面未收录的模型（如 `OpenBMB/VoxCPM2` 语音设计/克隆）时，直接复用同一个活跃会话的 Jupyter 内核：

```bash
COLAB="/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/colab"

# 1. 查看当前活跃会话名称
"$COLAB" sessions

# 2. 在云端 GPU 内核直接执行本地编写的 Python 脚本（注意：exec 接收 Python 代码文件而非 bash 命令）
"$COLAB" exec --file /path/to/run_voxcpm2.py --timeout 900

# 3. 将云端打包好的产物下载回本地（注意：本地目标父目录必须先 mkdir -p 创建好）
mkdir -p /path/to/local_audio_dir
"$COLAB" download /tmp/voxcpm2_out.tar.gz /path/to/local_audio_dir/voxcpm2_out.tar.gz
```
> **依赖保护技巧**：在云端脚本内 `pip install` 第三方包时，优先用 `pip install --no-deps <pkg>` 再补齐纯 Python 轻量依赖，避免覆盖重装 Colab 容器内已编译好的 Blackwell/CUDA 版 `torch`。

---

## 七、实战踩坑与最佳实践清单

1. **避免 `/dev/shm` 内存盘爆满导致容器被杀（关键）**：
   - G4 容器的 `/dev/shm` 为 `88 GB`。若先下载 `Qwen-Image-2.1`（约 `30.8 GB` 驻留 `/dev/shm`），仅调 `unload_model` 只清除了 **GPU 显存**，并未删除 `/dev/shm` 里的文件；此时再拉起 `Wan2.2 14B`（约 `35.4 GB` + 双 14B 模型加载页缓存）极易触碰容器内存上限导致会话断开。
   - **推荐做法**：生图与生视频**分阶段独立运行**——先把全部关键帧下载到本地并质检完毕，重开或清理后再用干净内存盘专门跑 ComfyUI 视频批处理。
2. **网络闪断与 Cloudflare 502 重试**：
   - `trycloudflare.com` 免费隧道偶发瞬时 `HTTP 502 Bad Gateway` 或 `SSLEOFError`。所有 HTTP 请求函数必须封装 **5 次指数退避重试**；同时本地脚本按已存在文件名自动 `[skip]` 断点续传。
3. **断线后的关机核验**：
   - 网络恢复后，对本任务仍在运行的会话补跑 `stop --session`，再用 `auth_status` 核验。
4. **项目中可直接复用的参考脚本**：
   - 生图批处理模板：[gen_keyframes_v03.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot/gen_keyframes_v03.py)
   - ComfyUI 视频批处理模板：[gen_videos_comfy_v03.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot/gen_videos_comfy_v03.py)
   - 支持保活和逐台关机核验的共享机器池：[colab_pool.py](天幕红尘/视频/common/colab_pool.py)
   - 自定义模型（VoxCPM2）远程合成模板：[run_voxcpm2_v03_en.py](file:///Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot/run_voxcpm2_v03_en.py)
