"""
Recommendation engine (rules-based, v1.4).
"""

import json
import math
import random
from pathlib import Path
from collections import defaultdict

from .price_service import get_live_prices_bulk

DATA_PATH = Path(__file__).parent / "data" / "recipes.json"

MEAL_ORDER = ["breakfast", "snack_morning", "lunch", "snack_afternoon", "dinner"]
MEAL_DATA_KEY = {
    "breakfast": "breakfast",
    "snack_morning": "snacks",
    "lunch": "lunch",
    "snack_afternoon": "snacks",
    "dinner": "dinner",
}

DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]

MAX_REPEATS_PER_WEEK = 2

GENDER_FACTOR = {
    "male": 1.15,
    "female": 0.90,
}

NOTE_TEXT_ESTIMATED = (
    "Οι τιμές είναι εκτιμήσεις. Η σύνδεση με πραγματικές τιμές από το επιλεγμένο "
    "σούπερ μάρκετ θα προστεθεί σε επόμενο βήμα."
)
NOTE_TEXT_LIVE = (
    "Οι τιμές προέρχονται από ζωντανή αναζήτηση στο επιλεγμένο σούπερ μάρκετ όπου "
    "ήταν δυνατό· όπου δεν βρέθηκε αποτέλεσμα, χρησιμοποιήθηκε εκτίμηση."
)


def load_recipes():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def all_recipes_by_id(data):
    recipes_by_id = {}
    for key in ("breakfast", "snacks", "lunch", "dinner"):
        for r in data[key]:
            recipes_by_id[r["id"]] = r
    return recipes_by_id


def all_ingredient_names(data) -> list:
    names = set()
    for key in ("breakfast", "snacks", "lunch", "dinner"):
        for recipe in data[key]:
            for ing in recipe["ingredients"]:
                names.add(ing["name"])
    return sorted(names)


def unit_multiplier(household_size: int, gender: str) -> float:
    return household_size * GENDER_FACTOR.get(gender, 1.0)


def effective_package_cost(ing: dict, live_prices: dict = None) -> float:
    if live_prices:
        live = live_prices.get(ing["name"])
        if live is not None:
            return live
    return ing["package_cost"]


def recipe_cost(recipe, household_size: int, gender: str, live_prices: dict = None) -> float:
    """Κόστος συνταγής βάσει ΑΝΑΛΟΓΙΚΗΣ εβδομαδιαίας τιμής -- προϊόντα
    ντουλάπας (weeks_per_package>1) μετράνε μόνο το αναλογικό τους μερίδιο."""
    mult = unit_multiplier(household_size, gender)
    total = 0.0
    for ing in recipe["ingredients"]:
        cost = effective_package_cost(ing, live_prices)
        weeks = ing.get("weeks_per_package", 1)
        unit_cost = (cost / weeks) / ing["package_size"]
        total += ing["quantity_per_person"] * mult * unit_cost
    return round(total, 2)


def recipe_kcal(recipe, gender: str) -> int:
    factor = GENDER_FACTOR.get(gender, 1.0)
    total = 0.0
    for ing in recipe["ingredients"]:
        total += ing["quantity_per_person"] * factor * ing["kcal_per_unit"]
    return round(total)


def recipe_macros(recipe, gender: str) -> dict:
    """Πρωτεΐνη/υδατάνθρακες/λίπος ΑΝΑ ΑΤΟΜΟ, σε γραμμάρια."""
    factor = GENDER_FACTOR.get(gender, 1.0)
    protein = carbs = fat = 0.0
    for ing in recipe["ingredients"]:
        qty = ing["quantity_per_person"] * factor
        protein += qty * ing.get("protein_g_per_unit", 0)
        carbs += qty * ing.get("carbs_g_per_unit", 0)
        fat += qty * ing.get("fat_g_per_unit", 0)
    return {"protein": round(protein, 1), "carbs": round(carbs, 1), "fat": round(fat, 1)}


def recipe_ingredients_per_person(recipe, gender: str):
    factor = GENDER_FACTOR.get(gender, 1.0)
    result = []
    for ing in recipe["ingredients"]:
        result.append({
            "name": ing["name"],
            "quantity": round(ing["quantity_per_person"] * factor, 3),
            "unit": ing["unit"],
        })
    return result


def filter_by_diet(recipes: list, diet_type: str) -> list:
    filtered = [r for r in recipes if diet_type in r["diet_types"]]
    return filtered if filtered else recipes


