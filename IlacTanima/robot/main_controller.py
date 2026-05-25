"""
Test düzeneği kontrol döngüsü.

Amaç: Verilen ürün adını kamera + ToF ile bulup
      kolun tam önünde dur. Gripper yok.

Kullanım:
  python -m robot.main_controller            # ismi sorar
  python -m robot.main_controller Parol      # direkt argüman
  python -m robot.main_controller --test     # bileşen testi

Durumlar:
  SEARCHING   → Kamera her frame'de ürünü arıyor
  CENTERING   → Ürün bulundu, kamera merkezine hizalanıyor
  APPROACHING → ToF ile hedefe yaklaşılıyor
  ALIGNING    → Sol-sağ ToF eşitleniyor (paralel hizalama)
  STOPPED     → Kutunun önünde duruldu ✓
"""

import sys
import time
import logging
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from robot.config_robot import (
    LOOP_DELAY,
    CENTER_THRESHOLD, CENTERING_GAIN, BASE_ANGLE,
    TARGET_DISTANCE_MM, ALIGNMENT_THRESHOLD_MM,
    DISTANCE_GAIN, ALIGNMENT_GAIN, MAX_STEP_DEG,
    SERVO_BASE, SERVO_ELBOW,
)
from robot.tof_sensors    import DualToF
from robot.arduino_bridge import ArduinoBridge
from robot.vision_tracker import VisionTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("robot")


class RobotController:

    SEARCHING   = "SEARCHING"
    CENTERING   = "CENTERING"
    APPROACHING = "APPROACHING"
    ALIGNING    = "ALIGNING"
    STOPPED     = "STOPPED"
    DONE        = "DONE"

    def __init__(self, target: str):
        self.target = target.strip()
        self.state  = self.SEARCHING

        self._base_angle  = BASE_ANGLE
        self._elbow_angle = BASE_ANGLE

        print()
        print("══════════════════════════════════════════")
        print(f"  Hedef ürün : {self.target}")
        print("  Bileşenler başlatılıyor...")
        print("══════════════════════════════════════════")

        self.vision  = VisionTracker()
        self.tof     = DualToF()
        self.arduino = ArduinoBridge()

        self.arduino.home()
        print("  Sistem hazır. Ürün aranıyor...\n")

    # ── Ana döngü ─────────────────────────────────────────────────────────────

    def run(self):
        try:
            while self.state != self.DONE:
                prev = self.state
                self._step()
                if self.state != prev:
                    self._print_state_change(prev, self.state)
                time.sleep(LOOP_DELAY)
        except KeyboardInterrupt:
            print("\n  Kullanıcı durdurdu.")
        finally:
            self._shutdown()

    def _step(self):
        {
            self.SEARCHING:   self._search,
            self.CENTERING:   self._center,
            self.APPROACHING: self._approach,
            self.ALIGNING:    self._align,
            self.STOPPED:     self._finish,
        }[self.state]()

    # ── Durum fonksiyonları ───────────────────────────────────────────────────

    def _search(self):
        t = self.vision.find_target(self.target)
        if t.found:
            log.info(f"[BULUNDU] güven={t.confidence:.0%}  "
                     f"konum={'SAĞ' if t.error_x > 0.1 else 'SOL' if t.error_x < -0.1 else 'MERKEZ'}")
            self.state = self.CENTERING

    def _center(self):
        t = self.vision.find_target(self.target)
        if not t.found:
            log.warning("[MERKEZ] Ürün kayboldu, tekrar aranıyor...")
            self.state = self.SEARCHING
            return

        if abs(t.error_x) <= CENTER_THRESHOLD:
            log.info(f"[MERKEZ] Hizalandı (hata={t.error_x:+.2f})")
            self.state = self.APPROACHING
            return

        step = _clamp(int(t.error_x * CENTERING_GAIN), -MAX_STEP_DEG, MAX_STEP_DEG)
        self._base_angle = _clamp(self._base_angle + step, 0, 180)
        log.info(f"[MERKEZ] hata={t.error_x:+.2f}  adım={step:+d}°  base={self._base_angle}°")
        self.arduino.move_servo(SERVO_BASE, self._base_angle)

    def _approach(self):
        r = self.tof.read()
        avg = r.avg_mm
        if avg is None:
            log.warning("[YAKLAŞ] ToF okuması bekleniyor...")
            return

        log.info(f"[YAKLAŞ] sol={r.left_mm:.0f}mm  sağ={r.right_mm:.0f}mm  "
                 f"ort={avg:.0f}mm  hedef={TARGET_DISTANCE_MM}mm")

        if avg <= TARGET_DISTANCE_MM:
            log.info("[YAKLAŞ] Hedef mesafeye ulaşıldı!")
            self.state = self.ALIGNING
            return

        step = _clamp(int((avg - TARGET_DISTANCE_MM) * DISTANCE_GAIN), 1, MAX_STEP_DEG)
        self._elbow_angle = _clamp(self._elbow_angle + step, 0, 180)
        self.arduino.move_servo(SERVO_ELBOW, self._elbow_angle)

    def _align(self):
        r = self.tof.read()
        err = r.alignment_error_mm
        if err is None:
            return

        log.info(f"[HİZALA] sol={r.left_mm:.0f}mm  sağ={r.right_mm:.0f}mm  "
                 f"fark={err:+.0f}mm  tolerans=±{ALIGNMENT_THRESHOLD_MM}mm")

        if abs(err) <= ALIGNMENT_THRESHOLD_MM:
            self.state = self.STOPPED
            return

        step = _clamp(int(err * ALIGNMENT_GAIN), -MAX_STEP_DEG, MAX_STEP_DEG)
        self._base_angle = _clamp(self._base_angle + step, 0, 180)
        self.arduino.move_servo(SERVO_BASE, self._base_angle)

    def _finish(self):
        r = self.tof.read()
        print()
        print("╔══════════════════════════════════════════╗")
        print(f"║  ✓  KUTUNUN ÖNÜNDE DURULDU               ║")
        print(f"║     Ürün     : {self.target:<26} ║")
        print(f"║     Sol ToF  : {(r.left_mm or 0):<5.0f} mm                    ║")
        print(f"║     Sağ ToF  : {(r.right_mm or 0):<5.0f} mm                    ║")
        print(f"║     Base     : {self._base_angle:<5}°                     ║")
        print(f"║     Elbow    : {self._elbow_angle:<5}°                     ║")
        print("╚══════════════════════════════════════════╝")
        print()
        self.state = self.DONE

    # ── Yardımcılar ───────────────────────────────────────────────────────────

    def _print_state_change(self, prev: str, new: str):
        icons = {
            self.SEARCHING:   "🔍",
            self.CENTERING:   "↔️ ",
            self.APPROACHING: "→ ",
            self.ALIGNING:    "⇔ ",
            self.STOPPED:     "✓ ",
            self.DONE:        "■ ",
        }
        log.info(f"  {icons.get(new, '')} {prev} → {new}")

    def _shutdown(self):
        try: self.arduino.home(); self.arduino.close()
        except Exception: pass
        try: self.vision.stop()
        except Exception: pass
        try: self.tof.close()
        except Exception: pass


