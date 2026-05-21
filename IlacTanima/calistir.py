import cv2
from ultralytics import YOLO

# 1. Eğittiğin modeli yükle
# 'best.pt' dosyasının bu Python dosyasıyla aynı klasörde olduğundan emin ol
model = YOLO('best.pt')

# 2. Laptop kamerasını aç
cap = cv2.VideoCapture(0)

# Pencere ayarları
pencere_ismi = "YOLOv8 Ilac Tanima Sistemi"
cv2.namedWindow(pencere_ismi, cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty(pencere_ismi, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

print("Sistem başlatıldı. Kapatmak için klavyeden 'q' tuşuna basın.")

while True:
    # Kameradan görüntü oku
    success, frame = cap.read()

    if not success:
        print("Kamera görüntüsü alınamıyor!")
        break

    # --- AYNA ETKİSİ (Yatay Yansıtma) ---
    # 1 rakamı görüntüyü sağ-sol olarak çevirir
    frame = cv2.flip(frame, 1)

    # --- TAHMİN VE GÜVEN EŞİĞİ ---
    # conf=0.7: Model bir nesneden %70 emin değilse kutu çizmez.
    # Bu, alakasız nesnelerin kutu içine alınmasını büyük oranda engeller.
    results = model(frame, stream=True, conf=0.7)

    # Tahmin sonuçlarını görüntünün üzerine çiz
    for r in results:
        frame = r.plot()

    # Tam ekran penceresinde göster
    cv2.imshow(pencere_ismi, frame)

    # Çıkış kontrolü
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Kaynakları serbest bırak
cap.release()
cv2.destroyAllWindows()