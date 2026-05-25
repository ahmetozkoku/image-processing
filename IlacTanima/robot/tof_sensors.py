"""
Çift VL53L4CD ToF sensör yöneticisi.

Problem: İki VL53L4CD'nin varsayılan I2C adresi aynı (0x29).
Çözüm : XSHUT piniyle önce birini kapat, diğerinin adresini değiştir,
        sonra ikincisini aç. Artık iki farklı adres → çakışma yok.

Bağlantı:
  Her iki sensör → SDA: GPIO2 (pin 3), SCL: GPIO3 (pin 5)
  Sol sensör  XSHUT → GPIO17 (pin 11)
  Sağ sensör  XSHUT → GPIO27 (pin 13)
"""

import time
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ToFReading:
    left_mm:  Optional[float]   # Sol sensör mesafesi (mm)
    right_mm: Optional[float]   # Sağ sensör mesafesi (mm)

    @property
    def avg_mm(self) -> Optional[float]:
        """Ortalama mesafe."""
        vals = [v for v in (self.left_mm, self.right_mm) if v is not None]
        return sum(vals) / len(vals) if vals else None

    @property
    def alignment_error_mm(self) -> Optional[float]:
        """
        Sol - Sağ fark (mm).
        Pozitif → sol taraf daha uzak (sağa kaymış).
        Negatif → sağ taraf daha uzak (sola kaymış).
        """
        if self.left_mm is None or self.right_mm is None:
            return None
        return self.left_mm - self.right_mm

    @property
    def is_aligned(self) -> bool:
        from robot.config_robot import ALIGNMENT_THRESHOLD_MM
        err = self.alignment_error_mm
        return err is not None and abs(err) < ALIGNMENT_THRESHOLD_MM

    @property
    def both_valid(self) -> bool:
        return self.left_mm is not None and self.right_mm is not None


class DualToF:
    """
    İki VL53L4CD sensörü XSHUT trick ile aynı I2C hattında kullanır.
    """

    def __init__(self):
        from robot.config_robot import (
            TOF_LEFT_XSHUT_GPIO, TOF_RIGHT_XSHUT_GPIO,
            TOF_LEFT_ADDRESS, TOF_RIGHT_ADDRESS,
        )
        self._left_addr  = TOF_LEFT_ADDRESS
        self._right_addr = TOF_RIGHT_ADDRESS
        self._xshut_l_gpio = TOF_LEFT_XSHUT_GPIO
        self._xshut_r_gpio = TOF_RIGHT_XSHUT_GPIO

        self._tof_l = None
        self._tof_r = None
        self._xshut_l = None
        self._xshut_r = None

        self._init_sensors()

    def _init_sensors(self):
        try:
            import board
            import busio
            from digitalio import DigitalInOut, Direction
            import adafruit_vl53l4cd

            i2c = busio.I2C(board.SCL, board.SDA)

            # GPIO pinlerini al
            xshut_l_pin = getattr(board, f"D{self._xshut_l_gpio}")
            xshut_r_pin = getattr(board, f"D{self._xshut_r_gpio}")

            self._xshut_l = DigitalInOut(xshut_l_pin)
            self._xshut_r = DigitalInOut(xshut_r_pin)
            self._xshut_l.direction = Direction.OUTPUT
            self._xshut_r.direction = Direction.OUTPUT

            # 1. Her ikisini kapat (LOW = kapalı)
            self._xshut_l.value = False
            self._xshut_r.value = False
            time.sleep(0.05)

            # 2. Sol sensörü aç → adresini değiştir
            self._xshut_l.value = True
            time.sleep(0.05)
            tof_l = adafruit_vl53l4cd.VL53L4CD(i2c)      # varsayılan 0x29
            tof_l.set_address(self._left_addr)             # → 0x30
            tof_l.start_ranging()
            self._tof_l = tof_l
            log.info("Sol ToF hazır @ 0x%02X", self._left_addr)

            # 3. Sağ sensörü aç (varsayılan 0x29, çakışma yok çünkü sol artık 0x30)
            self._xshut_r.value = True
            time.sleep(0.05)
            tof_r = adafruit_vl53l4cd.VL53L4CD(i2c)      # varsayılan 0x29
            tof_r.set_address(self._right_addr)            # → 0x31
            tof_r.start_ranging()
            self._tof_r = tof_r
            log.info("Sağ ToF hazır @ 0x%02X", self._right_addr)

        except Exception as exc:
            log.error("ToF başlatma hatası: %s", exc)
            log.warning("ToF sensörler simülasyon modunda çalışacak.")

    def read(self) -> ToFReading:
        """Her iki sensörden anlık mesafe okur (mm)."""
        left_mm  = self._read_one(self._tof_l, "sol")
        right_mm = self._read_one(self._tof_r, "sağ")
        return ToFReading(left_mm=left_mm, right_mm=right_mm)

    def _read_one(self, sensor, label: str) -> Optional[float]:
        if sensor is None:
            return None
        try:
            if sensor.data_ready:
                dist = sensor.distance   # mm
                sensor.clear_interrupt()
                return float(dist) if dist else None
        except Exception as exc:
            log.warning("ToF %s okuma hatası: %s", label, exc)
        return None

    def close(self):
        try:
            if self._tof_l: self._tof_l.stop_ranging()
            if self._tof_r: self._tof_r.stop_ranging()
        except Exception:
            pass
