"""
Arduino ile USB seri haberleşme.

Arduino'ya gönderilen komutlar:
  "1 90"    → Servo 1'i 90 dereceye götür
  "2 120"   → Servo 2'yi 120 dereceye götür
  "home"    → Tüm servolar home pozisyona
  "5 180"   → Gripper kapat
  "5 0"     → Gripper aç
  "show"    → Arduino mevcut açıları gönderir
"""

import glob
import logging
import time
from typing import Optional

log = logging.getLogger(__name__)


class ArduinoBridge:

    def __init__(self, port: Optional[str] = None, baudrate: int = 9600):
        import serial
        if port is None:
            port = self._find_port()
        log.info("Arduino'ya bağlanılıyor: %s @ %d baud", port, baudrate)
        self._ser = serial.Serial(port, baudrate, timeout=1.0)
        time.sleep(2.0)   # Arduino reset için bekle
        log.info("Arduino hazır.")

    # ── Bağlantı ──────────────────────────────────────────────────────────────

    @staticmethod
    def _find_port() -> str:
        ports = glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")
        if not ports:
            raise RuntimeError(
                "Arduino bulunamadı!\n"
                "  • USB kablosu takılı mı?\n"
                "  • 'ls /dev/ttyACM*' veya 'ls /dev/ttyUSB*' çalıştır."
            )
        log.info("Arduino portu: %s", ports[0])
        return ports[0]

    # ── Temel komut gönderici ─────────────────────────────────────────────────

    def send(self, command: str) -> str:
        """Ham komut gönder, Arduino'nun cevabını döndür."""
        cmd = command.strip() + "\n"
        self._ser.write(cmd.encode("utf-8"))
        self._ser.flush()
        time.sleep(0.05)
        response = ""
        while self._ser.in_waiting:
            try:
                response += self._ser.readline().decode("utf-8", errors="ignore")
            except Exception:
                break
        if response:
            log.debug("Arduino ← '%s' → '%s'", command.strip(), response.strip())
        return response.strip()

    # ── Yüksek seviyeli komutlar ──────────────────────────────────────────────

    def move_servo(self, servo_id: int, angle: int) -> str:
        """Belirli bir servo'yu verilen açıya götür."""
        angle = max(0, min(180, int(angle)))
        return self.send(f"{servo_id} {angle}")

    def home(self) -> str:
        """Tüm servo'ları başlangıç pozisyonuna götür."""
        log.info("Arduino → home")
        return self.send("home")

    def close_gripper(self) -> str:
        from robot.config_robot import SERVO_GRIPPER, GRIPPER_CLOSED
        log.info("Gripper kapatılıyor.")
        return self.move_servo(SERVO_GRIPPER, GRIPPER_CLOSED)

    def open_gripper(self) -> str:
        from robot.config_robot import SERVO_GRIPPER, GRIPPER_OPEN
        log.info("Gripper açılıyor.")
        return self.move_servo(SERVO_GRIPPER, GRIPPER_OPEN)

    def show_angles(self) -> str:
        """Arduino'daki mevcut açıları göster."""
        return self.send("show")

    def close(self):
        """Seri portu kapat."""
        try:
            self._ser.close()
        except Exception:
            pass
