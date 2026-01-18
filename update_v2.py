import os

print("🚀 正在开始升级到 V2 (支持 PNG/JPG)...")

# ---------------------------------------------------------
# 1. 更新 requirements.txt (增加 Pillow 库用于处理图片)
# ---------------------------------------------------------
req_content = """flask
svgpathtools
shapely
numpy
Pillow
"""
with open('requirements.txt', 'w', encoding='utf-8') as f:
    f.write(req_content)
print("✅ 依赖列表 requirements.txt 已更新 (增加了 Pillow)")

# ---------------------------------------------------------
# 2. 更新核心算法 gen_bottle_mask_4.py (增加位图腐蚀功能)
# ---------------------------------------------------------
core_content = """import argparse
import os
from svgpathtools import svg2paths2, wsvg, parse_path
from shapely.geometry import Polygon, MultiPolygon
from PIL import Image, ImageFilter
import numpy as np

# --- SVG 处理部分 (保持不变) ---
BLACK_COLORS = {'#000', '#000000', 'black', 'rgb(0,0,0)', 'rgba(0,0,0,1)'}

def is_black_path(attr):
    fill = attr.get('fill', 'none').strip().lower()
    stroke = attr.get('stroke', 'none').strip().lower()
    return fill in BLACK_COLORS or stroke in BLACK_COLORS

def path_to_polygon(path, num_samples=500):
    points = []
    for i in range(num_samples):
        t = i / num_samples
        point = path.point(t)
        points.append((point.real, point.imag))
    if points[0] != points[-1]: points.append(points[0])
    return Polygon(points)

def polygon_to_svg_path(polygon):
    if polygon.is_empty: return ""
    coords = list(polygon.exterior.coords)
    path_data = f"M {coords[0][0]:.2f},{coords[0][1]:.2f}"
    for x, y in coords[1:]: path_data += f" L {x:.2f},{y:.2f}"
    path_data += " Z"
    return path_data

def shrink_path_precisely(path, shrink_px=8):
    try:
        polygon = path_to_polygon(path, num_samples=1000)
        if not polygon.is_valid: polygon = polygon.buffer(0)
        
        # 执行向内偏移
        shrunk_polygon = polygon.buffer(-shrink_px, resolution=16, join_style=2, mitre_limit=2.0)
        
        if shrunk_polygon.is_empty: return path
        if isinstance(shrunk_polygon, MultiPolygon):
            shrunk_polygon = max(shrunk_polygon.geoms, key=lambda p: p.area)
        
        path_string = polygon_to_svg_path(shrunk_polygon)
        return parse_path(path_string)
    except:
        return path

def process_bottle_svg(input_path, output_path, shrink_px=8):
    paths, attributes, svg_attrs = svg2paths2(input_path)
    processed_paths = []
    processed_attrs = []
    for path, attr in zip(paths, attributes):
        if is_black_path(attr):
            shrunk_path = shrink_path_precisely(path, shrink_px)
            processed_paths.append(shrunk_path)
            processed_attrs.append({'fill': 'black', 'stroke': 'none', 'fill-opacity': '1'})
    wsvg(processed_paths, attributes=processed_attrs, filename=output_path, svg_attributes=svg_attrs)

# --- 新增：PNG/JPG 位图处理部分 ---
def process_raster_image(input_path, output_path, shrink_px=8):
    try:
        # 打开图片并转为 RGBA (带透明通道)
        img = Image.open(input_path).convert("RGBA")
        
        # 使用最大值滤波器模拟"腐蚀"效果
        # 原理：Alpha通道中，MinFilter 会让透明区域(0)向不透明区域(255)扩张，也就是让物体变小
        # 滤波器尺寸计算：2 * 像素 + 1
        filter_size = (shrink_px * 2) + 1
        
        # 仅对 Alpha 通道(透明度)进行腐蚀，保持颜色不变
        r, g, b, a = img.split()
        
        # MinFilter 在 Alpha 通道上的作用就是"收缩"白色区域（不透明区域）
        shrunk_a = a.filter(ImageFilter.MinFilter(filter_size))
        
        # 合并回原图
        img = Image.merge("RGBA", (r, g, b, shrunk_a))
        
        # 保存为 PNG (必须是PNG才能保留透明背景)
        # 如果原图是 jpg，这里也会被转存为 png
        final_output = output_path
        if not final_output.lower().endswith('.png'):
             final_output = os.path.splitext(output_path)[0] + '.png'
             
        img.save(final_output, format="PNG")
        print(f"✅ 图片处理成功: {input_path}")
        return final_output
        
    except Exception as e:
        print(f"❌ 图片处理失败: {e}")
        # 失败则直接复制原文件
        try:
            img = Image.open(input_path)
            img.save(output_path)
        except:
            pass
        return output_path
"""
with open('gen_bottle_mask_4.py', 'w', encoding='utf-8') as f:
    f.write(core_content)
