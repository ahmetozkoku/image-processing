# ─── Hedef ürün (başlangıçta kullanıcıdan sorulur, bu varsayılan) ────────────
TARGET_PRODUCT = "Parol"

# ─── Kamera ───────────────────────────────────────────────────────────────────
CAMERA_WIDTH  = 640
CAMERA_HEIGHT = 480

# ─── ToF sensör GPIO pinleri (BCM numarası) ───────────────────────────────────
TOF_LEFT_XSHUT_GPIO  = 17   # Sol sensör  → Pi GPIO17 (fiziksel pin 11)
TOF_RIGHT_XSHUT_GPIO = 27   # Sağ sensör  → Pi GPIO27 (fiziksel pin 13)
TOF_LEFT_ADDRESS     = 0x30 # Varsayılan 0x29 yerine yeni adres
TOF_RIGHT_ADDRESS    = 0x31

# ─── Mesafe eşikleri (mm) ─────────────────────────────────────────────────────
TARGET_DISTANCE_MM      = 150  # Bu mesafeye gelince dur (kutunun önü)
ALIGNMENT_THRESHOLD_MM  = 8    # Sol-sağ fark toleransı (±8mm tamam)

# ─── Görüntü merkezleme ───────────────────────────────────────────────────────
CENTER_THRESHOLD = 0.08   # ±8% piksel hatası = merkez sayılır (0.0–1.0 arası)
CENTERING_GAIN   = 25     # hata_x * gain = açı düzeltmesi (derece)

# ─── Servo ayarları ───────────────────────────────────────────────────────────
# Arduino'daki servo numaraları — robot koluna göre değiştir!
SERVO_BASE   = 1   # Yatay dönüş (sol-sağ)
SERVO_ELBOW  = 3   # İleri-geri yaklaşma

BASE_ANGLE   = 90  # Tüm servo'ların başlangıç (merkez) açısı

# ─── Kazanç katsayıları ───────────────────────────────────────────────────────
DISTANCE_GAIN       = 0.15   # (mesafe - hedef) * gain = açı adımı
ALIGNMENT_GAIN      = 0.3    # hizalama_hatası * gain = düzeltme açısı
MAX_STEP_DEG        = 15     # Tek adımda maksimum açı değişimi (derece)

# ─── Döngü hızı ───────────────────────────────────────────────────────────────
LOOP_HZ   = 10              # Kontrol döngüsü frekansı
LOOP_DELAY = 1.0 / LOOP_HZ  # saniye
