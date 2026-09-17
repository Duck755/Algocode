from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

# --- Config ---
SIZE = 1024  # square canvas
CREAM = (248, 240, 226)       # cream background
OUTER_BG = (255, 255, 255)    # outer white
NAVY = (20, 60, 130)          # navy blue for outline A and text
STROKE_WIDTH = 28             # thickness of the A outline
CORNER_RADIUS = SIZE // 6

# --- Create canvas ---
canvas = Image.new("RGB", (SIZE, SIZE), OUTER_BG)
draw = ImageDraw.Draw(canvas)

# Rounded rectangle cream background
draw.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=CORNER_RADIUS, fill=CREAM)

# --- Draw outline letter A ---
# A dimensions - positioned in upper portion
a_top = int(SIZE * 0.16)
a_bottom = int(SIZE * 0.60)
a_height = a_bottom - a_top
a_width = int(a_height * 0.82)
a_left = (SIZE - a_width) // 2
a_right = a_left + a_width

# A shape points (outer contour)
# Top apex
top_x = SIZE // 2
top_y = a_top

# Bottom left outer
bl_x = a_left
bl_y = a_bottom

# Bottom right outer
br_x = a_right
br_y = a_bottom

# Crossbar position (relative to height, ~45% from top)
crossbar_ratio = 0.48
crossbar_y = int(a_top + a_height * crossbar_ratio)

# Inner triangle (the hole in the A)
# The inner top is below the outer top
inner_top_offset = int(a_height * 0.35)
inner_top_y = a_top + inner_top_offset
inner_top_x = top_x

# Inner bottom - aligns with crossbar
inner_bottom_y = crossbar_y

# Inner width at bottom (of the triangular hole)
inner_bottom_half = int(a_width * 0.13)
inner_bl_x = top_x - inner_bottom_half
inner_br_x = top_x + inner_bottom_half

# Left leg inner slope: from inner_top down to inner bottom left
# Right leg inner slope: from inner_top down to inner bottom right

# --- Draw the outline A using two polygons (outer shape minus inner hole) ---
# We'll draw the A by stroking the path

# Method: draw the outer A shape filled, then draw inner "hole" in cream color
# But we want an outline (stroke only), not a filled A

# Better approach: use polygon with outline only
# Draw outer perimeter as a thick line, then inner perimeter as a thick line
# and fill the space between with navy

# Actually, let's draw it as a filled polygon (the stroke area)
# The stroke is a band of width STROKE_WIDTH around the A shape

# Let's compute outer and inner contours and fill the area between them.

# Outer A shape (thicker version):
half_stroke = STROKE_WIDTH // 2

# Outer contour (expanded by half_stroke)
def offset_point(x, y, dx, dy, offset):
    """Offset a point perpendicular to direction (dx, dy) by offset pixels."""
    import math
    length = math.sqrt(dx*dx + dy*dy)
    if length == 0:
        return x, y
    nx = -dy / length
    ny = dx / length
    return x + nx * offset, y + ny * offset

# Simpler approach: draw A by constructing the stroke polygon manually
# The A outline consists of:
# - Left outer edge (from bottom left up to top)
# - Right outer edge (from top down to bottom right)
# - Left bottom serif (bottom left horizontal)
# - Right bottom serif (bottom right horizontal)
# - Crossbar (horizontal in middle)
# - Inner left edge (from crossbar up to inner top)
# - Inner right edge (from inner top down to crossbar)

# Let's define the outer and inner boundaries and create a polygon

# Calculate the left and right leg slopes
# Left leg: from (bl_x, bl_y) to (top_x, top_y)
# Right leg: from (top_x, top_y) to (br_x, br_y)

# For the stroke effect, we create an outer polygon (expanded) and an inner polygon (contracted)
# then fill between them

# Let's use a simpler method: draw thick lines for all edges of the A

# Draw left leg (outer)
draw.line([(bl_x, bl_y), (top_x, top_y)], fill=NAVY, width=STROKE_WIDTH)
# Draw right leg (outer)
draw.line([(top_x, top_y), (br_x, br_y)], fill=NAVY, width=STROKE_WIDTH)

