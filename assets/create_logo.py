#!/usr/bin/env python3
"""SMarTrPlay Logo Generator"""
from PIL import Image, ImageDraw, ImageFont
import os

size = 256
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Dark navy rounded background
draw.rounded_rectangle([8, 8, size-8, size-8], radius=48, fill=(10, 15, 30, 255))

# Play triangle (cyan)
cx, cy = size // 2, size // 2 - 10
ps = 80
play = [(cx - ps//3, cy - ps//2), (cx - ps//3, cy + ps//2), (cx + ps//2, cy)]
draw.polygon(play, fill=(27, 241, 251, 255))

# Inner play (violet glow)
play2 = [(cx - ps//3 + 5, cy - ps//2 + 8), (cx - ps//3 + 5, cy + ps//2 - 8), (cx + ps//2 - 8, cy)]
draw.polygon(play2, fill=(141, 124, 246, 180))

# SMarTr text
try:
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
except:
    font = ImageFont.load_default()
draw.text((size // 2, size - 38), 'SMarTr', fill=(245, 247, 250, 255), font=font, anchor='mm')

# Cyan border
draw.rounded_rectangle([8, 8, size-8, size-8], radius=48, outline=(27, 241, 251, 80), width=2)

# Save all sizes
outdir = os.path.dirname(os.path.abspath(__file__)) + '/icons'
os.makedirs(outdir, exist_ok=True)

for sz, name in [(256, 'smartrplay-logo.png'), (128, 'smartrplay-logo-128.png'), (64, 'smartrplay-logo-64.png'), (48, 'smartrplay-logo-48.png')]:
    if sz == 256:
        img.save(os.path.join(outdir, name), 'PNG')
    else:
        img.resize((sz, sz), Image.LANCZOS).save(os.path.join(outdir, name), 'PNG')
    fpath = os.path.join(outdir, name)
    print(name + ': ' + str(os.path.getsize(fpath)) + ' bytes')

print('Logo created successfully')
