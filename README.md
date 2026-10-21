# 🛒 GCS & Gemini Pantry Updater

Een geautomatiseerde Python-toepassing die foto's van boodschappen of voorraad analyseert met **Google Cloud Storage (GCS)** en **Gemini Flash (Vertex AI)**. De gedetecteerde producten en aantallen worden automatisch gesynchroniseerd en bijgewerkt in een centrale `inventory.json` op GCS.

---

## 📋 Functionaliteiten

- 📸 **Multimodale AI-analyse**: Verwerkt afbeeldingen direct vanuit Google Cloud Storage met Gemini Flash via Vertex AI.
- 📦 **Automatische Voorraadbeheer**: Leest een bestaande `inventory.json` uit GCS, telt nieuw gedetecteerde producten op bij de huidige voorraad en slaat de bijgewerkte JSON direct weer op.
- 🔍 **Flexibele Invoer**:
  - Automatische detectie van de nieuwste foto in je raw-bucket als er geen argument wordt meegegeven.
  - Of specifieke analyse via een GCS URI als commandline-argument (`gs://...`).
- 🛡️ **Veilige Configuratie**: Gevoelige gegevens zoals GCP Project ID en bucket-namen worden beheerd via een `.env` bestand en nooit hardcoded in de code.

---

## 🚀 Installatie & Vereisten

### 1. Vereisten
- Python 3.10 of nieuwer
- Een Google Cloud Platform (GCP) project met:
  - **Vertex AI API** ingeschakeld
  - **Google Cloud Storage API** ingeschakeld
  - Twee GCS buckets (bijv. één voor onbewerkte foto's en één voor data/JSON)
  - Lokale authenticatie geconfigureerd via `gcloud auth application-default login`

### 2. Afhankelijkheden installeren
Installeer de vereiste Python packages:

```bash
pip install google-genai google-cloud-storage python-dotenv
```

---

## ⚙️ Configuratie

1. Kopieer het voorbeeldbestand `.env.example` naar `.env`:
   ```bash
   cp .env.example .env
   ```
2. Vul je eigen gegevens in binnen `.env`:
   ```ini
   GCP_PROJECT_ID=jouw-project-id
   GCP_REGION=europe-west4
   GCS_RAW_BUCKET=jouw-afbeeldingen-bucket
   GCS_DATA_BUCKET=jouw-data-bucket
   MODEL_NAME=gemini-2.5-flash
   ```

> ⚠️ **Let op:** Push **nooit** je echte `.env` bestand naar GitHub/GitLab. Zorg dat `.env` altijd in je `.gitignore` staat.

---

## 💻 Gebruik

### Automatische modus (zoekt de eerste foto in je raw-bucket)
```bash
python gcs.py
```

### Specifieke foto analyseren
Geef de volledige `gs://` URI mee als argument:
```bash
python gcs.py gs://jouw-raw-afbeeldingen-bucket/foto.jpg
```

---

## 📁 Bestandsstructuur

```text
├── gcs.py             # Hoofdscript voor GCS & Gemini logica
├── .env.example       # Template voor configuratievariabelen
├── .gitignore         # Voorkomt dat .env en tijdelijke bestanden worden gecommit
└── README.md          # Projectdocumentatie
```