def filter_gluten_free(recipes: list, gluten_free: bool) -> list:
    if not gluten_free:
        return recipes
    filtered = [r for r in recipes if "gluten_free" in r["diet_types"]]
    return filtered if filtered else recipes  # fallback αν αδειάσει εντελώς


def filter_by_exclusions(recipes: list, excluded_ingredients: list) -> list:
    if not excluded_ingredients:
        return recipes
    terms = [t.strip().lower() for t in excluded_ingredients if t.strip()]
    if not terms:
        return recipes

    def is_allowed(recipe):
        for ing in recipe["ingredients"]:
            name_lower = ing["name"].lower()
            if any(term in name_lower for term in terms):
                return False
        return True

    return [r for r in recipes if is_allowed(r)]


def build_meal_pools(data, diet_type: str, excluded_ingredients: list, gluten_free: bool = False):
    pools = {}
    for meal in MEAL_ORDER:
        base = filter_by_diet(data[MEAL_DATA_KEY[meal]], diet_type)
        base = filter_gluten_free(base, gluten_free)
        without_exclusions = filter_by_exclusions(base, excluded_ingredients)
        pools[meal] = without_exclusions if without_exclusions else base
    return pools


def build_weekly_plan(
    weekly_budget: float,
    diet_type: str = "classic",
    household_size: int = 1,
    gender: str = "female",
    supermarket: str = "sklavenitis",
    excluded_ingredients: list = None,
    max_daily_kcal: float = None,
    live_prices: dict = None,
    gluten_free: bool = False,
):
    excluded_ingredients = excluded_ingredients or []
    data = load_recipes()
    meal_pools = build_meal_pools(data, diet_type, excluded_ingredients, gluten_free)

    total_slots = len(DAYS) * len(MEAL_ORDER)
    avg_target = weekly_budget / total_slots
    target_kcal_per_meal = (max_daily_kcal / len(MEAL_ORDER)) if max_daily_kcal else None

    plan_ids = {day: {} for day in DAYS}
    recent_by_meal = {meal: [] for meal in MEAL_ORDER}
    usage_count = {meal: defaultdict(int) for meal in MEAL_ORDER}

    for day in DAYS:
        for meal in MEAL_ORDER:
            pool = meal_pools[meal]
            candidates = [
                r for r in pool
                if r["id"] not in recent_by_meal[meal][-2:]
                and usage_count[meal][r["id"]] < MAX_REPEATS_PER_WEEK
            ]
            if not candidates:
                candidates = [r for r in pool if r["id"] not in recent_by_meal[meal][-2:]]
            if not candidates:
                candidates = pool

            def score(r):
                cost_dev = abs(recipe_cost(r, household_size, gender, live_prices) - avg_target)
                if target_kcal_per_meal:
                    kcal_dev = abs(recipe_kcal(r, gender) - target_kcal_per_meal)
                    return cost_dev + kcal_dev / 100
                return cost_dev

            candidates_sorted = sorted(candidates, key=score)
            top = candidates_sorted[:3] if len(candidates_sorted) >= 3 else candidates_sorted
            chosen = random.choice(top)

            plan_ids[day][meal] = chosen["id"]
            recent_by_meal[meal].append(chosen["id"])
            usage_count[meal][chosen["id"]] += 1

    result = assemble_plan(
        plan_ids, data, household_size, gender, diet_type, supermarket,
        weekly_budget, excluded_ingredients, max_daily_kcal, meal_pools,
        apply_repairs=True, live_prices=live_prices, gluten_free=gluten_free,
    )
    return result


