"""
backend/scraper.py

Două strategii în ordine:
  1. Intercept XHR/fetch — dacă JS-ul paginii apelează un endpoint JSON,
     îl capturăm direct și nu mai atingem DOM-ul.
  2. Citire DOM cu auto-discovery — încearcă toate variantele cunoscute de ID
     pentru fiecare câmp și ia prima care returnează o valoare validă.
     Astfel, dacă Transelectrica redenumește un ID, scraper-ul se adaptează
     fără modificări de cod — adaugă doar noul ID în lista de candidați.
"""

import json
import re
import logging
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

logger = logging.getLogger("sen_monitor.scraper")

WIDGET_URL = (
    "https://www.transelectrica.ro/widget/web/tel/sen-harta/-/"
    "harta_WAR_SENOperareHartaportlet"
)

# ── Candidați de ID pentru fiecare câmp ──────────────────────────────────────
# Ordinea în listă = ordinea de prioritate.
# Dacă un ID returnează o valoare validă, îl folosim și îl logăm ca "confirmat".
# Adaugă orice ID nou la începutul listei potrivite după ce l-ai confirmat în browser.
DOM_CANDIDATES = {

    "consum": [
        "SEN_Harta_CONS_value",
        "SEN_Harta_CONSUM_value",
    ],

    "productie": [
        "SEN_Harta_PROD_value",
        "SEN_Harta_PRODUCTIE_value",
    ],

    "carbune": [
        "SEN_Harta_CARB_value",
        "SEN_Harta_CARBUNE_value",
        "SEN_Harta_COAL_value",
    ],

    "hidrocarburi": [
        "SEN_Harta_GAZE_value",
        "SEN_Harta_GAS_value",
        "SEN_Harta_HIDROCARBURI_value",
        "SEN_Harta_HC_value",
    ],

    "hidro": [
        "SEN_Harta_APE_value",
        "SEN_Harta_HIDRO_value",
        "SEN_Harta_HYDRO_value",
        "SEN_Harta_WATER_value",
    ],

    "nuclear": [
        "SEN_Harta_NUCL_value",
        "SEN_Harta_NUCLEAR_value",
        "SEN_Harta_NUC_value",
    ],

    # 🔥 FIXAT
    "eolian": [
        "SEN_Harta_EOLIAN_value",   # ✔ CONFIRMAT
        "SEN_Harta_WIND_value",
        "SEN_Harta_EOL_value",
        "SEN_Harta_WND_value",
    ],

    # 🔥 FIXAT
    "fotovoltaic": [
        "SEN_Harta_FV_value",
        "SEN_Harta_PV_value",
        "SEN_Harta_SOLAR_value",
        "SEN_Harta_FOTOVOLTAIC_value",
        "SEN_Harta_FOTO_value",   # ⚠ fallback (era sold)
    ],

    # 🔥 FIXAT
    "biomasa": [
        "SEN_Harta_BMASA_value",   # ✔ CONFIRMAT
        "SEN_Harta_BIOM_value",
        "SEN_Harta_BIO_value",
        "SEN_Harta_BIOMASA_value",
        "SEN_Harta_BIOGAS_value",
    ],

    # 🔥 FIXAT
    "stocare": [
        "SEN_Harta_ISPOZ_value",   # ✔ CONFIRMAT
        "SEN_Harta_STO_value",
        "SEN_Harta_STORAGE_value",
        "SEN_Harta_BAT_value",
        "SEN_Harta_STOR_value",
        "SEN_Harta_STOCARE_value",
    ],

    "sold": [
        "SEN_Harta_SOLD_value",
        "SEN_Harta_SCHIMB_value",
        "SEN_Harta_BALANCE_value",
        "SEN_Harta_SOLD_SCHIMB_value",
    ],
}
# Chei JSON pentru interceptarea endpointului intern
JSON_KEY_HINTS = {
    "cons": "consum",     "consum": "consum",
    "prod": "productie",  "productie": "productie",
    "carb": "carbune",    "carbune": "carbune",    "coal": "carbune",
    "gaze": "hidrocarburi","hidrocarburi": "hidrocarburi", "gas": "hidrocarburi",
    "ape":  "hidro",      "hidro": "hidro",         "hydro": "hidro",
    "nucl": "nuclear",    "nuclear": "nuclear",
    "eol":  "eolian",     "eolian": "eolian",       "wind": "eolian",
    "foto": "fotovoltaic","fotovoltaic": "fotovoltaic","solar": "fotovoltaic",
    "fv":   "fotovoltaic","pv": "fotovoltaic",
    "bio":  "biomasa",    "biomasa": "biomasa",
    "stor": "stocare",    "stocare": "stocare",     "bat": "stocare",
    "sold": "sold",       "balance": "sold",
}