print("✅ 核心算法 gen_bottle_mask_4.py 已更新 (增加了 PNG/JPG 支持)")

# ---------------------------------------------------------
# 3. 更新 app.py (增加文件类型判断逻辑)
# ---------------------------------------------------------
app_content = """import os
import zipfile
import tempfile
import shutil
from flask import Flask, render_template, request, send_file, after_this_request
from werkzeug.utils import secure_filename
# 导入两个处理函数
from gen_bottle_mask_4 import process_bottle_svg, process_raster_image

app = Flask(__name__)

# 允许的扩展名增加图片格式
ALLOWED_EXTENSIONS = {'svg', 'png', 'jpg', 'jpeg', 'webp'}

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
    output_dir = os.path.join(temp_dir, 'processed')
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
                
                ext = filename.rsplit('.', 1)[1].lower()
                
                try:
                    # 分流处理：如果是 SVG 走矢量算法，如果是图片走像素算法
                    if ext == 'svg':
                        process_bottle_svg(input_path, output_path, shrink_px=indent)
                        processed_count += 1
                    else:
                        # 图片处理后强制保存为 .png 以保留透明度
                        real_output = os.path.splitext(output_path)[0] + ".png"
                        process_raster_image(input_path, real_output, shrink_px=indent)
                        processed_count += 1
                        
                except Exception as e:
                    print(f"处理出错 {filename}: {e}")

        if processed_count == 0:
            return "没有成功处理任何文件，请检查文件格式。", 400

        # 打包
        zip_filename = f"batch_processed_{indent}px.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    zipf.write(os.path.join(root, file), file)

        @after_this_request
        def remove_temp_dir(response):
            try: shutil.rmtree(temp_dir)
            except: pass
            return response

        return send_file(zip_path, as_attachment=True)
    except Exception as e:
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        return f"服务器错误: {str(e)}", 500

if __name__ == '__main__':
    print("V2 服务启动！请访问 http://127.0.0.1:5001")
    app.run(debug=True, port=5001)
"""
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(app_content)
print("✅ 服务器代码 app.py 已更新")

# ---------------------------------------------------------
# 4. 更新前端 index.html (支持选择图片文件)
# ---------------------------------------------------------
if not os.path.exists('templates'):
    os.makedirs('templates')

html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>图像/SVG 批量内缩工具</title>
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
        .badge { background: #444; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; margin-left: 5px; vertical-align: middle; }
    </style>
</head>
<body>
<div class="container">
    <h1>图像/SVG 批量内缩工具 <span class="badge">V2.0</span></h1>
    <p>支持 SVG、PNG、JPG · 自动识别 · 批量处理</p>
    <form action="/process" method="post" enctype="multipart/form-data" id="form">
        <div class="group">
            <label>内缩程度 (px)</label>
            <input type="number" name="indent" value="8" min="1">
            <small style="color:#666">SVG 精确内缩 | 图片向内腐蚀</small>
        </div>
        <div class="group">
            <label>上传文件</label>
            <div class="upload-box">
                <span id="text">点击选择文件夹 / 拖拽文件到此</span>
                <input type="file" name="files" id="file" webkitdirectory multiple accept=".svg,.png,.jpg,.jpeg,.webp">
            </div>
            <div id="fileInfo"></div>
        </div>
        <button type="submit" id="btn">开始处理并下载</button>
        <div class="loading" id="load">⏳ 正在处理图像和路径，请稍候...</div>
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

print("✅ 前端界面 index.html 已更新")
print("🎉 所有文件升级完毕！请重新运行 '启动工具.command'")
