# ⚡ SEN România — Monitor Producție Live

Dashboard web care afișează **în timp real** valorile de producție din
Sistemul Energetic Național, preluate direct de la Transelectrica.

---

## Arhitectură

```
sen_monitor/
├── run.py                  ← punct de intrare (pornești de aici)
├── requirements.txt
├── backend/
│   ├── app.py              ← Flask server + APScheduler (job la 20 sec)
│   └── scraper.py          ← requests + BeautifulSoup → extrage datele
├── database/
│   ├── db.py               ← SQLite: init, insert, queries
│   └── sen_data.db         ← creat automat la prima rulare
└── frontend/
    └── index.html          ← UI complet, servit de Flask
```

**Flux de date:**
```
Transelectrica widget (HTML)
    ↓ la 20 secunde (APScheduler)
scraper.py → parsează HTML → extrage valori MW
    ↓
database/db.py → INSERT în SQLite
    ↓
Flask API (/api/latest, /api/history)
    ↓ polling JS (20 sec / 60 sec)
frontend/index.html → tabel live
```

---

## Instalare și rulare

### 1. Instalează Python 3.10+
Verifică: `python --version`

### 2. (Opțional) Creează un mediu virtual
```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### 3. Instalează dependințele
```bash
pip install -r requirements.txt
```

### 4. Pornește aplicația
```bash
python run.py
```

### 5. Deschide în browser
```
http://localhost:5000
```

---

## API Endpoints

| Endpoint | Descriere |
|---|---|
| `GET /api/latest` | Ultima citire live (JSON) |
| `GET /api/history?minutes=15` | Istoric agregat pe minut |
| `GET /api/status` | Status aplicație + ultima sincronizare |
| `GET /api/raw-recent?limit=50` | Ultimele N citiri brute |

---

## Câmpuri returnate

Toate valorile sunt în **MW** (megawați):

| Câmp | Sursă Transelectrica |
|---|---|
| `carbune` | -cărbune |
| `hidrocarburi` | -hidrocarburi |
| `hidro` | -hidro |
| `nuclear` | -nuclear |
| `eolian` | -eolian |
| `fotovoltaic` | -fotovoltaic |
| `biomasa` | -biomasă |
| `stocare` | -instalații de stocare |
| `consum` | Consum |
| `productie` | Producție |
| `sold` | Sold (- export / + import) |

---

## Logica agregării pe minut

- Fiecare citire brută este salvată cu timestamp exact (la secundă)
- Agregarea pe minut folosește **ultima citire din acel minut** (`MAX(timestamp)`)
- Dacă într-un minut nu există nicio citire (ex: server oprit), minutul respectiv
  **nu apare** în tabel — nu inserăm valori null artificiale

---

## Extindere ulterioară

Pentru a adăuga noi câmpuri (ex: sold import/export detaliat):
1. Adaugă coloana în `database/db.py` → `CREATE TABLE` + `INSERT`
2. Adaugă maparea în `backend/scraper.py` → `FIELD_MAP` + `ORDERED_KEYS`
3. Adaugă coloana în tabelul din `frontend/index.html`

---

## Depanare

**Toate valorile sunt 0 sau null:**
Transelectrica poate returna 0 noaptea sau în weekend.
Verifică în browser: https://www.transelectrica.ro/web/tel/sen-harta

**Eroare "source: error" în UI:**
Verifică conexiunea la internet și că transelectrica.ro este accesibil.

**Port 5000 ocupat:**
Modifică în `run.py`: `app.run(port=5001, ...)`