def assemble_plan(
    plan_ids, data, household_size, gender, diet_type, supermarket,
    weekly_budget, excluded_ingredients, max_daily_kcal, meal_pools=None,
    apply_repairs=False, live_prices=None, gluten_free=False,
):
    recipes_by_id = all_recipes_by_id(data)
    if meal_pools is None:
        meal_pools = build_meal_pools(data, diet_type, excluded_ingredients, gluten_free)

    plan = {day: {} for day in DAYS}
    for day in DAYS:
        for meal in MEAL_ORDER:
            recipe = recipes_by_id[plan_ids[day][meal]]
            plan[day][meal] = {
                "recipe_id": recipe["id"],
                "name": recipe["name"],
                "estimated_cost": recipe_cost(recipe, household_size, gender, live_prices),
                "kcal": recipe_kcal(recipe, gender),
                "macros": recipe_macros(recipe, gender),
                "ingredients": recipe_ingredients_per_person(recipe, gender),
            }

    if apply_repairs:
        _repair_budget(plan, meal_pools, household_size, gender, weekly_budget, live_prices)
        if max_daily_kcal:
            _repair_calories(plan, meal_pools, household_size, gender, max_daily_kcal, live_prices)

    shopping_list = build_shopping_list(plan, data, household_size, gender, live_prices)
    packaged_total = round(sum(item["estimated_cost"] for item in shopping_list), 2)

    daily_kcal = {day: sum(plan[day][meal]["kcal"] for meal in MEAL_ORDER) for day in DAYS}
    avg_daily_kcal = round(sum(daily_kcal.values()) / len(DAYS))

    daily_macros = {}
    for day in DAYS:
        daily_macros[day] = {
            "protein": round(sum(plan[day][meal]["macros"]["protein"] for meal in MEAL_ORDER), 1),
            "carbs": round(sum(plan[day][meal]["macros"]["carbs"] for meal in MEAL_ORDER), 1),
            "fat": round(sum(plan[day][meal]["macros"]["fat"] for meal in MEAL_ORDER), 1),
        }
    avg_daily_macros = {
        "protein": round(sum(d["protein"] for d in daily_macros.values()) / len(DAYS), 1),
        "carbs": round(sum(d["carbs"] for d in daily_macros.values()) / len(DAYS), 1),
        "fat": round(sum(d["fat"] for d in daily_macros.values()) / len(DAYS), 1),
    }

    note = NOTE_TEXT_LIVE if live_prices else NOTE_TEXT_ESTIMATED

    return {
        "diet_type": diet_type,
        "household_size": household_size,
        "gender": gender,
        "supermarket": supermarket,
        "excluded_ingredients": excluded_ingredients,
        "max_daily_kcal": max_daily_kcal,
        "gluten_free": gluten_free,
        "weekly_budget": weekly_budget,
        "estimated_total_cost": packaged_total,
        "remaining_budget": round(weekly_budget - packaged_total, 2),
        "plan": plan,
        "daily_kcal": daily_kcal,
        "avg_daily_kcal": avg_daily_kcal,
        "daily_macros": daily_macros,
        "avg_daily_macros": avg_daily_macros,
        "shopping_list": shopping_list,
        "note": note,
        "live_prices_used": bool(live_prices),
    }


def _repair_budget(plan, meal_pools, household_size, gender, weekly_budget, live_prices=None):
    running_total = round(
        sum(plan[day][meal]["estimated_cost"] for day in DAYS for meal in MEAL_ORDER), 2
    )
    if running_total <= weekly_budget:
        return

    usage_count = {meal: defaultdict(int) for meal in MEAL_ORDER}
    for day in DAYS:
        for meal in MEAL_ORDER:
            usage_count[meal][plan[day][meal]["recipe_id"]] += 1

    all_slots = [(day, meal) for day in DAYS for meal in MEAL_ORDER]
    all_slots.sort(key=lambda s: plan[s[0]][s[1]]["estimated_cost"], reverse=True)
    for day, meal in all_slots:
        if running_total <= weekly_budget:
            break
        pool = meal_pools[meal]
        current_id = plan[day][meal]["recipe_id"]

        under_cap = [r for r in pool if usage_count[meal][r["id"]] < MAX_REPEATS_PER_WEEK]
        candidates_pool = under_cap if under_cap else pool

        cheapest = min(candidates_pool, key=lambda r: recipe_cost(r, household_size, gender, live_prices))
        cheapest_cost = recipe_cost(cheapest, household_size, gender, live_prices)
        current_cost = plan[day][meal]["estimated_cost"]
        if cheapest_cost < current_cost:
            running_total = round(running_total - current_cost + cheapest_cost, 2)
            usage_count[meal][current_id] -= 1
            usage_count[meal][cheapest["id"]] += 1
            plan[day][meal] = {
                "recipe_id": cheapest["id"],
                "name": cheapest["name"],
                "estimated_cost": cheapest_cost,
                "kcal": recipe_kcal(cheapest, gender),
                "macros": recipe_macros(cheapest, gender),
                "ingredients": recipe_ingredients_per_person(cheapest, gender),
            }


