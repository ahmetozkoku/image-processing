"""
İlaç Veritabanı Oluşturucu
--------------------------
Çalıştır: python scripts/build_database.py

1. Tip Atlası GitHub reposundan veri indirmeye çalışır.
2. Başarısız olursa yerleşik Türkiye ilaç listesiyle devam eder.
"""
import sys
import json
import sqlite3
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from src.database.drug_db import DrugDatabase

ILACDB_URL = config.ILACDB_RAW

# ── Yerleşik örnek ilaç verisi (Türkiye'de yaygın kullanılan ilaçlar) ─────────

SAMPLE_DRUGS = [
    # ── Senin test ettiğin ilaçlar ──────────────────────────────────────────
    {"name":"İbu Fort 400mg","active_ingredient":"İbuprofen","company":"Deva","barcode":"8699525090014","sgk_status":"SGK Geri Ödeniyor","dosage":"400 mg 30 film kaplı tablet","atc_code":"M01AE01","warnings":"Mide rahatsızlığı olanlarda yemekle birlikte alınmalıdır. Böbrek ve kalp yetmezliğinde dikkat.","prescription_type":"Reçetesiz"},
    {"name":"İbu Fort","active_ingredient":"İbuprofen","company":"Deva","barcode":"8699525090014","sgk_status":"SGK Geri Ödeniyor","dosage":"400 mg 30 film kaplı tablet","atc_code":"M01AE01","warnings":"Mide rahatsızlığı olanlarda yemekle birlikte alınmalıdır.","prescription_type":"Reçetesiz"},
    {"name":"Klamoks BID 1000mg","active_ingredient":"Amoksisilin + Klavulanik Asit","company":"Bilim İlaç","barcode":"8699525500016","sgk_status":"SGK Geri Ödeniyor","dosage":"1000 mg 14 film tablet","atc_code":"J01CR02","warnings":"Penisilin alerjisi kontrendikedir. Diyare görülebilir.","prescription_type":"Reçeteli"},
    {"name":"Klamoks","active_ingredient":"Amoksisilin + Klavulanik Asit","company":"Bilim İlaç","barcode":"8699525500023","sgk_status":"SGK Geri Ödeniyor","dosage":"625 mg 14 film tablet","atc_code":"J01CR02","warnings":"Penisilin alerjisi kontrendikedir.","prescription_type":"Reçeteli"},
    {"name":"Brelax 500mg","active_ingredient":"Methocarbamol","company":"Koçak Farma","barcode":"8699585500013","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 20 tablet","atc_code":"M03BA03","warnings":"Uyku getirebilir, araç kullanmayın. Alkol ile birlikte kullanılmamalıdır.","prescription_type":"Reçeteli"},
    {"name":"Brelax","active_ingredient":"Methocarbamol","company":"Koçak Farma","barcode":"8699585500013","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 20 tablet","atc_code":"M03BA03","warnings":"Uyku getirebilir, araç kullanmayın.","prescription_type":"Reçeteli"},
    {"name":"Kwellada Krem","active_ingredient":"Permetrin %5","company":"GlaxoSmithKline","barcode":"8699536600018","sgk_status":"SGK Geri Ödeniyor","dosage":"%5 30 g krem","atc_code":"P03AC04","warnings":"Göz ve mukoza temasından kaçının. Gebelikte dikkatli kullanın. 2 aydan küçük bebeklerde kullanılmaz.","prescription_type":"Reçeteli"},
    {"name":"Kwellada","active_ingredient":"Permetrin %5","company":"GlaxoSmithKline","barcode":"8699536600018","sgk_status":"SGK Geri Ödeniyor","dosage":"%5 30 g krem","atc_code":"P03AC04","warnings":"Uyuz ve bit tedavisinde kullanılır. Göz temasından kaçının.","prescription_type":"Reçeteli"},
    # ── Analjezik / Antipiretik ────────────────────────────────────────────
    {"name":"Parol 500mg","active_ingredient":"Parasetamol","company":"Atabay","barcode":"8699504090016","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 20 tablet","atc_code":"N02BE01","warnings":"Alkol kullanımında dikkatli olunmalıdır. Karaciğer hastaları uyarısı.","prescription_type":"Reçetesiz"},
    {"name":"Nurofen 400mg","active_ingredient":"İbuprofen","company":"Reckitt","barcode":"8699538090012","sgk_status":"SGK Geri Ödeniyor","dosage":"400 mg 20 tablet","atc_code":"M01AE01","warnings":"Mide rahatsızlığı olanlarda dikkatli kullanılmalıdır.","prescription_type":"Reçetesiz"},
    {"name":"Aspirin 500mg","active_ingredient":"Asetilsalisilik Asit","company":"Bayer","barcode":"8699518090018","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 20 tablet","atc_code":"B01AC06","warnings":"Çocuklarda (< 16 yaş) kullanılmamalıdır. Kanama riskini artırır.","prescription_type":"Reçetesiz"},
    {"name":"Tylol Hot 650mg","active_ingredient":"Parasetamol","company":"Abdi İbrahim","barcode":"8699514019014","sgk_status":"SGK Geri Ödeniyor","dosage":"650 mg 8 saşe","atc_code":"N02BE01","warnings":"Günlük maksimum doz aşılmamalıdır.","prescription_type":"Reçetesiz"},
    # Antibiyotik
    {"name":"Augmentin 1000mg","active_ingredient":"Amoksisilin + Klavulanik Asit","company":"GlaxoSmithKline","barcode":"8699536090014","sgk_status":"SGK Geri Ödeniyor","dosage":"1000 mg 14 film tablet","atc_code":"J01CR02","warnings":"Penisilin alerjisi olan hastalarda kontrendikedir.","prescription_type":"Reçeteli"},
    {"name":"Cipro 500mg","active_ingredient":"Siprofloksasin","company":"Bayer","barcode":"8699518500018","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 14 tablet","atc_code":"J01MA02","warnings":"18 yaş altı çocuklarda kullanılmamalıdır. Güneş ışığından kaçınılmalıdır.","prescription_type":"Reçeteli"},
    {"name":"Klarit 500mg","active_ingredient":"Klaritromisin","company":"Abdi İbrahim","barcode":"8699514019021","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 14 tablet","atc_code":"J01FA09","warnings":"QT uzaması riski. İlaç etkileşimlerine dikkat.","prescription_type":"Reçeteli"},
    {"name":"Amoksil 500mg","active_ingredient":"Amoksisilin","company":"GSK","barcode":"8699536500013","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 16 kapsül","atc_code":"J01CA04","warnings":"Penisilin alerjisinde kontrendike.","prescription_type":"Reçeteli"},
    # Kardiyoloji
    {"name":"Beloc 50mg","active_ingredient":"Metoprolol Tartrat","company":"AstraZeneca","barcode":"8699517090017","sgk_status":"SGK Geri Ödeniyor","dosage":"50 mg 20 tablet","atc_code":"C07AB02","warnings":"Aniden kesilmemelidir. Kalp yetersizliği izlemi gerektirir.","prescription_type":"Reçeteli"},
    {"name":"Coversyl 5mg","active_ingredient":"Perindopril Arjinin","company":"Servier","barcode":"8699817090011","sgk_status":"SGK Geri Ödeniyor","dosage":"5 mg 30 tablet","atc_code":"C09AA04","warnings":"Gebelikte kullanılmamalıdır. Anjiyoödem riski.","prescription_type":"Reçeteli"},
    {"name":"Concor 5mg","active_ingredient":"Bisoprolol","company":"Merck","barcode":"8699513090013","sgk_status":"SGK Geri Ödeniyor","dosage":"5 mg 28 tablet","atc_code":"C07AB07","warnings":"Astım hastalarında dikkatle kullanılmalıdır.","prescription_type":"Reçeteli"},
    {"name":"Norvasc 5mg","active_ingredient":"Amlodipin","company":"Pfizer","barcode":"8699514509010","sgk_status":"SGK Geri Ödeniyor","dosage":"5 mg 30 tablet","atc_code":"C08CA01","warnings":"Ayak bileği ödemi görülebilir.","prescription_type":"Reçeteli"},
    {"name":"Xarelto 20mg","active_ingredient":"Rivaroksaban","company":"Bayer","barcode":"8699518200019","sgk_status":"SGK Geri Ödeniyor","dosage":"20 mg 28 tablet","atc_code":"B01AF01","warnings":"Kanama riskini artırır. Böbrek fonksiyon takibi.","prescription_type":"Reçeteli"},
    # Kolesterol / Diyabet
    {"name":"Glucophage 1000mg","active_ingredient":"Metformin HCl","company":"Merck","barcode":"8699513100019","sgk_status":"SGK Geri Ödeniyor","dosage":"1000 mg 100 tablet","atc_code":"A10BA02","warnings":"Böbrek yetersizliğinde kontrendike. Kontrast madde öncesi kesilmeli.","prescription_type":"Reçeteli"},
    {"name":"Zocor 20mg","active_ingredient":"Simvastatin","company":"MSD","barcode":"8699509020011","sgk_status":"SGK Geri Ödeniyor","dosage":"20 mg 28 tablet","atc_code":"C10AA01","warnings":"Kas ağrısı izlenmeli. Greyfurt suyu etkileşimi.","prescription_type":"Reçeteli"},
    {"name":"Crestor 10mg","active_ingredient":"Rosuvastatin","company":"AstraZeneca","barcode":"8699517100016","sgk_status":"SGK Geri Ödeniyor","dosage":"10 mg 28 tablet","atc_code":"C10AA07","warnings":"Kas miyopatisi riski. Karaciğer enzim takibi.","prescription_type":"Reçeteli"},
    {"name":"Januvia 100mg","active_ingredient":"Sitagliptin","company":"MSD","barcode":"8699509100018","sgk_status":"SGK Geri Ödeniyor","dosage":"100 mg 28 tablet","atc_code":"A10BH01","warnings":"Pankreatit riski. Böbrek fonksiyonu izlenmeli.","prescription_type":"Reçeteli"},
    # Solunum / Astım
    {"name":"Ventolin İnhaler","active_ingredient":"Salbutamol","company":"GlaxoSmithKline","barcode":"8699536090021","sgk_status":"SGK Geri Ödeniyor","dosage":"100 mcg/doz 200 doz","atc_code":"R03AC02","warnings":"Doz aşımında kardiyak risk. Titreme ve çarpıntı görülebilir.","prescription_type":"Reçeteli"},
    {"name":"Symbicort 160/4.5","active_ingredient":"Budesonid / Formoterol","company":"AstraZeneca","barcode":"8699517160017","sgk_status":"SGK Geri Ödeniyor","dosage":"160/4.5 mcg 60 doz","atc_code":"R03AK07","warnings":"Uzun etkili beta agonist. Ağız gargarası yapılmalı.","prescription_type":"Reçeteli"},
    # Mide / Sindirim
    {"name":"Nexium 40mg","active_ingredient":"Esomeprazol","company":"AstraZeneca","barcode":"8699517040015","sgk_status":"SGK Geri Ödeniyor","dosage":"40 mg 28 kapsül","atc_code":"A02BC05","warnings":"Uzun süreli kullanımda magnezyum düşüklüğü.","prescription_type":"Reçeteli"},
    {"name":"Lansor 30mg","active_ingredient":"Lansoprazol","company":"Mustafa Nevzat","barcode":"8699598030019","sgk_status":"SGK Geri Ödeniyor","dosage":"30 mg 28 kapsül","atc_code":"A02BC03","warnings":"H. Pylori tedavisinde antibiyotikle birlikte kullanılır.","prescription_type":"Reçeteli"},
    {"name":"Duphalac","active_ingredient":"Laktuloz","company":"Abbott","barcode":"8699536070018","sgk_status":"SGK Geri Ödeniyor","dosage":"667 mg/mL 300 mL şurup","atc_code":"A06AD11","warnings":"Diyabetik hastalarda dikkatle kullanılmalıdır.","prescription_type":"Reçetesiz"},
    # Tiroid / Hormon
    {"name":"Euthyrox 100mcg","active_ingredient":"Levotiroksin Sodyum","company":"Merck","barcode":"8699513001017","sgk_status":"SGK Geri Ödeniyor","dosage":"100 mcg 100 tablet","atc_code":"H03AA01","warnings":"Aç karnına alınmalı. Tiroid hormon düzeyi takip edilmeli.","prescription_type":"Reçeteli"},
    # Nöroloji / Psikiyatri
    {"name":"Xanax 0.5mg","active_ingredient":"Alprazolam","company":"Pfizer","barcode":"8699514005018","sgk_status":"SGK Geri Ödeniyor","dosage":"0.5 mg 50 tablet","atc_code":"N05BA12","warnings":"Bağımlılık riski yüksek. Alkol ile birlikte kullanılmamalı. Araç kullanımını etkiler.","prescription_type":"Kontrollü Reçete"},
    {"name":"Depakin 500mg","active_ingredient":"Valproik Asit","company":"Sanofi","barcode":"8699715500016","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 30 enterik kaplı tablet","atc_code":"N03AG01","warnings":"Gebelikte teratojenik. Karaciğer fonksiyonu takip edilmeli.","prescription_type":"Reçeteli"},
    # Ağrı Kesici (Topikal)
    {"name":"Voltaren Emulgel 1%","active_ingredient":"Diklofenak Dietilamonyum","company":"Novartis","barcode":"8699514019038","sgk_status":"Geri Ödenmiyor","dosage":"1% 100g jel","atc_code":"M02AA15","warnings":"Hasar görmüş deriye uygulanmamalıdır.","prescription_type":"Reçetesiz"},
    # Damar
    {"name":"Daflon 500mg","active_ingredient":"Diosmina","company":"Servier","barcode":"8699817500018","sgk_status":"SGK Geri Ödeniyor","dosage":"500 mg 30 tablet","atc_code":"C05CA03","warnings":"Gebeliğin 3. trimesterinde dikkatli kullanılmalıdır.","prescription_type":"Reçetesiz"},
    # Göz
    {"name":"Tobrex Damla","active_ingredient":"Tobramisin","company":"Alcon","barcode":"8699800090017","sgk_status":"SGK Geri Ödeniyor","dosage":"0.3% 5 mL damla","atc_code":"S01AA12","warnings":"Kontakt lens takarken kullanılmamalı.","prescription_type":"Reçeteli"},
    # Vitamin
    {"name":"Redoxon 1000mg","active_ingredient":"Askorbik Asit (C Vitamini)","company":"Bayer","barcode":"8699518001012","sgk_status":"Geri Ödenmiyor","dosage":"1000 mg 30 efervesan tablet","atc_code":"A11GA01","warnings":"Böbrek taşı öyküsü olanlarda dikkatli kullanılmalı.","prescription_type":"Reçetesiz"},
    {"name":"Magnezyum Sandoz 300mg","active_ingredient":"Magnezyum","company":"Sandoz","barcode":"8699717300013","sgk_status":"Geri Ödenmiyor","dosage":"300 mg 20 efervesan tablet","atc_code":"A12CC","warnings":"Böbrek yetersizliğinde dikkat.","prescription_type":"Reçetesiz"},
]


