"""将 icon.png 转换为 Tauri 需要的各种格式"""
from PIL import Image

ICONS_DIR = r"D:\Deepseek\Reasonix\agent-orchestrator\desktop-tauri\src-tauri\icons"
SRC_PNG = f"{ICONS_DIR}/icon.png"

img = Image.open(SRC_PNG).convert("RGBA")
print(f"Source: {img.size}")

# 基础 PNG 尺寸
sizes = {
    "32x32.png": 32, "64x64.png": 64, "128x128.png": 128,
    "128x128@2x.png": 256,
    "Square30x30Logo.png": 30, "Square44x44Logo.png": 44,
    "Square71x71Logo.png": 71, "Square89x89Logo.png": 89,
    "Square107x107Logo.png": 107, "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150, "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310, "StoreLogo.png": 50,
}
for name, size in sizes.items():
    img.resize((size, size), Image.LANCZOS).save(f"{ICONS_DIR}/{name}")
    print(f"OK {name}")

# ICO (多尺寸)
img.save(f"{ICONS_DIR}/icon.ico", format="ICO",
         sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print("OK icon.ico")

# iOS
ios = {
    "AppIcon-20x20@1x.png": 20, "AppIcon-20x20@2x.png": 40,
    "AppIcon-20x20@2x-1.png": 40, "AppIcon-20x20@3x.png": 60,
    "AppIcon-29x29@1x.png": 29, "AppIcon-29x29@2x.png": 58,
    "AppIcon-29x29@2x-1.png": 58, "AppIcon-29x29@3x.png": 87,
    "AppIcon-40x40@1x.png": 40, "AppIcon-40x40@2x.png": 80,
    "AppIcon-40x40@2x-1.png": 80, "AppIcon-40x40@3x.png": 120,
    "AppIcon-60x60@2x.png": 120, "AppIcon-60x60@3x.png": 180,
    "AppIcon-76x76@1x.png": 76, "AppIcon-76x76@2x.png": 152,
    "AppIcon-83.5x83.5@2x.png": 167, "AppIcon-512@2x.png": 1024,
}
for name, size in ios.items():
    img.resize((size, size), Image.LANCZOS).save(f"{ICONS_DIR}/ios/{name}")
print("OK iOS")

# Android
android = {
    "mipmap-mdpi": 48, "mipmap-hdpi": 72, "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144, "mipmap-xxxhdpi": 192,
}
for folder, size in android.items():
    d = f"{ICONS_DIR}/android/{folder}"
    for s in ["ic_launcher.png", "ic_launcher_foreground.png", "ic_launcher_round.png"]:
        img.resize((size, size), Image.LANCZOS).save(f"{d}/{s}")
print("OK Android")
print("ALL DONE")
