# 디스코드 창 캡처 루프: interval마다 찍고 Detector가 저장 여부 판정
import threading, time
from PIL import ImageGrab
import winapi
from detect import Detector, blank, diff, sig

class Grabber:
    """창 하나를 찍어 region으로 자른 이미지를 돌려줌"""
    def __init__(self, cfg, log, guard=False):
        self.cfg, self.log, self.guard = cfg, log, guard
        self.hwnd, self.mode = None, cfg["backend"]

    def window(self):
        """창 핸들. guard면 최소화된 창도 잡아 둠(MinimizeGuard가 되살림)"""
        if not (winapi.IS_WIN and self.hwnd and winapi.user32.IsWindow(self.hwnd)):
            self.hwnd = winapi.find_window(self.cfg["window_title"], iconic=self.guard)
        return self.hwnd

    def covered(self):
        """디스코드 방송 영역을 다른 창이 덮고 있는지"""
        h = self.hwnd
        return bool(winapi.IS_WIN and h) and not winapi.is_on_top(h, self.screen_box(winapi.window_rect(h)))

    def crop(self, img):
        r = self.cfg.get("region")
        if not r:
            return img
        w, h = img.size
        rs = self.cfg.get("region_size")
        if rs and not getattr(self, "size_warned", False) and (abs(w - rs[0]) > rs[0] * 0.05 or abs(h - rs[1]) > rs[1] * 0.05):
            self.size_warned = True  # 디스코드는 방송을 창 크기에 맞춰 늘이므로 비율 영역이 채팅·사이드바로 밀림
            self.log(f"주의: 디스코드 창 크기가 영역 지정 때({rs[0]}x{rs[1]})와 다름({w}x{h}). 캡처가 어긋나면 크기를 되돌리거나 영역을 다시 지정하세요")
        return img.crop((int(r[0] * w), int(r[1] * h), int(r[2] * w), int(r[3] * h)))

    def raw(self, mode):
        """mode로 창 전체 이미지. 못 찍으면 None"""
        hwnd = self.window()
        if not winapi.IS_WIN:
            return ImageGrab.grab()  # Mac 개발용: 전체 화면
        if not hwnd or winapi.iconic(hwnd):
            return None  # 최소화된 창은 Windows가 그리지 않아서 못 찍음
        if mode == "printwindow":
            return winapi.grab_printwindow(hwnd)
        box = winapi.window_rect(hwnd)
        if not winapi.is_on_top(hwnd, self.screen_box(box)):
            return None  # 다른 창이 덮고 있음
        return ImageGrab.grab(bbox=box, all_screens=True)

    def screen_box(self, box):
        r = self.cfg.get("region") or [0, 0, 1, 1]
        l, t, rr, b = box
        w, h = rr - l, b - t
        return (l + int(r[0] * w), t + int(r[1] * h), l + int(r[2] * w), t + int(r[3] * h))

    def grab_mode(self, mode):
        img = self.raw(mode)
        return None if img is None else self.crop(img)

    def grab(self):
        """방송 영역 이미지. auto면 printwindow가 검게 나올 때 screen으로 바꿈"""
        if self.mode == "auto":
            for m, msg in (("printwindow", "창이 가려져도 찍힘"), ("screen", "디스코드 창이 화면에 보여야 찍힘")):
                img = self.grab_mode(m)
                if img is not None and not blank(img):
                    self.mode = m
                    self.log(f"캡처 방식: {m} ({msg})")
                    return img
            return None
        return self.grab_mode(self.mode)

class Capturer(threading.Thread):
    def __init__(self, cfg, session, on_saved, log):
        super().__init__(daemon=True)
        self.cfg, self.session, self.on_saved, self.log = cfg, session, on_saved, log
        self.grabber = Grabber(cfg, log, guard=cfg["minimize_guard"])
        self.det = Detector(cfg)
        self.stop_ev = threading.Event()
        self.lock = threading.Lock()
        self.missing = self.was_covered = False
        self.freeze_hits = 0
        if cfg["minimize_guard"] and winapi.IS_WIN:
            threading.Thread(target=self._guard, daemon=True).start()

    def _guard(self):
        """디스코드를 최소화하면 0.3초 안에 되살려 맨 뒤로 보냄 → 최소화한 것처럼 안 보이지만 계속 캡처됨"""
        told = False
        while not self.stop_ev.wait(0.3):
            h = self.grabber.hwnd
            if winapi.iconic(h):
                winapi.send_to_back(h)
                if not told:
                    self.log("디스코드 최소화 → 맨 뒤로 보냄(녹화 중에는 계속 이렇게 함)")
                    told = True

    def _check_freeze(self, img):
        """덮였다가 다시 보일 때 화면이 확 바뀌면, 덮인 동안 디스코드가 그리기를 멈췄다는 신호"""
        if self.grabber.mode != "printwindow" or not winapi.IS_WIN:
            return
        cov = self.grabber.covered()
        if self.was_covered and not cov and self.det.prev is not None and diff(sig(img), self.det.prev) >= self.cfg["major_diff"]:
            self.freeze_hits += 1
            if self.freeze_hits == 2:
                self.log("주의: 디스코드가 가려진 동안 화면이 멈추는 것 같음 → '디스코드 가림방지' 버튼으로 다시 실행하세요")
        self.was_covered = cov

    def run(self):
        while not self.stop_ev.wait(self.cfg["interval_sec"]):
            try:
                with self.lock:
                    img = self.grabber.grab()
                    if img is None:
                        if not self.missing:
                            self.log(f"'{self.cfg['window_title']}' 창을 찍지 못함(없음/최소화/방송 꺼짐). 계속 시도 중")
                        self.missing = True
                        continue
                    if self.missing:
                        self.log("창 다시 찾음")
                    self.missing = False
                    self._check_freeze(img)
                    for im, kind in self.det.feed(img, time.monotonic()):
                        self.on_saved(self.session.add_shot(im, kind), False)
            except Exception as e:
                self.log(f"캡처 오류: {e}")
        for im, kind in self.det.flush():  # 정지 직전 필기 상태
            self.on_saved(self.session.add_shot(im, kind), False)

    def manual(self):
        """Shift+Z: 지금 화면을 ★로 저장"""
        with self.lock:
            img = self.grabber.grab()
            if img is None:
                self.log("수동 캡처 실패: 창을 찍지 못함")
                return None
            self.det.pending = None
            self.det.mark_saved(img, time.monotonic())
            p = self.session.add_shot(img, "manual", star=True)
        self.on_saved(p, True)
        return p

    def stop(self):
        self.stop_ev.set()