# ── Bileşen test modu ─────────────────────────────────────────────────────────

def _run_component_test():
    print("\n═══════════════════════════════════════")
    print("  BİLEŞEN TESTİ")
    print("═══════════════════════════════════════\n")

    # 1. Arduino
    print("[1/3] Arduino testi...")
    try:
        a = ArduinoBridge()
        a.home(); time.sleep(1)
        print("      home → OK")
        a.move_servo(SERVO_BASE, 60);  time.sleep(0.8)
        a.move_servo(SERVO_BASE, 90);  time.sleep(0.8)
        a.move_servo(SERVO_ELBOW, 60); time.sleep(0.8)
        a.move_servo(SERVO_ELBOW, 90); time.sleep(0.8)
        a.home(); a.close()
        print("      ✓ Arduino OK\n")
    except Exception as e:
        print(f"      ✗ Arduino HATA: {e}\n")

    # 2. ToF
    print("[2/3] ToF sensör testi (8 okuma)...")
    try:
        tof = DualToF()
        for i in range(8):
            r = tof.read()
            print(f"      [{i+1}] sol={r.left_mm}mm  sağ={r.right_mm}mm  "
                  f"fark={r.alignment_error_mm}mm")
            time.sleep(0.25)
        tof.close()
        print("      ✓ ToF OK\n")
    except Exception as e:
        print(f"      ✗ ToF HATA: {e}\n")

    # 3. Kamera
    hedef = input("[3/3] Kamera testi — ürün adı gir (boş = Parol): ").strip() or "Parol"
    print(f"      Aranan: {hedef}  (12 frame)")
    try:
        v = VisionTracker()
        for i in range(12):
            t = v.find_target(hedef)
            durum = f"BULUNDU  güven={t.confidence:.0%}  hata_x={t.error_x:+.2f}" if t.found else "bulunamadı"
            print(f"      [{i+1:2d}] {durum}")
            time.sleep(0.2)
        v.stop()
        print("      ✓ Kamera OK\n")
    except Exception as e:
        print(f"      ✗ Kamera HATA: {e}\n")

    print("═══════════════════════════════════════")
    print("  TEST TAMAMLANDI")
    print("═══════════════════════════════════════\n")


# ── Giriş noktası ─────────────────────────────────────────────────────────────

def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    if "--test" in flags:
        _run_component_test()
        sys.exit(0)

    # Hedef ürün: argümandan veya kullanıcıdan al
    if args:
        target = " ".join(args)
    else:
        print()
        target = input("  Hangi ürünü arıyayım? >> ").strip()
        if not target:
            print("  Ürün adı boş, varsayılan kullanılıyor: Parol")
            target = "Parol"

    controller = RobotController(target)
    controller.run()
