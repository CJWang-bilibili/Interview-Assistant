# Interview Assistant · 面试助手

实时捕获腾讯会议、钉钉等视频会议软件的系统音频，使用本地 **faster-whisper** 模型将语音转为文字，并通过置顶浮窗实时展示，支持一键复制到历史记录。

---

## 功能特性

| 功能 | 说明 |
|------|------|
| 🎙 实时语音识别 | 监听系统音频，段落结束后自动转文字 |
| 📋 复制到历史 | 点击按钮，当前内容带时间戳追加到历史区，同时写入剪贴板 |
| 🗑 删除 | 清空当前识别区 |
| 🪟 窗口置顶 | 浮窗默认置顶，随时可见 |
| 🌐 多语言 | 支持中文、英文及自动检测 |
| 💻 纯本地 | faster-whisper 完全离线运行，无需 API Key |

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

### Windows
在「音频设备」中选择 **「立体声混音 (Stereo Mix)」**。
若列表中没有该选项，请右键任务栏音量图标 → 声音设置 → 录制 → 右键空白处 → 显示已禁用设备，然后启用「立体声混音」。

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
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 本地语音识别（CTranslate2 加速） |
| [sounddevice](https://python-sounddevice.readthedocs.io/) | 音频流捕获 |
| numpy | 音频数据处理 |
| tkinter | GUI（Python 标准库） |

---

## 常见问题

**Q: 识别延迟多久？**
A: 在说话停顿 1~2 秒后触发识别，CPU 上 base 模型约 1~3 秒出结果。

**Q: 支持同声传译吗？**
A: 目前是分段识别，适合会后复盘或笔记整理。实时逐字流式输出需要更大模型。

**Q: 可以换更精准的模型吗？**
A: 在 `main.py` 中修改 `model_size="small"` 或 `"medium"` 即可，精度更高但速度更慢。
