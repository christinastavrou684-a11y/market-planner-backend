from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .models import SuggestRequest, SwapMealRequest
from .engine import (
    build_weekly_plan, assemble_plan, get_meal_alternative, load_recipes,
    add_live_prices_to_plan, DAYS, MEAL_ORDER,
)
from .scraper_sklavenitis import search_sklavenitis
from .scraper_mymarket import search_mymarket

app = FastAPI(title="Market Planner API", version="0.4.0")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_plan_ids(result):
    return {
        day: {meal: result["plan"][day][meal]["recipe_id"] for meal in MEAL_ORDER}
        for day in DAYS
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/scrape_test")
def scrape_test(query: str, max_results: int = 5):
    return search_sklavenitis(query, max_results=max_results)


@app.get("/scrape_test_mymarket")
def scrape_test_mymarket(query: str, max_results: int = 5):
    return search_mymarket(query, max_results=max_results)


@app.post("/suggest")
def suggest(request: SuggestRequest):
    # Βήμα 1: επιλογή γευμάτων με εκτιμώμενες τιμές (γρήγορο, χωρίς δίκτυο)
    result = build_weekly_plan(
        weekly_budget=request.weekly_budget,
        diet_type=request.diet_type,
        household_size=request.household_size,
        gender=request.gender,
        supermarket=request.supermarket,
        excluded_ingredients=request.excluded_ingredients,
        max_daily_kcal=request.max_daily_kcal,
        live_prices=None,
    )

    if not request.use_live_prices:
        return result

    # Βήμα 2: ξαναϋπολογισμός ΜΟΝΟ με τα υλικά που χρειάζεται αυτό το πλάνο
    data = load_recipes()
    plan_ids = _extract_plan_ids(result)
    return add_live_prices_to_plan(
        plan_ids=plan_ids,
        data=data,
        household_size=request.household_size,
        gender=request.gender,
        diet_type=request.diet_type,
        supermarket=request.supermarket,
        weekly_budget=request.weekly_budget,
        excluded_ingredients=request.excluded_ingredients,
        max_daily_kcal=request.max_daily_kcal,
    )


@app.post("/swap_meal")
def swap_meal(request: SwapMealRequest):
    current_recipe_id = request.plan_recipe_ids[request.day][request.meal]

    new_recipe_id = get_meal_alternative(
        day=request.day,
        meal=request.meal,
        current_recipe_id=current_recipe_id,
        diet_type=request.diet_type,
        household_size=request.household_size,
        gender=request.gender,
        excluded_ingredients=request.excluded_ingredients,
    )

    updated_plan_ids = {
        day: dict(meals) for day, meals in request.plan_recipe_ids.items()
    }
    updated_plan_ids[request.day][request.meal] = new_recipe_id

    data = load_recipes()

    if not request.use_live_prices:
        return assemble_plan(
            plan_ids=updated_plan_ids,
            data=data,
            household_size=request.household_size,
            gender=request.gender,
            diet_type=request.diet_type,
            supermarket=request.supermarket,
            weekly_budget=request.weekly_budget,
            excluded_ingredients=request.excluded_ingredients,
            max_daily_kcal=request.max_daily_kcal,
            apply_repairs=False,
            live_prices=None,
        )

    return add_live_prices_to_plan(
        plan_ids=updated_plan_ids,
        data=data,
        household_size=request.household_size,
        gender=request.gender,
        diet_type=request.diet_type,
        supermarket=request.supermarket,
        weekly_budget=request.weekly_budget,
        excluded_ingredients=request.excluded_ingredients,
        max_daily_kcal=request.max_daily_kcal,
    )


# Σερβίρει το frontend (index.html, style.css, script.js) στο "/".
# Πρέπει να μπει ΜΕΤΑ τα άλλα endpoints ώστε αυτά να έχουν προτεραιότητα.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
