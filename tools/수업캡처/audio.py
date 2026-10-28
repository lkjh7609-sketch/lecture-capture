# 노트북 마이크로 현장 음성 녹음 → chunk_min분 wav 조각 → faster-whisper 받아쓰기
# 파일명 audio/HHMMSS.wav = 조각 시작 시각. 받아쓰기는 그 시각 + 구간 offset으로 실제 시각을 맞춤
import os, queue, threading, time, wave
from datetime import datetime

RATE = 16000

class Recorder(threading.Thread):
    def __init__(self, cfg, session, on_chunk, log):
        super().__init__(daemon=True)
        self.cfg, self.session, self.on_chunk, self.log = cfg, session, on_chunk, log
        self.stop_ev = threading.Event()
        self.current = None  # 쓰는 중인 파일 이름(받아쓰기 대상에서 제외)

    def run(self):
        try:
            import sounddevice as sd
        except ImportError:
            self.log("녹음 꺼짐: sounddevice 없음")
            return
        q = queue.Queue()
        try:
            stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", callback=lambda d, *_: q.put(bytes(d)))
            stream.start()
        except Exception as e:
            self.log(f"녹음 시작 실패(마이크 확인): {e}")
            return
        self.log("녹음 시작")
        chunk = self.cfg["chunk_min"] * 60
        try:
            while not self.stop_ev.is_set():
                start = time.time()
                path = self.session.dir / "audio" / (datetime.fromtimestamp(start).strftime("%H%M%S") + ".wav")
                self.current = path.name
                with wave.open(str(path), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
                    while not self.stop_ev.is_set() and time.time() - start < chunk:
                        try:
                            w.writeframes(q.get(timeout=0.5))
                        except queue.Empty:
                            pass
                self.current = None
                self.on_chunk(path)
        finally:
            stream.stop(); stream.close()
            self.log("녹음 정지")

    def stop(self):
        self.stop_ev.set()

class Transcriber(threading.Thread):
    """초안 받아쓰기 → 성공하면 wav 삭제 → on_draft(wav 이름)로 다듬기 단계에 넘김
    can_run()이 False인 동안은 쉰다(transcribe_live=False: 녹화 중엔 녹음만, 정지 후 받아쓰기)"""
    def __init__(self, cfg, session, log, on_draft, can_run=lambda: True, exclude=()):
        super().__init__(daemon=True)
        self.cfg, self.session, self.log, self.on_draft, self.can_run = cfg, session, log, on_draft, can_run
        self.q = queue.Queue()
        for p in session.pending_wav(exclude):  # 지난번에 못 끝낸 조각
            self.q.put(p)
        self.busy = False

    def put(self, path):
        self.q.put(path)

    def pending(self):
        return self.q.qsize() + self.busy

    def _hold(self):
        while not self.can_run():
            time.sleep(5)

    def run(self):
        self._hold()  # 정지 후 모드면 모델(메모리 약 1GB)도 그때 로드
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            self.log("받아쓰기 꺼짐: faster-whisper 없음")
            return
        self.log(f"받아쓰기 모델 로드: {self.cfg['whisper_model']} (처음 한 번은 다운로드)")
        try:
            model = WhisperModel(self.cfg["whisper_model"], device="cpu", compute_type="int8",
                                 cpu_threads=max(2, (os.cpu_count() or 4) // 2))  # 절반만 써서 수업 중 버벅임 방지
        except Exception as e:
            self.log(f"받아쓰기 모델 로드 실패: {e}")
            return
        while True:
            path = self.q.get()
            self._hold()
            self.busy = True
            try:
                t0 = datetime.strptime(f"{self.session.date} {path.stem[:6]}", "%Y-%m-%d %H%M%S").timestamp()
                segs, _ = model.transcribe(str(path), language="ko", beam_size=self.cfg["whisper_beam"],
                                           vad_filter=True, initial_prompt=self.cfg["whisper_prompt"])
                out = [(t0 + s.start, t0 + s.end, s.text.strip()) for s in segs if s.text.strip()]
                self.session.add_transcript(path, out)
                path.unlink()  # 스크립트가 생겼으니 음성은 지움
                self.on_draft(path.name)
            except Exception as e:
                self.log(f"받아쓰기 실패 {path.name}: {e}")
            finally:
                self.busy = False
