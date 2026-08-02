import os
from PIL import Image, ImageDraw, ImageFont

def get_font(size=120):
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\impact.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf"
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()

def create_cmp_logo():
    w, h = 500, 500
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # Colors
    blue_color = (10, 82, 190, 255) # #0a52be
    red_color = (225, 25, 35, 255)   # #e11923
    white_color = (255, 255, 255, 255)

    # 1. Outer Blue Circle Ring
    center_x, center_y, radius = 250, 250, 220
    border_width = 24

    draw.ellipse(
        [(center_x - radius, center_y - radius), (center_x + radius, center_y + radius)],
        outline=blue_color,
        width=border_width
    )

    # Inner White background circle
    inner_r = radius - border_width
    draw.ellipse(
        [(center_x - inner_r, center_y - inner_r), (center_x + inner_r, center_y + inner_r)],
        fill=white_color
    )

    # 2. Text CMP rendering with Red top and Blue bottom divided by a arc/swoosh
    font = get_font(140)
    text = "CMP"
    
    # Measure text box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    tx = (w - text_w) // 2 - bbox[0]
    ty = (h - text_h) // 2 - bbox[1] - 10

    # Render Red Text Layer
    red_layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    r_draw = ImageDraw.Draw(red_layer)
    r_draw.text((tx, ty), text, font=font, fill=red_color)

    # Render Blue Text Layer
    blue_layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    b_draw = ImageDraw.Draw(blue_layer)
    b_draw.text((tx, ty), text, font=font, fill=blue_color)

    # Create mask for bottom half with curved swoosh
    # Upper half mask (Red) and Lower half mask (Blue)
    swoosh_mask = Image.new("L", (w, h), 0)
    sm_draw = ImageDraw.Draw(swoosh_mask)

    # Polygon cut for lower half (Blue): starts around y=240 on left, curves down to y=260 in middle, up to y=240 on right
    # Fill bottom part in white (255)
    points = [
        (0, 240),
        (150, 270),
        (350, 260),
        (500, 235),
        (500, 500),
        (0, 500)
    ]
    sm_draw.polygon(points, fill=255)

    # Composite: Base is red text, overlay is blue text with swoosh_mask
    text_combined = Image.composite(blue_layer, red_layer, swoosh_mask)

    # Draw white curved swoosh line through text
    swoosh_line_layer = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    sl_draw = ImageDraw.Draw(swoosh_line_layer)
    
    # White swoosh arc line across center
    curve_points = [(50, 265), (160, 290), (340, 275), (450, 245)]
    sl_draw.line([(50, 260), (160, 285), (340, 270), (450, 240)], fill=white_color, width=12)

    # Composite final image
    final_img = Image.alpha_composite(img, text_combined)
    final_img = Image.alpha_composite(final_img, swoosh_line_layer)

    out_path = r"c:\Users\LEC\Desktop\Imvoi\cmp_logo.png"
    final_img.save(out_path, "PNG")
    print(f"Generated logo at {out_path}")

if __name__ == "__main__":
    create_cmp_logo()
