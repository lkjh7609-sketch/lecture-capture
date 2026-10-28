# 앱 아이콘: 파란 둥근 사각형 + 흰 녹화 점. 빌드 때 icon.ico로 저장, 앱은 draw()로 트레이·창 아이콘에 씀
from pathlib import Path
from PIL import Image, ImageDraw

def draw(size=256, rec=False):
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, 248, 248), radius=56, fill="#0a6ed1")
    d.ellipse((78, 78, 178, 178), fill="white")
    d.ellipse((108, 108, 148, 148), fill="#e5484d" if rec else "#0a6ed1")  # 녹화 중엔 빨간 점
    return img if size == 256 else img.resize((size, size), Image.LANCZOS)

def save_ico(path):
    draw().save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path

if __name__ == "__main__":
    save_ico(Path(__file__).with_name("icon.ico"))
    print("ok icon.ico")
