import os

# 1. 确保 templates 文件夹存在
if not os.path.exists('templates'):
    os.makedirs('templates')

# 2. 重新生成标准的 index.html (确保无格式问题)
html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SVG 批量内缩工具</title>
    <style>
        :root { --bg: #1a1a1a; --card: #2d2d2d; --text: #e0e0e0; --accent: #4CAF50; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .container { background: var(--card); padding: 2rem; border-radius: 12px; width: 100%; max-width: 480px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        h1 { margin: 0 0 10px 0; font-size: 1.5rem; }
        p { color: #888; font-size: 0.9rem; margin-bottom: 2rem; }
        .group { margin-bottom: 1.5rem; text-align: left; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="number"] { width: 100%; padding: 10px; background: #333; border: 1px solid #555; color: #fff; border-radius: 6px; box-sizing: border-box; }
        .upload-box { border: 2px dashed #555; padding: 2rem; border-radius: 8px; cursor: pointer; position: relative; transition: 0.2s; text-align: center; }
        .upload-box:hover { border-color: var(--accent); background: rgba(76,175,80,0.1); }
        .upload-box input { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
        button { background: var(--accent); color: white; border: none; padding: 12px; width: 100%; border-radius: 6px; font-size: 1rem; cursor: pointer; transition: 0.2s; }
        button:hover { background: #45a049; }
        button:disabled { background: #555; cursor: not-allowed; }
        #fileInfo { margin-top: 10px; color: var(--accent); font-size: 0.9rem; }
        .loading { display: none; margin-top: 15px; color: #aaa; }
    </style>
</head>
<body>
<div class="container">
    <h1>SVG 批量内缩工具</h1>
    <p>拖拽文件或文件夹 · 自动处理 · 打包下载</p>
    <form action="/process" method="post" enctype="multipart/form-data" id="form">
        <div class="group">
            <label>内缩像素 (px)</label>
            <input type="number" name="indent" value="8" min="1">
        </div>
        <div class="group">
            <label>上传文件</label>
            <div class="upload-box">
                <span id="text">点击选择文件夹 / 拖拽文件到此</span>
                <input type="file" name="files" id="file" webkitdirectory multiple accept=".svg">
            </div>
            <div id="fileInfo"></div>
        </div>
        <button type="submit" id="btn">开始处理并下载</button>
        <div class="loading" id="load">⏳ 正在计算路径偏移，请稍候...</div>
    </form>
</div>
<script>
    const f = document.getElementById('file'), t = document.getElementById('text'), i = document.getElementById('fileInfo'), b = document.getElementById('btn'), l = document.getElementById('load');
    f.onchange = () => { 
        const c = f.files.length; 
        if(c){ i.innerText = `已选中 ${c} 个文件`; t.innerText = `准备上传 ${c} 个文件`; } 
    };
    document.getElementById('form').onsubmit = (e) => {
        if(!f.files.length){ alert('请先选择文件！'); e.preventDefault(); return; }
        b.disabled = true; b.innerText = '处理中...'; l.style.display = 'block';
    };
</script>
</body>
</html>
"""

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("✅ index.html 已修复！")

# 3. 重新生成 app.py (确保端口为 5001)
app_content = """import os
import zipfile
import tempfile
import shutil
from flask import Flask, render_template, request, send_file, after_this_request
from werkzeug.utils import secure_filename
from gen_bottle_mask_4 import process_bottle_svg

app = Flask(__name__)
ALLOWED_EXTENSIONS = {'svg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_files():
    try:
        indent = int(request.form.get('indent', 8))
    except ValueError:
        indent = 8
        
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return "没有选择文件", 400

    temp_dir = tempfile.mkdtemp()
    input_dir = os.path.join(temp_dir, 'input')
    output_dir = os.path.join(temp_dir, 'processed_svgs')
    os.makedirs(input_dir)
    os.makedirs(output_dir)

    processed_count = 0
    try:
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                if not filename: continue
                input_path = os.path.join(input_dir, filename)
                output_path = os.path.join(output_dir, filename)
                file.save(input_path)
                try:
                    process_bottle_svg(input_path, output_path, shrink_px=indent)
                    processed_count += 1
                except Exception as e:
                    print(f"Error: {e}")

        if processed_count == 0:
            return "没有处理任何文件", 400

        zip_filename = f"batch_processed_{indent}px.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    zipf.write(os.path.join(root, file), file)

        @after_this_request
        def remove_temp_dir(response):
            try:
                shutil.rmtree(temp_dir)
            except: pass
            return response

        return send_file(zip_path, as_attachment=True)
    except Exception as e:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    print("Starting on port 5001...")
    app.run(debug=True, port=5001)
"""

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_content)

print("✅ app.py 已修复！")
print("🎉 所有文件修复完成，请重新运行启动工具。")