def fetch_from_github() -> list:
    print("Tip Atlası veritabanından veri indiriliyor...")
    try:
        r = requests.get(ILACDB_URL, timeout=15)
        r.raise_for_status()
        data = r.json()
        rows = []
        for item in data:
            rows.append({
                "name":              item.get("isim", item.get("name", "")),
                "active_ingredient": item.get("etkinMadde", item.get("active_ingredient", "")),
                "company":           item.get("firma", item.get("company", "")),
                "barcode":           item.get("barkod", item.get("barcode", "")),
                "sgk_status":        item.get("sgkDurumu", "Bilinmiyor"),
                "dosage":            item.get("dozaj", ""),
                "atc_code":          item.get("atcKodu", ""),
                "warnings":          item.get("uyari", ""),
                "prescription_type": item.get("receteTuru", "Reçeteli"),
            })
        print(f"  {len(rows)} ilaç indirildi.")
        return rows
    except Exception as e:
        print(f"  GitHub'dan indirme başarısız: {e}")
        return []


def main():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = DrugDatabase(str(config.DB_PATH))

    rows = fetch_from_github()
    if not rows:
        print("Yerleşik örnek veri kullanılıyor...")
        rows = SAMPLE_DRUGS

    db.insert_bulk(rows)
    total = db.count()
    print(f"\n✅  Veritabanı hazır: {config.DB_PATH}")
    print(f"   Toplam kayıt: {total} ilaç")


if __name__ == "__main__":
    main()
