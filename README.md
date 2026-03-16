# Interview Assistant · 面试助手

实时捕获腾讯会议、钉钉等视频会议软件的系统音频，使用本地 **FunASR Paraformer** 模型将语音转为文字，并通过置顶浮窗实时展示，支持一键复制到历史记录。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 🎙 实时语音识别 | 监听系统音频，段落结束后自动转文字 |
| 📋 复制到历史 | 点击按钮，当前内容带时间戳追加到历史区，同时写入剪贴板 |
| 🗑 删除 | 清空当前识别区 |
| 🪟 窗口置顶 | 浮窗默认置顶，随时可见 |
| 🌐 多语言 | 支持中文、英文及自动检测 |
| 💻 纯本地 | FunASR Paraformer 完全离线运行，无需 API Key |

---

## 界面预览

```
┌─────────────────────────────────────────────────────┐
│  🎙 Interview Assistant                  [置顶 ✓]   │
├─────────────────────────────────────────────────────┤
│  音频设备: [系统音频] default monitor  语言:[zh▼]    │
│  状态: 🎙 监听中…       音量 ████████░░             │
├─────────────────────────────────────────────────────┤
│  实时识别                                            │
│  ╔═══════════════════════════════════════════════╗  │
│  ║  你好，我是今天的面试官，请做一个自我介绍。   ║  │
│  ╚═══════════════════════════════════════════════╝  │
│      [  🗑 删除  ]              [  📋 复制到历史  ]  │
├─────────────────────────────────────────────────────┤
│  历史对话                              [清空历史]    │
│  ╔═══════════════════════════════════════════════╗  │
│  ║ [14:23:05] 请问你有哪些项目经验？             ║  │
│  ║ ─────────────────────────────────────────     ║  │
│  ║ [14:25:12] 好的，那我先介绍一下背景情况…      ║  │
│  ╚═══════════════════════════════════════════════╝  │
└─────────────────────────────────────────────────────┘
```

---

## 安装

### Linux / macOS

```bash
git clone https://github.com/CJWang-bilibili/Interview-Assistant.git
cd Interview-Assistant
bash setup.sh
```

### Windows

```bat
git clone https://github.com/CJWang-bilibili/Interview-Assistant.git
cd Interview-Assistant
setup_windows.bat
```

---

## 运行

```bash
python3 main.py       # Linux / macOS
python  main.py       # Windows
```

> **首次启动**会自动下载 Whisper `base` 模型（约 150 MB），之后离线运行。

---

## 配置会议软件音频捕获

### Linux（推荐）
在「音频设备」下拉框中选择带 **`[系统音频]`** 前缀的设备（PulseAudio/PipeWire monitor），即可捕获腾讯会议、钉钉等软件播放的声音。

### Windows（推荐：VB-CABLE）

**Step 1 — 安装 VB-CABLE 驱动**
下载并以管理员身份运行 `VBCABLE_Driver_Pack45.exe`：
https://vb-audio.com/Cable/

安装完成后系统会新增两个虚拟设备：
- `CABLE Input` — 虚拟扬声器（让会议软件往这里输出）
- `CABLE Output` — 虚拟麦克风（本工具从这里读取）

**Step 2 — 设置会议软件扬声器**
打开腾讯会议 / 钉钉 / Zoom 等，将「扬声器」改为 **CABLE Input**。

**Step 3 — 启动本工具**
运行 `python main.py`，「音频设备」下拉框会自动选中 **`[VB-CABLE] CABLE Output`**，直接点「开始监听」即可。

---

> ⚠️ **使用 CABLE Input 作为扬声器后没有声音？**
>
> 这是因为音频流进了虚拟管道，没有转发到真实扬声器。解决方法：
>
> 1. 右键任务栏音量图标 → **声音**（或打开控制面板 → 声音）
> 2. 切到 **录制** 选项卡
> 3. 找到 **CABLE Output** → 右键 → **属性**
> 4. 切到 **侦听** 标签页
> 5. 勾选 **侦听此设备**
> 6. 「通过此设备播放」选你的 **真实耳机 / 扬声器**
> 7. 点击 **确定**
>
> 设置完成后，音频会同时送到：CABLE Output（本工具识别）+ 你的真实扬声器（你能听到）。

### macOS
安装 [BlackHole](https://github.com/ExistentialAudio/BlackHole) 虚拟音频设备，并在会议软件中将输出路由到 BlackHole，再在本工具中选择 BlackHole 作为输入设备。

---

## 项目结构

```
Interview-Assistant/
├── main.py             # 入口，组装各模块
├── audio_capture.py    # 系统音频捕获（sounddevice）
├── transcriber.py      # 实时语音识别（faster-whisper）
├── gui.py              # 浮窗 UI（tkinter）
├── requirements.txt    # Python 依赖
├── setup.sh            # Linux/macOS 安装脚本
└── setup_windows.bat   # Windows 安装脚本
```

---

## 依赖

| 包 | 用途 |
|----|------|
| [FunASR](https://github.com/modelscope/FunASR) | 本地语音识别（阿里达摩院，中文最优） |
| [ModelScope](https://github.com/modelscope/modelscope) | 模型下载管理 |
| [PyTorch](https://pytorch.org/) | FunASR 推理后端 |
| [sounddevice](https://python-sounddevice.readthedocs.io/) | 音频流捕获 |
| numpy | 音频数据处理 |
| tkinter | GUI（Python 标准库） |

---

## 常见问题

**Q: 识别延迟多久？**
A: 说话停顿 1~2 秒后触发，CPU 上 Paraformer 约 0.5~2 秒出结果，比 Whisper 快。

**Q: 支持英文吗？**
A: 支持。在语言下拉框选 `en` 自动切换为 `paraformer-en`，选 `auto` 使用 SenseVoice 多语言模型。

**Q: 首次下载慢怎么办？**
A: 模型从 ModelScope（阿里云）下载，国内速度较快。下载后完全离线运行。

**Q: 相比 Whisper 提升多少？**
A: 中文字错率 Paraformer 约 3~5%，Whisper base 约 15~20%，提升显著。
