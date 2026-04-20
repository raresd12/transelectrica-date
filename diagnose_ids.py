"""
diagnose_ids.py
Rulează LOCAL (nu pe server) ca să găsești ID-urile corecte din pagina Transelectrica.

Utilizare:
    python diagnose_ids.py

Output:
    - toate elementele cu ID care conțin "SEN_Harta"
    - valoarea text din fiecare element
    - sugestia automată de DOM_ID_MAP corectat
"""

from playwright.sync_api import sync_playwright

WIDGET_URL = (
    "https://www.transelectrica.ro/widget/web/tel/sen-harta/-/"
    "harta_WAR_SENOperareHartaportlet"
)

# Cuvinte cheie pentru recunoașterea automată a câmpului din ID
FIELD_HINTS = {
    "cons":  "consum",
    "prod":  "productie",
    "carb":  "carbune",
    "coal":  "carbune",
    "gaze":  "hidrocarburi",
    "gas":   "hidrocarburi",
    "hidro": "hidrocarburi",   # hidrocarburi, nu hidro!
    "ape":   "hidro",
    "water": "hidro",
    "hydro": "hidro",
    "nucl":  "nuclear",
    "nuc":   "nuclear",
    "eol":   "eolian",
    "wind":  "eolian",
    "foto":  "fotovoltaic",
    "fv":    "fotovoltaic",
    "pv":    "fotovoltaic",
    "solar": "fotovoltaic",
    "bio":   "biomasa",
    "stor":  "stocare",
    "bat":   "stocare",
    "sold":  "sold",
    "balance": "sold",
    "schimb":  "sold",
}

def guess_field(elem_id: str) -> str:
    """Ghicește câmpul DB din ID-ul elementului."""
    id_lower = elem_id.lower()
    for hint, field in FIELD_HINTS.items():
        if hint in id_lower:
            return field
    return "???"

def main():
    print("=" * 65)
    print("  DIAGNOSTIC ID-URI SEN Harta — Transelectrica")
    print("=" * 65)
    print(f"  URL: {WIDGET_URL}\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()

        print("  Încarc pagina (poate dura 10-20 sec)...")
        try:
            page.goto(WIDGET_URL, wait_until="networkidle", timeout=30_000)
        except Exception:
            page.goto(WIDGET_URL, wait_until="domcontentloaded", timeout=15_000)

        # Așteptăm să apară cel puțin un element SEN_Harta
        try:
            page.wait_for_selector("[id*='SEN_Harta']", timeout=10_000)
        except Exception:
            print("  ATENȚIE: niciun element SEN_Harta găsit în 10 secunde.")

        # Găsim TOATE elementele cu ID care conțin SEN_Harta
        elements = page.query_selector_all("[id*='SEN_Harta']")

        print(f"\n  {len(elements)} elemente găsite cu ID '*SEN_Harta*':\n")
        print(f"  {'ID':50s}  {'Valoare':12s}  {'Câmp sugerat'}")
        print("  " + "-" * 80)

        found = {}
        for el in elements:
            elem_id = el.get_attribute("id") or ""
            text = el.inner_text().strip().replace("\n", " ")
            field = guess_field(elem_id)
            print(f"  {elem_id:50s}  {text:12s}  → {field}")
            if field != "???":
                found[elem_id] = field

        # Printăm DOM_ID_MAP sugerat
        print("\n" + "=" * 65)
        print("  DOM_ID_MAP SUGERAT (copiază în scraper.py):\n")
        print("  DOM_ID_MAP = {")
        for elem_id, field in found.items():
            print(f'      "{elem_id}": "{field}",')
        print("  }")

        # Salvăm și în fișier
        with open("diagnose_output.txt", "w", encoding="utf-8") as f:
            f.write("DOM_ID_MAP = {\n")
            for elem_id, field in found.items():
                f.write(f'    "{elem_id}": "{field}",\n')
            f.write("}\n")
        print("\n  Rezultat salvat și în: diagnose_output.txt")

        browser.close()

if __name__ == "__main__":
    main()