def _to_float(s) -> float | None:
    if s is None:
        return None
    s = str(s).strip()
    if not s or s in ("-", "—", "N/A", ""):
        return None
    if ":" in s:
        return None
    cleaned = re.sub(r"[^\d.\-,]", "", s.replace("\xa0", "").replace(" ", ""))
    if not cleaned or cleaned == "-":
        return None
    cleaned = cleaned.replace(",", ".")
    parts = cleaned.split(".")
    if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
        cleaned = parts[0] + parts[1]
    elif len(parts) > 2:
        cleaned = "".join(parts)
    try:
        v = float(cleaned)
        return v if abs(v) <= 30_000 else None
    except ValueError:
        return None


def _empty_result() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        **{field: None for field in DOM_CANDIDATES},
    }


def _try_extract_json(body: str) -> dict | None:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict):
        return None
    result = {}
    for raw_key, raw_val in data.items():
        key_lower = raw_key.lower().replace("-", "_").replace(" ", "_")
        for hint, field in JSON_KEY_HINTS.items():
            if hint in key_lower and field not in result:
                v = _to_float(raw_val)
                if v is not None:
                    result[field] = v
                break
    return result if result else None


def _read_dom_with_discovery(page) -> dict:
    """
    Pentru fiecare câmp încearcă toți candidații de ID în ordine.
    Returnează primul ID care dă o valoare validă.
    Logează ce ID a fost folosit efectiv — util pentru a actualiza lista.
    """
    result = {}
    confirmed_map = {}   # câmp → ID confirmat

    for field, candidate_ids in DOM_CANDIDATES.items():
        for elem_id in candidate_ids:
            try:
                el = page.query_selector(f"#{elem_id}")
                if not el:
                    continue
                text = el.inner_text().strip()
                v = _to_float(text)
                if v is not None:
                    result[field] = v
                    confirmed_map[field] = elem_id
                    break
            except Exception as e:
                logger.debug("DOM eroare %s: %s", elem_id, e)

    # Log rezumat: ce ID a funcționat pentru fiecare câmp
    if confirmed_map:
        logger.info("ID-uri confirmate în DOM:")
        for field, elem_id in confirmed_map.items():
            logger.info("  %-15s ← %s = %s", field, elem_id, result.get(field))

    missing = [f for f in DOM_CANDIDATES if f not in result]
    if missing:
        logger.warning(
            "Câmpuri fără valoare (ID-urile nu există sau sunt goale): %s\n"
            "  → Rulează diagnose_ids.py local pentru a găsi ID-urile corecte.",
            missing
        )

    return result


def fetch_data() -> dict | None:
    intercepted_json: dict = {}

    def on_response(response):
        nonlocal intercepted_json
        if intercepted_json:
            return
        ct = response.headers.get("content-type", "")
        if "json" not in ct and "javascript" not in ct:
            return
        try:
            body = response.text()
            parsed = _try_extract_json(body)
            if parsed and len(parsed) >= 3:
                logger.info("JSON endpoint interceptat: %s (%d câmpuri)", response.url, len(parsed))
                intercepted_json = parsed
        except Exception:
            pass

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ro-RO",
            )
            page = context.new_page()
            page.on("response", on_response)

            logger.info("Playwright: deschid pagina...")
            try:
                page.goto(WIDGET_URL, wait_until="networkidle", timeout=30_000)
            except PWTimeout:
                logger.warning("networkidle timeout — continuu cu DOM curent")

            # Așteptăm orice element SEN_Harta
            try:
                page.wait_for_selector("[id*='SEN_Harta']", timeout=10_000)
            except PWTimeout:
                logger.warning("Niciun element SEN_Harta găsit în 10s")

            # ── Strategia 1: JSON interceptat ──
            if intercepted_json and len(intercepted_json) >= 5:
                logger.info("Strategia 1 (JSON): %d câmpuri", len(intercepted_json))
                result = _empty_result()
                result.update(intercepted_json)
            else:
                # ── Strategia 2: DOM cu auto-discovery ──
                logger.info("Strategia 2 (DOM auto-discovery)")
                dom_vals = _read_dom_with_discovery(page)

                if not dom_vals:
                    logger.error(
                        "Nicio valoare găsită. Rulează diagnose_ids.py local!\n"
                        "HTML snippet:\n%s", page.content()[:1500]
                    )
                    browser.close()
                    return None

                result = _empty_result()
                result.update(dom_vals)
                if intercepted_json:
                    for f, v in intercepted_json.items():
                        if result.get(f) is None:
                            result[f] = v

            browser.close()

        filled = sum(1 for k, v in result.items() if k != "timestamp" and v is not None)
        logger.info("Citire finală: %d/11 câmpuri | consum=%s | productie=%s",
                    filled, result.get("consum"), result.get("productie"))
        return result if filled > 0 else None

    except Exception as e:
        logger.error("fetch_data eroare: %s", e, exc_info=True)
        return None
