from PIL import Image, ImageDraw, ImageFilter
import numpy as np
from collections import Counter

src = r"c:\Users\Administrator\.trae-cn\attachments\6aabcd70416852a5d69caed3\d0c062c9-2d93-483b-b27f-ac3941fb9945_3a1e87cf-0344-4fd6-828c-2a95ad28d709_algocode_icon.jpg"
img = Image.open(src).convert("RGB")
W, H = img.size
arr = np.array(img)
print(f"Original: {W}x{H}")

# --- Detect cream background via mode (most common color in gap region) ---
gap = arr[int(H*0.55):int(H*0.62), int(W*0.3):int(W*0.7)]
gap_colors = Counter(tuple(c) for c in gap.reshape(-1, 3))
cream = np.array(gap_colors.most_common(1)[0][0])
print(f"Cream (mode): {cream}")

# --- Detect outer background color (corner area) ---
corner = arr[0:20, 0:20]
corner_colors = Counter(tuple(c) for c in corner.reshape(-1, 3))
outer_bg = np.array(corner_colors.most_common(1)[0][0])
print(f"Outer bg: {outer_bg}")

# --- Graph mask: navy blue is very dark (brightness < 130) ---
brightness = arr.mean(axis=2)
graph_mask = brightness < 130
print(f"Graph pixel count: {graph_mask.sum()}")

# Exclude lower 40% (text region)
graph_mask[int(H * 0.60):, :] = False
print(f"After text exclusion: {graph_mask.sum()}")

# Bounding box
rows = np.any(graph_mask, axis=1)
cols = np.any(graph_mask, axis=0)
rmin, rmax = np.where(rows)[0][[0, -1]]
cmin, cmax = np.where(cols)[0][[0, -1]]
print(f"BBox: rows {rmin}-{rmax} ({rmax-rmin}px), cols {cmin}-{cmax} ({cmax-cmin}px)")

# Padding
pad = 30
rmin = max(0, rmin - pad)
rmax = min(H, rmax + pad)
cmin = max(0, cmin - pad)
cmax = min(W, cmax + pad)

# Crop image and mask
img_crop = img.crop((cmin, rmin, cmax, rmax))
mask_crop = Image.fromarray((graph_mask[rmin:rmax, cmin:cmax] * 255).astype(np.uint8))

# Scale up to ~65% of canvas (the larger dimension determines scale)
target = int(W * 0.65)
scale = target / max(img_crop.size)
new_w = int(img_crop.size[0] * scale)
new_h = int(img_crop.size[1] * scale)
img_enlarged = img_crop.resize((new_w, new_h), Image.LANCZOS)
mask_enlarged = mask_crop.resize((new_w, new_h), Image.LANCZOS)

# Slight blur for anti-aliased edges
mask_enlarged = mask_enlarged.filter(ImageFilter.GaussianBlur(1.0))
print(f"Enlarged: {new_w}x{new_h}")

# --- New canvas ---
canvas = Image.new("RGB", (W, W), tuple(outer_bg))
draw = ImageDraw.Draw(canvas)
radius = W // 6
draw.rounded_rectangle([0, 0, W - 1, W - 1], radius=radius, fill=tuple(cream))

# Center paste using mask
x = (W - new_w) // 2
y = (W - new_h) // 2
canvas.paste(img_enlarged, (x, y), mask_enlarged)

out = r"c:\Users\Administrator\Desktop\algocode\algocode_icon_v4.jpg"
canvas.save(out, quality=95)
print(f"Saved: {out}")
