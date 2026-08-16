#!/usr/bin/python3
"""Generate SMarTrPlay Android TV Assets."""
import os
import struct
import zlib

def create_png(width, height, draw_func):
    """Create a PNG file with custom drawing."""
    # Create RGBA pixel data
    pixels = []
    for y in range(height):
        row = bytearray()
        row.append(0)  # filter byte
        for x in range(width):
            r, g, b, a = draw_func(x, y, width, height)
            row.extend([r, g, b, a])
        pixels.append(bytes(row))
    
    raw = b''.join(pixels)
    compressed = zlib.compress(raw)
    
    def chunk(ctype, data):
        c = ctype + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        return struct.pack('>I', len(data)) + c + crc
    
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    png += chunk(b'IDAT', compressed)
    png += chunk(b'IEND', b'')
    return png

# SMarTr Brand Colors
BG_R, BG_G, BG_B = 0x0A, 0x0F, 0x1E
CYAN_R, CYAN_G, CYAN_B = 0x1B, 0xF1, 0xFB
VIOLET_R, VIOLET_G, VIOLET_B = 0x8D, 0x7C, 0xF6
WHITE_R, WHITE_G, WHITE_B = 0xF5, 0xF7, 0xFA

def draw_icon(x, y, w, h):
    cx, cy = w//2, h//2
    radius = min(w, h) // 2 - 10
    dist = ((x - cx)**2 + (y - cy)**2) ** 0.5
    if dist <= radius:
        return BG_R, BG_G, BG_B, 255
    elif dist <= radius + 3:
        return VIOLET_R, VIOLET_G, VIOLET_B, 255
    else:
        return 0, 0, 0, 0

def draw_splash(x, y, w, h):
    return BG_R, BG_G, BG_B, 255

def draw_banner(x, y, w, h):
    return BG_R, BG_G, BG_B, 255

os.makedirs('assets', exist_ok=True)

with open('assets/icon.png', 'wb') as f:
    f.write(create_png(512, 512, draw_icon))

with open('assets/splash.png', 'wb') as f:
    f.write(create_png(1920, 1080, draw_splash))

with open('assets/banner.png', 'wb') as f:
    f.write(create_png(320, 180, draw_banner))

print('Assets generated: icon.png, splash.png, banner.png')