def _repair_calories(plan, meal_pools, household_size, gender, max_daily_kcal, live_prices=None):
    usage_count = {meal: defaultdict(int) for meal in MEAL_ORDER}
    for day in DAYS:
        for meal in MEAL_ORDER:
            usage_count[meal][plan[day][meal]["recipe_id"]] += 1

    for day in DAYS:
        day_total = sum(plan[day][meal]["kcal"] for meal in MEAL_ORDER)
        if day_total <= max_daily_kcal:
            continue
        meals_sorted = sorted(MEAL_ORDER, key=lambda m: plan[day][m]["kcal"], reverse=True)
        for meal in meals_sorted:
            if day_total <= max_daily_kcal:
                break
            pool = meal_pools[meal]
            current_id = plan[day][meal]["recipe_id"]

            under_cap = [r for r in pool if usage_count[meal][r["id"]] < MAX_REPEATS_PER_WEEK]
            candidates_pool = under_cap if under_cap else pool

            lightest = min(candidates_pool, key=lambda r: recipe_kcal(r, gender))
            lightest_kcal = recipe_kcal(lightest, gender)
            current_kcal = plan[day][meal]["kcal"]
            if lightest_kcal < current_kcal:
                day_total = day_total - current_kcal + lightest_kcal
                usage_count[meal][current_id] -= 1
                usage_count[meal][lightest["id"]] += 1
                plan[day][meal] = {
                    "recipe_id": lightest["id"],
                    "name": lightest["name"],
                    "estimated_cost": recipe_cost(lightest, household_size, gender, live_prices),
                    "kcal": lightest_kcal,
                    "macros": recipe_macros(lightest, gender),
                    "ingredients": recipe_ingredients_per_person(lightest, gender),
                }


def add_live_prices_to_plan(
    plan_ids, data, household_size, gender, diet_type, supermarket,
    weekly_budget, excluded_ingredients, max_daily_kcal, meal_pools=None,
    gluten_free=False,
):
    interim = assemble_plan(
        plan_ids, data, household_size, gender, diet_type, supermarket,
        weekly_budget, excluded_ingredients, max_daily_kcal, meal_pools,
        apply_repairs=False, live_prices=None, gluten_free=gluten_free,
    )
    needed_names = [item["name"] for item in interim["shopping_list"]]
    live_prices = get_live_prices_bulk(needed_names, supermarket)

    return assemble_plan(
        plan_ids, data, household_size, gender, diet_type, supermarket,
        weekly_budget, excluded_ingredients, max_daily_kcal, meal_pools,
        apply_repairs=True, live_prices=live_prices, gluten_free=gluten_free,
    )


def get_meal_alternative(
    day: str,
    meal: str,
    current_recipe_id: str,
    diet_type: str,
    household_size: int,
    gender: str,
    excluded_ingredients: list,
    gluten_free: bool = False,
):
    data = load_recipes()
    pool = filter_by_diet(data[MEAL_DATA_KEY[meal]], diet_type)
    pool = filter_gluten_free(pool, gluten_free)
    pool = filter_by_exclusions(pool, excluded_ingredients) or pool

    alternatives = [r for r in pool if r["id"] != current_recipe_id]
    if not alternatives:
        alternatives = pool
    chosen = random.choice(alternatives)
    return chosen["id"]


def build_shopping_list(plan, data, household_size: int, gender: str, live_prices: dict = None):
    recipes_by_id = all_recipes_by_id(data)
    mult = unit_multiplier(household_size, gender)
    aggregated = defaultdict(lambda: {
        "quantity": 0.0, "unit": "", "package_size": 0.0, "package_cost": 0.0, "weeks_per_package": 1,
    })

    for day in plan:
        for meal in MEAL_ORDER:
            recipe = recipes_by_id[plan[day][meal]["recipe_id"]]
            for ing in recipe["ingredients"]:
                key = (ing["name"], ing["unit"])
                aggregated[key]["quantity"] += ing["quantity_per_person"] * mult
                aggregated[key]["unit"] = ing["unit"]
                aggregated[key]["package_size"] = ing["package_size"]
                aggregated[key]["package_cost"] = effective_package_cost(ing, live_prices)
                aggregated[key]["weeks_per_package"] = ing.get("weeks_per_package", 1)

    shopping_list = []
    for (name, unit), vals in sorted(aggregated.items()):
        packages_needed = math.ceil(round(vals["quantity"] / vals["package_size"], 4))
        packages_needed = max(packages_needed, 1)
        full_purchase_cost = round(packages_needed * vals["package_cost"], 2)
        weeks = vals["weeks_per_package"]
        weekly_share_cost = round(full_purchase_cost / weeks, 2)

        shopping_list.append({
            "name": name,
            "needed_quantity": round(vals["quantity"], 2),
            "unit": unit,
            "packages": packages_needed,
            "package_size": vals["package_size"],
            "lasts_weeks": weeks,
            "full_purchase_cost": full_purchase_cost,
            "estimated_cost": weekly_share_cost,
        })

    return shopping_list
