import json
import logging
import mimetypes
import os
import sys
import traceback
from dotenv import load_dotenv
from google import genai
from google.cloud import storage

# Configureer logging formaat
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pantry_updater")

# Laad .env variabelen (zonder gevoelige data te loggen)
load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("GCP_REGION", "europe-west4")
BUCKET_NAME = os.getenv("GCS_DATA_BUCKET")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

logger.info("Configuratie geladen:")
logger.info(f"  • GCP Project ID : {PROJECT_ID}")
logger.info(f"  • GCP Regio      : {REGION}")
logger.info(f"  • Data Bucket    : {BUCKET_NAME}")
logger.info(f"  • Model          : {MODEL_NAME}")

# SDK Initialisatie
try:
    logger.info("Initialiseren van Google Cloud Storage client...")
    storage_client = storage.Client(project=PROJECT_ID)
    logger.info("Storage client succesvol geïnitialiseerd.")
except Exception as e:
    logger.error(f"Fout bij initialiseren Storage client: {e}")
    logger.debug(traceback.format_exc())

try:
    logger.info(f"Initialiseren van GenAI client (Vertex AI in {REGION})...")
    genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)
    logger.info("GenAI client succesvol geïnitialiseerd.")
except Exception as e:
    logger.error(f"Fout bij initialiseren GenAI client: {e}")
    logger.debug(traceback.format_exc())


def get_mime_type(uri: str) -> str:
    """Bepaal het mime-type op basis van de bestandsextensie."""
    mime, _ = mimetypes.guess_type(uri)
    if not mime:
        if uri.lower().endswith((".jpg", ".jpeg")):
            mime = "image/jpeg"
        elif uri.lower().endswith(".png"):
            mime = "image/png"
        elif uri.lower().endswith(".webp"):
            mime = "image/webp"
        else:
            mime = "image/jpeg"  # Fallback
    return mime


def verify_gcs_blob(gcs_uri: str):
    """Controleer of de blob bestaat en toon metadata voor debugging."""
    try:
        if not gcs_uri.startswith("gs://"):
            logger.warning(f"URI '{gcs_uri}' begint niet met 'gs://'")
            return None
        parts = gcs_uri[5:].split("/", 1)
        bucket_name = parts[0]
        blob_name = parts[1] if len(parts) > 1 else ""

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.get_blob(blob_name)
        if blob:
            logger.info(f"Blob verificatie geslaagd: gs://{bucket_name}/{blob_name}")
            logger.info(f"  • Bestandsgrootte: {blob.size} bytes")
            logger.info(f"  • Content-type in GCS: {blob.content_type}")
            return blob
        else:
            logger.warning(f"⚠️ Let op: Blob niet gevonden via get_blob('gs://{bucket_name}/{blob_name}')")
            return None
    except Exception as e:
        logger.warning(f"⚠️ Kon blob metadata niet verifiëren: {e}")
        return None


