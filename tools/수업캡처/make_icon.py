# 앱 아이콘(icon.ico) 생성: 파란 원 + 흰 녹화 점. 빌드 때 한 번 실행
from pathlib import Path
from PIL import Image, ImageDraw

img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, 248, 248), radius=56, fill="#0a6ed1")
d.ellipse((78, 78, 178, 178), fill="white")
d.ellipse((108, 108, 148, 148), fill="#0a6ed1")
img.save(Path(__file__).with_name("icon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ok icon.ico")