# Draw bottom left horizontal serif
bl_serif_right = bl_x + int(a_width * 0.18)
draw.line([(bl_x, bl_y), (bl_serif_right, bl_y)], fill=NAVY, width=STROKE_WIDTH)

# Draw bottom right horizontal serif
br_serif_left = br_x - int(a_width * 0.18)
draw.line([(br_serif_left, br_y), (br_x, br_y)], fill=NAVY, width=STROKE_WIDTH)

# Draw crossbar
# Find where left and right legs intersect crossbar_y
# Left leg equation
left_slope = (top_y - bl_y) / (top_x - bl_x)
left_cross_x = int(bl_x + (crossbar_y - bl_y) / left_slope)

# Right leg equation
right_slope = (br_y - top_y) / (br_x - top_x)
right_cross_x = int(top_x + (crossbar_y - top_y) / right_slope)

draw.line([(left_cross_x, crossbar_y), (right_cross_x, crossbar_y)], fill=NAVY, width=STROKE_WIDTH)

# Now draw inner edges to create the hollow effect
# Inner left: from crossbar up to inner top
# Inner right: from inner top down to crossbar

# Inner top point (apex of the triangular hole)
# It's along the center line, below the outer top
inner_top_y = a_top + int(a_height * 0.32)

# Inner bottom width (at crossbar level) - the base of the triangular hole
# This should leave the stroke width on both sides
inner_half_width_base = int((right_cross_x - left_cross_x) / 2 - STROKE_WIDTH * 0.6)

inner_bl_x = top_x - inner_half_width_base
inner_br_x = top_x + inner_half_width_base

# Draw inner left edge
draw.line([(inner_bl_x, crossbar_y), (top_x, inner_top_y)], fill=NAVY, width=STROKE_WIDTH)
# Draw inner right edge
draw.line([(top_x, inner_top_y), (inner_br_x, crossbar_y)], fill=NAVY, width=STROKE_WIDTH)

# --- Fill the corners/joins ---
# Add circles at joints for rounded joins
join_radius = STROKE_WIDTH // 2

def draw_round_join(x, y, r, color):
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

# Top apex
draw_round_join(top_x, top_y, join_radius, NAVY)
# Bottom left
draw_round_join(bl_x, bl_y, join_radius, NAVY)
# Bottom right
draw_round_join(br_x, br_y, join_radius, NAVY)
# Crossbar left
draw_round_join(left_cross_x, crossbar_y, join_radius, NAVY)
# Crossbar right
draw_round_join(right_cross_x, crossbar_y, join_radius, NAVY)
# Bottom left serif right end
draw_round_join(bl_serif_right, bl_y, join_radius, NAVY)
# Bottom right serif left end
draw_round_join(br_serif_left, br_y, join_radius, NAVY)
# Inner top
draw_round_join(top_x, inner_top_y, join_radius, NAVY)
# Inner bottom left
draw_round_join(inner_bl_x, crossbar_y, join_radius, NAVY)
# Inner bottom right
draw_round_join(inner_br_x, crossbar_y, join_radius, NAVY)

# --- Draw "Algocode" text ---
# Try to find a good font
font_paths = [
    r"C:\Windows\Fonts\calibrib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\georgiab.ttf",
]

font = None
font_size = int(SIZE * 0.14)
for fp in font_paths:
    if os.path.exists(fp):
        try:
            font = ImageFont.truetype(fp, font_size)
            print(f"Using font: {fp}")
            break
        except:
            continue

if font is None:
    font = ImageFont.load_default()
    print("Using default font")

text = "Algocode"
# Center text horizontally, position below the A
bbox = draw.textbbox((0, 0), text, font=font)
text_w = bbox[2] - bbox[0]
text_h = bbox[3] - bbox[1]
text_x = (SIZE - text_w) // 2 - bbox[0]
text_y = int(SIZE * 0.66)

draw.text((text_x, text_y), text, fill=NAVY, font=font)

# --- Save ---
out_path = r"c:\Users\Administrator\Desktop\algocode\algocode_icon_outline.jpg"
canvas.save(out_path, quality=95)
print(f"Saved: {out_path}")

# Also save a PNG version for transparency option
out_png = r"c:\Users\Administrator\Desktop\algocode\algocode_icon_outline.png"
canvas.save(out_png)
print(f"Saved: {out_png}")
