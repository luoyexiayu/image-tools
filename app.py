import os
import zipfile
import tempfile
import shutil
import base64
from flask import Flask, render_template, request, send_file, after_this_request, jsonify
from werkzeug.utils import secure_filename
from gen_bottle_mask_4 import process_bottle_svg, process_raster_image, convert_bitmap_to_svg, remove_background_ai

app = Flask(__name__)
ALLOWED_EXTENSIONS = {'svg', 'png', 'jpg', 'jpeg', 'webp', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/preview', methods=['POST'])
def preview_image():
    try:
        mode = request.form.get('mode', 'shrink')
        file = request.files.get('file')
        if not file: return jsonify({'error': 'No file'}), 400

        try: indent = int(request.form.get('indent', 8))
        except: indent = 8
        try: smoothness = int(request.form.get('smoothness', 4))
        except: smoothness = 4
        try: radius = float(request.form.get('radius', 0))
        except: radius = 0
        color = request.form.get('color', '#FFFFFF')
        try: threshold = int(request.form.get('threshold', 10))
        except: threshold = 10
        try: shift = int(request.form.get('shift', 0))
        except: shift = 0
        try: s_width = int(request.form.get('stroke_width', 0))
        except: s_width = 0
        s_color = request.form.get('stroke_color', '#FFFFFF')
        s_pos = request.form.get('stroke_pos', 'outer')

        temp_dir = tempfile.mkdtemp()
        filename = secure_filename(file.filename)
        input_path = os.path.join(temp_dir, filename)
        output_path = os.path.join(temp_dir, 'preview_' + filename)
        
        file.save(input_path)
        ext = filename.rsplit('.', 1)[1].lower()
        result_path = output_path
        
        if mode == 'shrink':
            if ext == 'svg':
                process_bottle_svg(input_path, output_path, shrink_px=indent)
            else:
                real_output = os.path.splitext(output_path)[0] + ".png"
                process_raster_image(input_path, real_output, shrink_px=indent)
                result_path = real_output
        elif mode == 'vectorize':
            if ext != 'svg':
                result = convert_bitmap_to_svg(input_path, output_path, fill_color=color, smoothness=smoothness, corner_radius=radius)
                if result: result_path = result
            else:
                shutil.copy(input_path, output_path)
        elif mode == 'matting':
            real_output = os.path.splitext(output_path)[0] + ".png"
            remove_background_ai(input_path, real_output, 
                                 alpha_threshold=threshold, edge_shift=shift,
                                 stroke_width=s_width, stroke_color=s_color, stroke_pos=s_pos)
            result_path = real_output

        with open(result_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        mime_type = "image/svg+xml" if result_path.endswith('.svg') else "image/png"
        shutil.rmtree(temp_dir)
        return jsonify({'image': f"data:{mime_type};base64,{encoded_string}"})

    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}), 500

@app.route('/process', methods=['POST'])
def process_files():
    mode = request.form.get('mode', 'shrink')
    try: indent = int(request.form.get('indent', 8))
    except: indent = 8
    try: smoothness = int(request.form.get('smoothness', 4))
    except: smoothness = 4
    try: radius = float(request.form.get('radius', 0))
    except: radius = 0
    try: threshold = int(request.form.get('threshold', 10))
    except: threshold = 10
    try: shift = int(request.form.get('shift', 0))
    except: shift = 0
    try: s_width = int(request.form.get('stroke_width', 0))
    except: s_width = 0
    s_color = request.form.get('stroke_color', '#FFFFFF')
    s_pos = request.form.get('stroke_pos', 'outer')
    
    raw_files = request.files.getlist('files')
    files = [f for f in raw_files if f.filename != '']
    if not files: return "没有选择任何文件", 400

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
                    if mode == 'shrink':
                        if ext == 'svg':
                            process_bottle_svg(input_path, output_path, shrink_px=indent)
                        else:
                            real_output = os.path.splitext(output_path)[0] + ".png"
                            process_raster_image(input_path, real_output, shrink_px=indent)
                        processed_count += 1
                    elif mode == 'vectorize':
                        if ext != 'svg':
                            result = convert_bitmap_to_svg(input_path, output_path, fill_color='black', smoothness=smoothness, corner_radius=radius)
                            if result: processed_count += 1
                        else:
                            shutil.copy(input_path, output_path)
                            processed_count += 1
                    elif mode == 'matting':
                        real_output = os.path.splitext(output_path)[0] + ".png"
                        remove_background_ai(input_path, real_output, 
                                             alpha_threshold=threshold, edge_shift=shift,
                                             stroke_width=s_width, stroke_color=s_color, stroke_pos=s_pos)
                        processed_count += 1

                except Exception as e:
                    print(f"File Error: {e}")

        if processed_count == 0: return "处理失败", 400

        zip_filename = f"{mode}_processed.zip"
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
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
