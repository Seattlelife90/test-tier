# 🎮 Game Pricing Recommendation Tool (Xbox + Steam)

## 📖 Overview
The **Game Pricing Recommendation Tool** is designed to automate **international pricing recommendations** for video games across **Xbox** and **Steam** platforms.  

It pulls live regional prices, applies **scale factors** and **weighting**, and generates **USD-normalized recommendations** with variance tracking against the US baseline.  

This tool is the **MVP (v1.0.0)** baseline — focused on **AAA titles** only. Future iterations will expand to **AA** and **Indie tiers**.

---

## ✅ Features
- Live **price pulls** from Steam and Xbox stores (all supported regions)  
- **Customizable baskets** — add/remove titles, apply scale factors, adjust weights  
- **Scale factor controls** for normalizing mid-tier games (e.g. $39.99 → $69.99 baseline)  
- **Weighted averages** per country  
- **FX conversion engine** with automatic USD normalization  
- **Variance analysis** (%Diff vs. US baseline)  
- **Vanity pricing support** (e.g., xx.95 endings by market)  
- **Consistent canonical titles** across all markets  

---

## ⚙️ Installation & Usage
Clone the repo and install dependencies:  
```bash
git clone https://github.com/Seattlelife90/test-tier.git
cd test-tier
pip install -r requirements.txt
```

Run locally:  
```bash
streamlit run streamlit_app.py
```

Or deploy directly to [Streamlit Cloud](https://share.streamlit.io).  

---

## 📊 Example Output
- **Raw basket rows** with scaling  
- **Xbox & Steam regional pricing recommendations** (local + USD + %Diff vs US)  
- Exportable tables for Excel / CSV  

---

## ⚠️ Known Limitations (MVP)
- Currently **AAA tier only** (no AA/Indie yet)  
- UI is functional but not yet optimized for very large pulls  
- FX benchmark only compares against **US baseline**  
- Steam/Xbox requests can be slow for large country lists  

---

## 🚀 Roadmap (v2+)
- Add **AA and Indie tier support**  
- **Genre-based pricing adjustments** (RPG, Shooter, Sports, etc.)  
- Enhanced **regional vanity pricing rules**  
- Performance improvements (async requests, caching)  
- Publisher-ready **reporting & dashboards**  

---

## 📌 Versioning
- **v1.0.0 (MVP)** → Baseline for AAA pricing  
- Future releases will expand scope and features  

---

## 👤 Author
Built by **Maxwell Morelly**  
💡 For professional use cases, publishing strategy, or SaaS applications.  
