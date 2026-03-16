@echo off
REM setup_windows.bat — Windows 一键安装

echo === Interview Assistant 安装脚本 (Windows) ===

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+ https://www.python.org/
    pause
    exit /b 1
)

REM 安装 Python 依赖
echo 正在安装依赖包...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [完成] 安装成功！
echo.
echo 运行方式：
echo   python main.py
echo.
echo 提示：
echo   在「音频设备」中选择「立体声混音 (Stereo Mix)」以捕获会议音频。
echo   如未找到该设备，请在 Windows 声音设置中启用「立体声混音」。
echo   首次运行会自动下载 Whisper base 模型（约 150 MB）。
echo.
pause
