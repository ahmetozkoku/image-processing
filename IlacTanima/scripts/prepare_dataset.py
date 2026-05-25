"""
Dataset Hazırlama Scripti
--------------------------
Kaggle'dan indirdiğin dataset klasörünü YOLOv11 formatına hazırlar.
Roboflow'dan ek dataset de indirebilir.

Kullanım:
    python scripts/prepare_dataset.py --source data/dataset/kaggle_dataset
    python scripts/prepare_dataset.py --roboflow  (Roboflow datasetini de indir)
"""
import sys
import shutil
import random
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

TRAIN_RATIO = 0.80
VAL_RATIO   = 0.10
TEST_RATIO  = 0.10
EXTENSIONS  = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def split_dataset(source_dir: Path, out_dir: Path):
    """Klasördeki görüntüleri train/val/test olarak böler."""
    images = [p for p in source_dir.rglob("*") if p.suffix.lower() in EXTENSIONS]
    if not images:
        print(f"  Görüntü bulunamadı: {source_dir}")
        return

    random.shuffle(images)
    n = len(images)
    n_train = int(n * TRAIN_RATIO)
    n_val   = int(n * VAL_RATIO)

    splits = {
        "train": images[:n_train],
        "val":   images[n_train:n_train + n_val],
        "test":  images[n_train + n_val:],
    }

    for split, paths in splits.items():
        img_dir = out_dir / split / "images"
        lbl_dir = out_dir / split / "labels"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        for src in paths:
            shutil.copy2(src, img_dir / src.name)
            label_src = src.with_suffix(".txt")
            if label_src.exists():
                shutil.copy2(label_src, lbl_dir / label_src.name)

        print(f"  {split:5s}: {len(paths)} görüntü")


def write_yaml(out_dir: Path, class_names: list):
    nc = len(class_names)
    names_str = "\n  ".join(f"- {n}" for n in class_names)
    yaml_content = f"""path: {out_dir.resolve()}
train: train/images
val:   val/images
test:  test/images

nc: {nc}
names:
  {names_str}
"""
    yaml_path = out_dir / "dataset.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    print(f"\n  YAML: {yaml_path}")
    return yaml_path


def detect_classes(source_dir: Path) -> list:
    """Alt klasör isimlerini sınıf isimleri olarak kullan."""
    subdirs = sorted([d.name for d in source_dir.iterdir() if d.is_dir()])
    return subdirs if subdirs else ["drug_box"]


def main():
    parser = argparse.ArgumentParser(description="Dataset hazırlama")
    parser.add_argument("--source", type=str,
                        default=str(config.DATASET_DIR / "raw"),
                        help="Ham görüntülerin bulunduğu klasör")
    parser.add_argument("--out", type=str,
                        default=str(config.DATASET_DIR / "prepared"),
                        help="Hazırlanan dataset çıktı klasörü")
    args = parser.parse_args()

    source = Path(args.source)
    out    = Path(args.out)

    if not source.exists():
        print(f"❌  Kaynak klasör bulunamadı: {source}")
        print(f"    Kaggle datasetini şuraya koy: {source}")
        sys.exit(1)

    print(f"\n📁  Kaynak: {source}")
    print(f"📁  Çıktı : {out}\n")

    classes = detect_classes(source)
    print(f"Sınıflar ({len(classes)}): {classes}")

    if classes and (source / classes[0]).is_dir():
        # Sınıf bazlı klasör yapısı (classification formatı)
        for cls_dir in sorted(source.iterdir()):
            if cls_dir.is_dir():
                split_dataset(cls_dir, out / cls_dir.name)
        write_yaml(out, classes)
    else:
        # Düz klasör (YOLO formatı zaten)
        split_dataset(source, out)
        write_yaml(out, classes)

    print("\n✅  Dataset hazır!")
    print(f"   Şimdi şunu çalıştır: python scripts/train.py --data {out}/dataset.yaml")


if __name__ == "__main__":
    main()
