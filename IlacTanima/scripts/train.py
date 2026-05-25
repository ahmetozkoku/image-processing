"""
YOLOv11 Eğitim Scripti
-----------------------
Kullanım:
    python scripts/train.py
    python scripts/train.py --data data/dataset/prepared/dataset.yaml --epochs 100

GPU varsa otomatik kullanır. CPU'da da çalışır (yavaş).
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",   type=str, default=str(config.DATASET_DIR / "prepared" / "dataset.yaml"))
    parser.add_argument("--model",  type=str, default="yolo11n.pt",    help="Başlangıç modeli (yolo11n/s/m/l/x.pt)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz",  type=int, default=640)
    parser.add_argument("--batch",  type=int, default=16)
    parser.add_argument("--name",   type=str, default="ilac_tanima_v2")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"❌  Dataset YAML bulunamadı: {data_path}")
        print("    Önce şunu çalıştır: python scripts/prepare_dataset.py")
        sys.exit(1)

    from ultralytics import YOLO

    print(f"\n🚀  YOLOv11 eğitimi başlıyor...")
    print(f"   Dataset : {data_path}")
    print(f"   Model   : {args.model}")
    print(f"   Epochs  : {args.epochs}")
    print(f"   Image   : {args.imgsz}px\n")

    model = YOLO(args.model)
    results = model.train(
        data    = str(data_path),
        epochs  = args.epochs,
        imgsz   = args.imgsz,
        batch   = args.batch,
        name    = args.name,
        patience= 20,
        save    = True,
        plots   = True,
        augment = True,
        degrees = 15,
        flipud  = 0.3,
        fliplr  = 0.5,
        hsv_h   = 0.02,
        hsv_s   = 0.7,
        hsv_v   = 0.4,
        mosaic  = 1.0,
        mixup   = 0.1,
    )

    best_pt = Path("runs/detect") / args.name / "weights/best.pt"
    if best_pt.exists():
        dest = config.BASE_DIR / "best.pt"
        import shutil
        shutil.copy2(best_pt, dest)
        print(f"\n✅  Eğitim tamamlandı!")
        print(f"   En iyi model: {dest}")
        print(f"   Sonuçlar: runs/detect/{args.name}/")
    else:
        print("\n✅  Eğitim tamamlandı. Sonuçları 'runs/detect/' klasöründe inceleyebilirsin.")


if __name__ == "__main__":
    main()
