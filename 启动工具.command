#!/bin/bash
cd "$(dirname "$0")"

echo "=========================================="
echo "    正在执行 V10.0 部署预处理..."
echo "    (生成云端服务器所需的配置文件)"
echo "=========================================="
echo ""

# 1. 更新 requirements.txt (加入服务器专用库 gunicorn)
# 注意：移除了 opencv-python-headless 的版本限制，让服务器自动选择
echo "flask
svgpathtools
shapely
numpy
Pillow
opencv-python-headless
rembg
onnxruntime
gunicorn" > requirements.txt
echo "✅ 已生成: requirements.txt (依赖清单)"

# 2. 创建 Procfile (Render 平台的启动命令)
# 告诉服务器：请使用 gunicorn 启动 app.py 中的 app 应用
echo "web: gunicorn app:app" > Procfile
echo "✅ 已生成: Procfile (启动命令)"

# 3. 创建 .gitignore (告诉 Git 忽略哪些垃圾文件)
echo "venv/
__pycache__/
*.pyc
.DS_Store
*.zip
processed/
input/
temp/" > .gitignore
echo "✅ 已生成: .gitignore (忽略清单)"

# 4. 检查文件大小 (AI库很大，但我们不上传库，只上传代码)
echo ""
echo "🎉 部署准备完成！"
echo "------------------------------------------------"
echo "接下来，你需要做两件事："
echo "1. 把这个文件夹里的代码上传到 GitHub。"
echo "2. 在 Render.com 连接你的 GitHub 仓库。"
echo "------------------------------------------------"
echo "按任意键退出..."
read -n 1