import os
import cv2
import numpy as np
from svgpathtools import svg2paths2, wsvg, parse_path
from shapely.geometry import Polygon, MultiPolygon
from PIL import Image, ImageFilter, ImageOps, ImageChops
from rembg import remove, new_session

# --- 关键修改：使用 u2netp (轻量版) ---
# 这样可以将内存占用控制在 200MB 以内，适配 Render 免费版
rembg_session = new_session("u2netp")

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

def process_raster_image(input_path, output_path, shrink_px=8):
    try:
        img = Image.open(input_path).convert("RGBA")
        filter_size = (shrink_px * 2) + 1
        r, g, b, a = img.split()
        shrunk_a = a.filter(ImageFilter.MinFilter(filter_size))
        img = Image.merge("RGBA", (r, g, b, shrunk_a))
        final_output = output_path
        if not final_output.lower().endswith('.png'):
             final_output = os.path.splitext(output_path)[0] + '.png'
        img.save(final_output, format="PNG")
        return final_output
    except Exception as e:
        return output_path

def get_rounded_path_d(points, radius):
    n = len(points)
    if n < 3: return ""
    dists = []
    for i in range(n):
        p1 = points[i]
        p2 = points[(i+1)%n]
        d = np.linalg.norm(p1 - p2)
        dists.append(d)
    radii = []
    for i in range(n):
        prev_dist = dists[i-1]
        next_dist = dists[i]
        max_r = min(prev_dist, next_dist) / 2.0
        radii.append(min(radius, max_r))
    path_cmds = []
    def get_pt(idx, direction, r):
        p_center = points[idx]
        target_idx = (idx + direction) % n
        p_target = points[target_idx]
        vec = p_target - p_center
        length = np.linalg.norm(vec)
        if length == 0: return p_center
        return p_center + (vec / length) * r
    start_pt = get_pt(0, 1, radii[0])
    path_cmds.append(f"M {start_pt[0]:.2f},{start_pt[1]:.2f}")
    for i in range(n):
        next_i = (i + 1) % n
        line_target = get_pt(next_i, -1, radii[next_i])
        path_cmds.append(f"L {line_target[0]:.2f},{line_target[1]:.2f}")
        ctrl_pt = points[next_i]
        curve_end = get_pt(next_i, 1, radii[next_i])
        path_cmds.append(f"Q {ctrl_pt[0]:.2f},{ctrl_pt[1]:.2f} {curve_end[0]:.2f},{curve_end[1]:.2f}")
    path_cmds.append("Z")
    return " ".join(path_cmds)

def convert_bitmap_to_svg(input_path, output_path, fill_color='black', smoothness=4, corner_radius=0):
    try:
        img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
        if img is None: return False
        binary = None
        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha_channel = img[:, :, 3]
            _, binary = cv2.threshold(alpha_channel, 10, 255, cv2.THRESH_BINARY)
        else:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        svg_paths = []
        svg_attrs = []
        height, width = binary.shape
        epsilon_factor = float(smoothness) * 0.0005
        for cnt in contours:
            if cv2.contourArea(cnt) < 50: continue 
            epsilon = epsilon_factor * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            points = approx.reshape(-1, 2).astype(float)
            if len(points) < 3: continue
            if corner_radius > 0:
                path_d = get_rounded_path_d(points, float(corner_radius))
            else:
                path_d = f"M {points[0][0]},{points[0][1]}"
                for p in points[1:]: path_d += f" L {p[0]},{p[1]}"
                path_d += " Z"
            if path_d:
                svg_paths.append(parse_path(path_d))
                svg_attrs.append({'fill': fill_color, 'stroke': 'none'})
        final_output = os.path.splitext(output_path)[0] + '.svg'
        wsvg(svg_paths, attributes=svg_attrs, filename=final_output, 
             svg_attributes={'width': str(width), 'height': str(height), 'viewBox': f'0 0 {width} {height}'})
        return final_output
    except Exception as e:
        print(f"Error: {e}")
        return None

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def apply_stroke(img_pil, width, color_hex, position='outer'):
    if width <= 0: return img_pil
    padding = width + 5
    img = ImageOps.expand(img_pil, border=padding, fill=(0,0,0,0))
    r, g, b, a = img.split()
    alpha_np = np.array(a)
    kernel_size = 2 * width + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    if position == 'outer':
        dilated = cv2.dilate(alpha_np, kernel)
        stroke_mask = Image.fromarray(dilated)
        base_layer = Image.new("RGBA", img.size, hex_to_rgb(color_hex))
        base_layer.putalpha(stroke_mask)
        final = Image.alpha_composite(base_layer, img)
        return final
    elif position == 'inner':
        eroded = cv2.erode(alpha_np, kernel)
        mask_np = cv2.subtract(alpha_np, eroded) 
        stroke_layer = Image.new("RGBA", img.size, hex_to_rgb(color_hex))
        stroke_layer.putalpha(Image.fromarray(mask_np))
        final = Image.alpha_composite(img, stroke_layer)
        return final
    elif position == 'center':
        w_half = width // 2
        k_half = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*w_half+1, 2*w_half+1))
        dilated = cv2.dilate(alpha_np, k_half)
        eroded = cv2.erode(alpha_np, k_half)
        mask_np = cv2.subtract(dilated, eroded)
        stroke_layer = Image.new("RGBA", img.size, hex_to_rgb(color_hex))
        stroke_layer.putalpha(Image.fromarray(mask_np))
        final = Image.alpha_composite(img, stroke_layer)
        return final
    return img

def remove_background_ai(input_path, output_path, alpha_threshold=10, edge_shift=0, 
                         stroke_width=0, stroke_color='#FFFFFF', stroke_pos='outer'):
    try:
        img = Image.open(input_path).convert("RGBA")
        result = remove(img, session=rembg_session)
        if alpha_threshold > 0 or edge_shift != 0:
            arr = np.array(result)
            r, g, b, a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
            if alpha_threshold > 0:
                a = np.where(a > alpha_threshold, 255, 0).astype(np.uint8)
            if edge_shift != 0:
                ks = abs(edge_shift) * 2 + 1
                k = np.ones((ks, ks), np.uint8)
                if edge_shift > 0: a = cv2.erode(a, k, iterations=1)
                else: a = cv2.dilate(a, k, iterations=1)
            result = Image.fromarray(np.dstack((r, g, b, a)))
        if stroke_width > 0:
            result = apply_stroke(result, stroke_width, stroke_color, stroke_pos)
        final_output = output_path
        if not final_output.lower().endswith('.png'):
             final_output = os.path.splitext(output_path)[0] + '.png'
        result.save(final_output, format="PNG")
        return final_output
    except Exception as e:
        print(f"AI Error: {e}")
        Image.open(input_path).save(output_path)
        return output_path
