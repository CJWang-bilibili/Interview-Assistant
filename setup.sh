#!/usr/bin/env bash
# setup.sh — Linux / macOS 一键安装
set -e

echo "=== Interview Assistant 安装脚本 ==="

# 检查 Python 版本
python3 -c "import sys; assert sys.version_info >= (3,9), 'Python >= 3.9 required'" \
  || { echo "❌ 需要 Python 3.9 或更高版本"; exit 1; }

# tkinter（Linux 需额外安装）
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "→ 安装 tkinter..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y python3-tk
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3-tkinter
  elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm tk
  else
    echo "⚠️  请手动安装 tkinter（python3-tk）"
  fi
fi

# PortAudio（sounddevice 依赖）
if ! python3 -c "import sounddevice" 2>/dev/null; then
  echo "→ 安装 PortAudio 系统库..."
  if command -v apt-get &>/dev/null; then
    sudo apt-get install -y libportaudio2 portaudio19-dev
  elif command -v dnf &>/dev/null; then
    sudo dnf install -y portaudio portaudio-devel
  elif command -v pacman &>/dev/null; then
    sudo pacman -S --noconfirm portaudio
  elif command -v brew &>/dev/null; then
    brew install portaudio
  fi
fi

# Python packages
echo "→ 安装 Python 依赖..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

echo ""
echo "✅ 安装完成！"
echo ""
echo "▶  运行方式："
echo "   python3 main.py"
echo ""
echo "💡 提示："
echo "   • Linux: 在「音频设备」中选择带 [系统音频] 标签的设备（PulseAudio monitor）"
echo "   • macOS: 安装 BlackHole 后选择对应设备"
echo "   • 首次启动会自动下载 FunASR Paraformer 模型（约 300 MB）"
echo "   • 语音识别引擎: FunASR Paraformer（中文精度大幅优于 Whisper）"
