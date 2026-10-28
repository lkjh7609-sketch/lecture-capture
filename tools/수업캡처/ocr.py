# Windows 내장 OCR(한국어)로 캡처 글자 추출. 검색·보조용(최종 정리는 Claude가 이미지를 직접 읽음)
# 한국어 OCR이 없으면: 설정 → 시간 및 언어 → 언어 → 한국어 → 언어 옵션 → 광학 문자 인식 설치
import asyncio, queue, threading

class OcrWorker(threading.Thread):
    def __init__(self, session, log):
        super().__init__(daemon=True)
        self.session, self.log = session, log
        self.q = queue.Queue()
        for f in session.pending_ocr():  # 지난번에 못 끝낸 것
            self.q.put(f)

    def put(self, file):
        self.q.put(file)

    def pending(self):
        return self.q.qsize()

    def run(self):
        try:
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.globalization import Language
            from winsdk.windows.storage import StorageFile, FileAccessMode
            from winsdk.windows.graphics.imaging import BitmapDecoder
        except ImportError:
            self.log("OCR 꺼짐: winsdk 없음(Windows 전용)")
            return
        engine = OcrEngine.try_create_from_language(Language("ko")) or OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            self.log("OCR 꺼짐: 한국어 OCR 언어팩 없음")
            return

        async def read(path):
            f = await StorageFile.get_file_from_path_async(str(path))
            stream = await f.open_async(FileAccessMode.READ)
            bmp = await (await BitmapDecoder.create_async(stream)).get_software_bitmap_async()
            res = await engine.recognize_async(bmp)
            return "\n".join(l.text for l in res.lines)

        loop = asyncio.new_event_loop()
        while True:
            file = self.q.get()
            try:
                text = loop.run_until_complete(read(self.session.dir / file))
            except Exception as e:
                self.log(f"OCR 실패 {file}: {e}")
                text = ""
            try:
                self.session.add_ocr(file, text)
            except Exception as e:
                self.log(f"OCR 기록 실패 {file}: {e}")
