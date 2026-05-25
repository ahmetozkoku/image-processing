import numpy as np
from typing import Optional


class BarcodeReader:
    def __init__(self):
        try:
            from pyzbar.pyzbar import decode as _decode
            self._decode = _decode
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def scan(self, frame: np.ndarray) -> Optional[str]:
        if not self._available or frame is None:
            return None
        try:
            barcodes = self._decode(frame)
            for bc in barcodes:
                data = bc.data.decode('utf-8', errors='ignore').strip()
                if data:
                    return data
        except Exception:
            pass
        return None
