# 화면 변화 감지: 멈춘 화면만, 직전 저장본과 충분히 다를 때만 저장
# - major: 슬라이드/화면 전환 → 바로 저장
# - minor: 같은 화면에 펜 필기·코드 줄 추가 → min_gap_sec 간격으로 저장
#   간격 때문에 못 찍은 최신 상태는 pending으로 들고 있다가, 화면이 넘어가기 직전(major)이나 정지할 때 저장
#   → 필기가 끝난 마지막 모습은 항상 남는다
# 테스트: python detect.py <이미지들...>   (연속 프레임으로 보고 저장 판정을 출력)
from PIL import Image, ImageChops

SIG = (640, 360)  # 얇은 펜 선도 남도록 너무 작게 줄이지 않음
PIX = 24          # 이 이상 밝기 차이 나는 픽셀만 "바뀜"으로 셈(영상 압축 노이즈 무시)
NOISE = 0.0005    # 직전 프레임과 이보다 적게 다르면 "멈춤"

def sig(img):
    return img.convert("L").resize(SIG, Image.BILINEAR)

def diff(a, b):
    """바뀐 픽셀 비율 0~1"""
    if a is None or b is None:
        return 1.0
    h = ImageChops.difference(a, b).point(lambda v: 255 if v >= PIX else 0).histogram()
    return h[255] / (SIG[0] * SIG[1])

GRID = (32, 18)   # 20x20px 칸

def cells(a, b):
    """바뀐 칸 수. 2x2칸 안에 들어가는 작은 덩어리(마우스 커서 등)는 뺀다 → 펜 선·글자 줄만 남음"""
    if a is None or b is None:
        return GRID[0] * GRID[1]
    m = ImageChops.difference(a, b).point(lambda v: 255 if v >= PIX else 0).resize(GRID, Image.BOX)
    on = {(i % GRID[0], i // GRID[0]) for i, v in enumerate(m.tobytes()) if v >= 2}  # 칸 안 3px 이상
    n, seen = 0, set()
    for c in on:
        if c in seen:
            continue
        group, stack = [], [c]
        seen.add(c)
        while stack:
            x, y = stack.pop()
            group.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in on and q not in seen:
                        seen.add(q)
                        stack.append(q)
        xs, ys = [g[0] for g in group], [g[1] for g in group]
        if max(xs) - min(xs) >= 2 or max(ys) - min(ys) >= 2:
            n += len(group)
    return n

def blank(img):
    lo, hi = img.convert("L").getextrema()
    return hi - lo < 12  # 검은 화면/방송 끊김

class Detector:
    def __init__(self, cfg):
        self.cfg = cfg
        self.prev = self.saved = self.pending = None
        self.still_since = self.saved_at = 0.0

    def feed(self, img, now):
        """저장할 [(img, kind)] (비어 있으면 저장 안 함)"""
        if blank(img):
            return []
        s = sig(img)
        if diff(s, self.prev) > self.cfg.get("noise_diff", NOISE):
            self.still_since = now
        self.prev = s
        if now - self.still_since < self.cfg["stable_sec"]:
            return []  # 그리는 중·타이핑 중·스크롤 중
        d = diff(s, self.saved)
        if d >= self.cfg["major_diff"]:
            out = self.flush() + [(img, "major")]
        elif cells(s, self.saved) >= self.cfg["minor_cells"]:
            if now - self.saved_at < self.cfg["min_gap_sec"]:
                self.pending = img
                return []
            out = [(img, "minor")]
        else:
            return []
        self.pending = None
        self.mark_saved(img, now)
        return out

    def flush(self):
        """들고 있던 최신 필기 상태"""
        p, self.pending = self.pending, None
        return [(p, "minor")] if p is not None else []

    def mark_saved(self, img, now):
        self.saved = sig(img)
        self.saved_at = now


if __name__ == "__main__":
    import sys
    from config import DEFAULTS
    cfg = dict(DEFAULTS, stable_sec=0, min_gap_sec=0)
    d, last = Detector(cfg), None
    for i, p in enumerate(sys.argv[1:]):
        img = Image.open(p)
        s = sig(img)
        print(f"{p}: 직전과 {diff(s, last):.4f}/{cells(s, last)}칸 → {[k for _, k in d.feed(img, float(i))] or '건너뜀'}")
        last = s
