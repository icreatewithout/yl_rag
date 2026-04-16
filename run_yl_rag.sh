#!/bin/bash

echo "======================================================"
echo "          YL Memory Palace RAG (uv 启动器)"
echo "======================================================"

# 1. 设置环境变量
export HF_ENDPOINT="https://hf-mirror.com"
export HF_HUB_OFFLINE="1"

# 2. 运行项目
echo "[1/1] 正在通过 uv 启动项目..."
echo "------------------------------------------------------"

# 使用 uv run 执行
# uv 会自动处理并加载当前目录下的 .python-version 或 pyproject.toml 对应的环境
uv run -m yl_rag

# 检查退出码
if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] 程序运行失败。"
    exit 1
fi
