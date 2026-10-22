from PIL import Image, ImageDraw


def icono(size):
    img = Image.new("RGB", (size, size), (30, 32, 38))
    d = ImageDraw.Draw(img)
    m = size * 0.12
    d.ellipse([m, m, size - m, size - m], fill=(88, 101, 242))
    r = size * 0.28
    d.ellipse([size / 2 - r, size / 2 - r, size / 2 + r, size / 2 + r], fill=(30, 32, 38))
    d.rectangle([size * 0.46, size * 0.06, size * 0.54, size * 0.24], fill=(88, 101, 242))
    return img


icono(512).save("icon.png")
icono(256).save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48),
                                   (64, 64), (128, 128), (256, 256)])
print("iconos creados")
