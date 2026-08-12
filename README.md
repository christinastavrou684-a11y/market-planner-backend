# Market Planner — Backend (v1)

Αυτό είναι το πρώτο κομμάτι: μηχανή προτάσεων γευμάτων βάσει budget.
Δεν έχει ακόμα σύνδεση με πραγματικές τιμές από σούπερ μάρκετ (έρχεται μετά).

## Πώς το τρέχεις (πρώτη φορά)

1. Άνοιξε το Terminal μέσα στο VS Code: **Terminal > New Terminal**
2. Δημιούργησε virtual environment:
   ```
   python3 -m venv venv
   ```
3. Ενεργοποίησε το venv:
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
4. Εγκατέστησε τα απαραίτητα πακέτα:
   ```
   pip install -r requirements.txt
   ```
5. Τρέξε τον server:
   ```
   uvicorn app.main:app --reload
   ```
6. Άνοιξε στον browser: http://127.0.0.1:8000/docs
   Εκεί θα δεις αυτόματο interactive UI (Swagger) όπου μπορείς να δοκιμάσεις
   το endpoint `/suggest` δίνοντας budget, household_size, diet_type.

## Deploy (Render.com)

Build Command: `pip install -r requirements.txt`
Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## Δομή

```
app/
  data/recipes.json   → βάση συνταγών με εκτιμώμενο κόστος
  engine.py            → λογική επιλογής γευμάτων & λίστας ψωνιών
  models.py            → σχήματα request/response
  main.py               → FastAPI app (εδώ ζει το /suggest endpoint)
```
