import re
import cv2
import numpy as np
from typing import Optional

# Bunlar ilaç adı değil, filtrele
_IGNORE = {
    'tablet', 'kapsul', 'kapsül', 'film', 'kapli', 'kaplı', 'mg', 'ml',
    'mcg', 'ug', 'g', 'gr', 'oral', 'solüsyon', 'susp', 'süspansiyon',
    'ampul', 'flakon', 'sirup', 'şurup', 'damla', 'krem', 'jel', 'merhem',
    'draje', 'efervesan', 'bid', 'tid', 'flaşkon', 'etken', 'madde',
    'içeren', 'plaster', 'patch', 'tb', 'cp', 'cap', 'tab', 'inj',
    'susp.', 'sol.', 'amp.', 'x', 'adet', 'blister', 'kutu',
}


class OCRReader:
    def __init__(self):
        self._reader = None

    def _lazy_load(self):
        if self._reader is None:
            import easyocr
            self._reader = easyocr.Reader(['tr', 'en'], gpu=False, verbose=False)

    def read_text(self, image: np.ndarray) -> Optional[str]:
        if image is None or image.size == 0:
            return None
        self._lazy_load()
        try:
            # OCR için minimum boyut
            h, w = image.shape[:2]
            if h < 80:
                scale = 80 / h
                image = cv2.resize(image, (int(w * scale), 80))

            results = self._reader.readtext(image, detail=1, paragraph=False)
            # Güven skoru > 0.3 olan tüm metinleri al
            tokens = [text for (_, text, conf) in results if conf > 0.30]
            return ' '.join(tokens).strip() or None
        except Exception:
            return None

    def extract_drug_name(self, raw_text: str) -> str:
        """
        OCR çıktısından ilaç marka adını çıkar.
        Örnek: 'KLAMOKS BID 1000 mg 14 Film Tablet' → 'KLAMOKS BID'
        """
        if not raw_text:
            return ''

        words = raw_text.split()
        name_parts = []

        for word in words[:8]:
            # Sadece harf olan kısmı al
            clean = re.sub(r'[^a-zA-ZğüşöçıİĞÜŞÖÇ]', '', word).lower()
            if not clean:
                continue
            # Sayı veya birim veya jenerik kelimeyse dur
            if clean in _IGNORE or re.fullmatch(r'\d+', clean):
                if name_parts:   # marka adını zaten bulduk, dur
                    break
                continue
            if len(clean) >= 2:
                name_parts.append(word)
            if len(name_parts) == 3:  # en fazla 3 kelime
                break

        return ' '.join(name_parts)
