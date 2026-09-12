# HE THONG PHAN TICH RUI RO TIN DUNG & DU BAO KHA NANG VO NO KHACH HANG CA NHAN
> **Mon hoc:** Tuong tac Du lieu Truc quan  
> **Dataset:** Home Credit Default Risk (Kaggle)  
> **Muc tieu diem so:** 9.5/10 (A+)  
> **Nhom thuc hien:** 3 Thanh vien

---

## 1. GIOI THIEU DU AN
Du an xay dung giai phap hoan chinh tu tang ky thuat du lieu quan he da bang, mo hinh hoc may giai thich duoc (XAI), he thong cham diem tin dung (Credit Scorecard 300-850) den Dashboard truc quan tuong tac va cong cu mo phong tham dinh thoi gian thuc (What-if Simulator).

### Diem nhan khoa hoc vuot Barem:
1. **Credit Scoring System:** Anh xa xac suat vo no (PD) sang thang diem 300-850 qua cong thuc PDO.
2. **Expected Loss (EL):** Dinh luong so tien thiet hai giam thieu duoc theo chuan Basel: EL = PD x LGD x EAD.
3. **Mo hinh nang cao & XAI:** So sanh Logistic Regression baseline voi XGBoost; giai thich bang SHAP Values.
4. **Xu ly mat can bang:** So sanh unweighted, class_weight='balanced' va SMOTE tren training fold.
5. **Toi uu nguong quyet dinh:** Quet ma tran chi phi kinh doanh de tim nguong th* toi uu.
6. **Fairness Diagnostics:** Kiem toan tinh cong bang theo gioi tinh va do tuoi.
7. **Dashboard tuong tac:** Toi thieu 8 loai bieu do, ban do rui ro vung, Cross-filtering va What-if Simulator.

---

## 2. PHAN CONG TRACH NHIEM 3 THANH VIEN
* **Thanh vien 1 (Modeling & Machine Learning):**
  * Main: Baseline Logistic, XGBoost, tuning, SHAP, Credit Scoring 300-850, Expected Loss.
  * Secondary: Ho tro schema join va kiem toan ro ri du lieu (Leakage Audit).
* **Thanh vien 2 (Data Engineering & Pipeline):**
  * Main: Thu thap, clean DAYS_EMPLOYED=365243, aggregate 7 bang theo SK_ID_CURR, Calculated fields, EDA tinh.
  * Secondary: Fairness Check va quet ma tran chi phi nguong cat.
* **Thanh vien 3 (Dashboard & Visualization):**
  * Main: Dashboard Power BI / Streamlit, >=8 bieu do, Map vung, Cross-filtering, What-if Simulator.
  * Secondary: Truc quan hoa ho tro EDA tinh.
* **Lam chung ca 3 nguoi:** Storytelling 3 lop (Overview -> Diagnostic -> Prescriptive), Bao cao IEEE (>=40 trang), Slide va Video Demo (5-8 phut).

---

## 3. CAU TRUC REPOSITORY
`	ext
ttdltq/
|-- docs/                   # Tai lieu du an chia theo 4 thu muc con:
|   |-- overview/           # Tong quan de tai, Barem, PDF de bai
|   |-- contracts/          # data_contract.md & model_contract.md
|   |-- architecture/       # repo_structure_and_linkages.md & note.md
|   `-- tasks/              # Phan cong tong the & chi tiet 3 thanh vien
|-- data/
|   |-- raw/                # 7 file CSV tho tu Kaggle (duoc gitignore)
|   |-- interim/            # Bang trung gian sau aggregate
|   -- processed/          # cleaned_dataset.csv & data_dictionary.csv
|-- src/                    # Source code module dung chung
|   |-- data/               # Code load, clean, aggregate, build pipeline
|   |-- features/           # Code tao dac trung tai chinh (DTI, Annuity/Income...)
|   |-- models/             # Code tien xu ly, baseline, xgboost, scoring, threshold
|   -- dashboard/          # Backend cho What-if Simulator
|-- notebooks/              # 8 Jupyter Notebooks tuan tu tu 00 den 07
|-- models/                 # File model (.pkl) da huan luyen
|-- dashboard/              # Tep Power BI (.pbix) va Streamlit app
-- reports/                # Bao cao IEEE (>=40 trang), figures, slides, video link
`

---

## 4. HUONG DAN CAI DAT & TAI LAP KET QUA
1. Cai dat thu vien: pip install -r requirements.txt
2. Dat 7 file CSV Kaggle vao thu muc data/raw/
3. Chay pipeline lam sach: python -m src.data.build_pipeline
4. Chay cac notebook tuan tu trong thu muc 
otebooks/ tu 00 den 07.

---

## 5. SAN PHAM BAN GIAO
- Bao cao khoa hoc IEEE: 
eports/Report_Credit_Risk_IEEE.docx (>= 40 trang)
- Dashboard tuong tac: dashboard/Credit_Risk_Analytics.pbix
- Model Artifact: models/full_inference_pipeline.pkl
- Video Demo du phong: Xem link tai 
eports/video/video_demo_link.txt