def process_and_update_pantry(image_gcs_uri: str):
    logger.info("=" * 60)
    logger.info(f"Start verwerking voor URI: {image_gcs_uri}")
    logger.info("=" * 60)

    # Controleer de blob in GCS
    verify_gcs_blob(image_gcs_uri)

    # Bepaal het mime type
    detected_mime_type = get_mime_type(image_gcs_uri)
    logger.info(f"Gedetecteerd MIME-type: {detected_mime_type}")

    # 1. Beeld ontleden met Gemini Flash -> JSON
    prompt = "Geef alle boodschappen op de foto terug als JSON dict waarin de sleutel de productnaam is en de waarde het aantal: {'item_naam': aantal}"

    logger.info(f"Aanroepen van Gemini model '{MODEL_NAME}' via Vertex AI in '{REGION}'...")
    logger.info(f"  • File URI: {image_gcs_uri}")
    logger.info(f"  • Mime-type meegestuurd: {detected_mime_type}")
    logger.info(f"  • Prompt: {prompt}")

    try:
        part = genai.types.Part.from_uri(
            file_uri=image_gcs_uri,
            mime_type=detected_mime_type
        )
        logger.debug(f"Part object aangemaakt: {part}")

        response = genai_client.models.generate_content(
            model=MODEL_NAME,
            contents=[part, prompt],
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        logger.info("✅ Succesvolle reactie ontvangen van Gemini API!")
        logger.debug(f"Ruwe respons: {response}")
    except Exception as e:
        logger.error(f"❌ Fout tijdens aanroepen van Gemini: {e}")
        logger.error("Uitgebreide foutdetails:")
        logger.error(f"  • Error Type: {type(e).__name__}")
        logger.error(f"  • Error Args: {getattr(e, 'args', None)}")
        if hasattr(e, "code"):
            logger.error(f"  • Error Code: {e.code}")
        if hasattr(e, "message"):
            logger.error(f"  • Error Message: {e.message}")
        if hasattr(e, "response"):
            logger.error(f"  • Response details: {e.response}")

        logger.error("Volledige traceback:")
        logger.error(traceback.format_exc())

        logger.info("\n🔍 Tips voor troubleshooting:")
        logger.info("  1. Controleer of het model '%s' beschikbaar is in regio '%s'.", MODEL_NAME, REGION)
        logger.info("     (Populaire modellen: 'gemini-1.5-flash', 'gemini-2.0-flash').")
        logger.info("  2. Controleer of de Vertex AI Service Agent leestoegang heeft tot de bucket.")
        logger.info("     (Service account: service-<PROJECT_NUMBER>@gcp-sa-aiplatform.iam.gserviceaccount.com -> Storage Object Viewer).")
        logger.info("  3. Controleer of bestandsnamen met spaties of speciale tekens ondersteund worden.")
        return

    logger.info("Parsen van Gemini JSON output...")
    try:
        logger.debug(f"Gemini response text: {response.text}")
        new_detected_items = json.loads(response.text)
        logger.info(f"📦 Gedetecteerde items ({len(new_detected_items) if isinstance(new_detected_items, dict) else 'onbekend'} stuks): {new_detected_items}")
    except json.JSONDecodeError as jde:
        logger.error(f"❌ Fout bij het parsen van Gemini JSON output: {jde}")
        logger.error(f"Ontvangen tekst was:\n{response.text}")
        return

    # 2. Haal inventory.json op uit GCS
    logger.info(f"📥 Ophalen van inventory.json uit bucket: '{BUCKET_NAME}'...")
    try:
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob("inventory.json")

        if blob.exists():
            logger.info("ℹ️ Bestaande inventory.json gevonden. Inladen...")
            content = blob.download_as_text()
            logger.debug(f"Bestaande inhoud:\n{content}")
            try:
                current_data = json.loads(content)
            except json.JSONDecodeError:
                logger.warning("⚠️ inventory.json bevat ongeldige JSON. We beginnen met een lege inventaris.")
                current_data = {"items": {}}
        else:
            logger.info("ℹ️ Geen bestaande inventory.json gevonden. Nieuwe wordt aangemaakt.")
            current_data = {"items": {}}
    except Exception as e:
        logger.error(f"❌ Fout bij interactie met bucket '{BUCKET_NAME}': {e}")
        logger.error(traceback.format_exc())
        return

    if "items" not in current_data or not isinstance(current_data["items"], dict):
        current_data["items"] = {}

    # 3. Tel nieuwe items op bij de JSON-state
    if isinstance(new_detected_items, dict):
        logger.info("Bijwerken van inventaris:")
        for item, qty in new_detected_items.items():
            if isinstance(qty, (int, float)):
                item_lower = str(item).lower()
                oud_aantal = current_data["items"].get(item_lower, 0)
                nieuw_aantal = oud_aantal + int(qty)
                current_data["items"][item_lower] = nieuw_aantal
                logger.info(f"   ➕ '{item_lower}': {oud_aantal} -> {nieuw_aantal}")
            else:
                logger.warning(f"   ⚠️ Item '{item}' heeft ongeldig aantal: {qty}")
    else:
        logger.warning("⚠️ Gemini gaf geen dictionary terug. Geen items bijgewerkt.")

    # 4. Sla de bijgewerkte JSON direct op in GCS
    logger.info("📤 Opslaan van bijgewerkte inventory.json naar GCS...")
    try:
        updated_json_str = json.dumps(current_data, indent=2, ensure_ascii=False)
        blob.upload_from_string(
            data=updated_json_str,
            content_type="application/json"
        )
        logger.info("🎉 Inventory JSON succesvol geüpdatet op GCS!")
        logger.info(f"Huidige inventaris:\n{updated_json_str}")
    except Exception as e:
        logger.error(f"❌ Fout bij opslaan naar GCS: {e}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 GCS & Gemini Pantry Updater")
    logger.info("=" * 60)

    # 1. Check of er een URI meegegeven is via CLI argumenten: python gcs.py gs://bucket/foto.jpg
    target_uri = None
    if len(sys.argv) > 1:
        target_uri = sys.argv[1]
        logger.info(f"Argument ontvangen via CLI: {target_uri}")
    else:
        # 2. Zoek automatisch naar een afbeelding in de RAW bucket of DATA bucket
        raw_bucket_name = os.getenv("GCS_RAW_BUCKET", BUCKET_NAME)
        logger.info(f"🔍 Geen URI meegegeven als argument. Zoeken naar afbeeldingen in bucket '{raw_bucket_name}'...")
        try:
            raw_bucket = storage_client.bucket(raw_bucket_name)
            blobs = list(raw_bucket.list_blobs(max_results=20))
            logger.info(f"Aantal blobs gevonden in bucket: {len(blobs)}")
            for b in blobs:
                logger.debug(f"  - Blob: {b.name} ({b.size} bytes)")

            image_blobs = [b for b in blobs if b.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
            logger.info(f"Aantal afbeeldingen gevonden: {len(image_blobs)}")

            if image_blobs:
                target_blob = image_blobs[0]
                target_uri = f"gs://{raw_bucket_name}/{target_blob.name}"
                logger.info(f"👉 Automatisch eerste gevonden afbeelding geselecteerd: {target_uri}")
            else:
                logger.warning(f"⚠️ Geen afbeeldingen gevonden in bucket '{raw_bucket_name}'.")
        except Exception as e:
            logger.error(f"⚠️ Kon bucket '{raw_bucket_name}' niet doorzoeken: {e}")
            logger.error(traceback.format_exc())

    if target_uri:
        process_and_update_pantry(target_uri)
    else:
        logger.info("\n💡 Gebruik:")
        logger.info("   python gcs.py gs://<jouw-bucket>/<pad-naar-foto>.jpg")
        logger.info("   Of plaats eerst een foto (.jpg/.png) in je bucket.")
