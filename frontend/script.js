const DAY_ORDER = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"];
const MEAL_ORDER = ["breakfast", "snack_morning", "lunch", "snack_afternoon", "dinner"];
const MEAL_LABELS = {
  breakfast: "Πρωινό",
  snack_morning: "Δεκατιανό",
  lunch: "Μεσημεριανό",
  snack_afternoon: "Απογευματινό",
  dinner: "Βραδινό",
};
const SUPERMARKET_LABELS = { sklavenitis: "Σκλαβενίτης", mymarket: "My Market" };
const DIET_LABELS = { classic: "Κλασική", vegetarian: "Vegetarian", vegan: "Vegan" };
const GENDER_LABELS = { male: "Άντρας", female: "Γυναίκα" };

const form = document.getElementById("suggest-form");
const submitBtn = document.getElementById("submit-btn");
const errorMsg = document.getElementById("error-msg");
const resultPanel = document.getElementById("result-panel");
const planNote = document.getElementById("plan-note");
const daysContainer = document.getElementById("days-container");
const receiptMeta = document.getElementById("receipt-meta");
const receiptItems = document.getElementById("receipt-items");
const receiptTotal = document.getElementById("receipt-total");
const receiptFooter = document.getElementById("receipt-footer");

// Κρατάει τις τρέχουσες παραμέτρους + το πλάνο (recipe_id ανά ημέρα/γεύμα)
// ώστε να μπορούμε να ζητήσουμε swap ενός μεμονωμένου γεύματος αργότερα.
let currentParams = null;
let currentData = null;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  await runSuggest();
});

async function runSuggest() {
  errorMsg.hidden = true;
  submitBtn.disabled = true;
  submitBtn.textContent = "Φτιάχνω το πλάνο...";

  const excludedRaw = document.getElementById("excluded_ingredients").value;
  const excluded = excludedRaw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const maxKcalRaw = document.getElementById("max_daily_kcal").value;

  currentParams = {
    weekly_budget: parseFloat(document.getElementById("weekly_budget").value),
    household_size: parseInt(document.getElementById("household_size").value, 10),
    diet_type: document.getElementById("diet_type").value,
    gender: document.getElementById("gender").value,
    supermarket: document.getElementById("supermarket").value,
    excluded_ingredients: excluded,
    max_daily_kcal: maxKcalRaw ? parseFloat(maxKcalRaw) : null,
  };

  try {
    const res = await fetch("/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentParams),
    });

    if (!res.ok) {
      throw new Error(`Το API επέστρεψε σφάλμα (${res.status})`);
    }

    currentData = await res.json();
    renderAll(currentData);
    resultPanel.hidden = false;
  } catch (err) {
    showError(err);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Φτιάξε το πλάνο μου";
  }
}

async function swapMeal(day, meal) {
  const planRecipeIds = {};
  for (const d of DAY_ORDER) {
    planRecipeIds[d] = {};
    for (const m of MEAL_ORDER) {
      planRecipeIds[d][m] = currentData.plan[d][m].recipe_id;
    }
  }

  const payload = {
    plan_recipe_ids: planRecipeIds,
    day,
    meal,
    diet_type: currentParams.diet_type,
    household_size: currentParams.household_size,
    gender: currentParams.gender,
    supermarket: currentParams.supermarket,
    weekly_budget: currentParams.weekly_budget,
    excluded_ingredients: currentParams.excluded_ingredients,
    max_daily_kcal: currentParams.max_daily_kcal,
  };

  try {
    const res = await fetch("/swap_meal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Το API επέστρεψε σφάλμα (${res.status})`);

    currentData = await res.json();
    renderAll(currentData);
  } catch (err) {
    showError(err);
  }
}

function showError(err) {
  errorMsg.textContent = `Κάτι πήγε στραβά: ${err.message}. Σιγουρέψου ότι ο server (uvicorn) τρέχει.`;
  errorMsg.hidden = false;
}

function renderAll(data) {
  renderNote(data);
  renderPlan(data);
  renderReceipt(data);
}

function renderNote(data) {
  const store = SUPERMARKET_LABELS[data.supermarket] || data.supermarket;
  let text = `${data.note} Επιλεγμένο σούπερ μάρκετ: ${store}.`;
  if (data.excluded_ingredients && data.excluded_ingredients.length) {
    text += ` Εξαιρέθηκαν: ${data.excluded_ingredients.join(", ")}.`;
  }
  if (data.max_daily_kcal) {
    text += ` Όριο θερμίδων: ${data.max_daily_kcal} kcal/ημέρα.`;
  }
  planNote.textContent = text;
}

function renderPlan(data) {
  document.getElementById("plan-heading").textContent =
    `Το πλάνο της εβδομάδας — μέσος όρος ${data.avg_daily_kcal} kcal/ημέρα`;

  daysContainer.innerHTML = "";

  for (const day of DAY_ORDER) {
    const dayData = data.plan[day];
    if (!dayData) continue;

    const row = document.createElement("div");
    row.className = "day-row";

    const header = document.createElement("div");
    header.className = "day-header";
    header.innerHTML = `<span>${day}</span><span class="day-kcal">${data.daily_kcal[day]} kcal</span>`;
    row.appendChild(header);

    for (const mealKey of MEAL_ORDER) {
      const meal = dayData[mealKey];
      if (!meal) continue;

      const ingredientsText = meal.ingredients
        .map((ing) => formatIngredient(ing))
        .join(" · ");

      const mealRow = document.createElement("div");
      mealRow.className = "meal-row";
      mealRow.innerHTML = `
        <span class="meal-type">${MEAL_LABELS[mealKey]}</span>
        <span class="meal-main">
          <span class="meal-name">${meal.name}</span>
          <span class="meal-ingredients">${ingredientsText}</span>
        </span>
        <span class="meal-stats">
          <span class="meal-cost">${meal.estimated_cost.toFixed(2)}€</span>
          <span class="meal-kcal">${meal.kcal} kcal</span>
          <button type="button" class="swap-btn" title="Άλλαξε αυτό το γεύμα">🔄 αλλαγή</button>
        </span>
      `;
      mealRow.querySelector(".swap-btn").addEventListener("click", () => swapMeal(day, mealKey));
      row.appendChild(mealRow);
    }

    daysContainer.appendChild(row);
  }
}

function formatQty(q) {
  return q >= 1 ? q.toFixed(1).replace(/\.0$/, "") : q;
}

// Ενδεικτικά "σπιτικά" μέτρα για επιλεγμένα υλικά, ώστε να μη μένουν μόνο
// σε γραμμάρια/ml (π.χ. "30ml (2 κουταλιές) Ελαιόλαδο").
const TABLESPOON_ML = 15;
const CUP_ML = 240;
const TABLESPOON_G = 20; // π.χ. μέλι

const LIQUID_HINTS = {
  "Ελαιόλαδο": (ml) => tbspHint(ml / TABLESPOON_ML, "κουταλιά", "κουταλιές"),
  "Γάλα": (ml) => tbspHint(ml / CUP_ML, "ποτήρι", "ποτήρια"),
  "Φυτικό γάλα": (ml) => tbspHint(ml / CUP_ML, "ποτήρι", "ποτήρια"),
};

const SOLID_HINTS = {
  "Μέλι": (g) => tbspHint(g / TABLESPOON_G, "κουταλιά", "κουταλιές"),
};

function tbspHint(count, singular, plural) {
  if (count < 0.4) return null;
  const rounded = Math.round(count * 2) / 2; // στρογγυλοποίηση στο μισό
  const label = rounded === 1 ? singular : plural;
  const numText = Number.isInteger(rounded) ? rounded : rounded.toFixed(1);
  return `${numText} ${label}`;
}

function formatIngredient(ing) {
  const { name, unit, quantity } = ing;

  if (unit === "kg") {
    const grams = Math.round((quantity * 1000) / 5) * 5;
    const hint = SOLID_HINTS[name] ? SOLID_HINTS[name](grams) : null;
    return hint ? `${grams}γρ (${hint}) ${name}` : `${grams}γρ ${name}`;
  }

  if (unit === "l") {
    const ml = Math.round((quantity * 1000) / 5) * 5;
    const hint = LIQUID_HINTS[name] ? LIQUID_HINTS[name](ml) : null;
    return hint ? `${ml}ml (${hint}) ${name}` : `${ml}ml ${name}`;
  }

  if (unit === "τεμ") {
    const rounded = Math.max(1, Math.round(quantity));
    return `${rounded}τεμ ${name}`;
  }

  return `${formatQty(quantity)}${unit} ${name}`;
}

function renderReceipt(data) {
  const dietLabel = DIET_LABELS[data.diet_type] || data.diet_type;
  const genderLabel = GENDER_LABELS[data.gender] || data.gender;
  const storeLabel = SUPERMARKET_LABELS[data.supermarket] || data.supermarket;
  receiptMeta.textContent = `${data.household_size} άτομα (${genderLabel}) · ${dietLabel} · ${storeLabel}`;

  receiptItems.innerHTML = "";
  for (const item of data.shopping_list) {
    const row = document.createElement("div");
    row.className = "receipt-item";
    const packLabel = item.packages > 1 ? `${item.packages} συσκ.` : "1 συσκ.";
    const durationNote = item.lasts_weeks > 1 ? ` · διαρκεί ~${item.lasts_weeks} εβδ.` : "";
    const costNote = item.lasts_weeks > 1
      ? `${item.estimated_cost.toFixed(2)}€ <span class="qty">(μερίδιο εβδ. · πλήρης τιμή ${item.full_purchase_cost.toFixed(2)}€)</span>`
      : `${item.estimated_cost.toFixed(2)}€`;
    row.innerHTML = `
      <span>${item.name} <span class="qty">(${packLabel} × ${item.package_size}${item.unit}${durationNote})</span></span>
      <span>${costNote}</span>
    `;
    receiptItems.appendChild(row);
  }

  receiptTotal.innerHTML = `
    <div class="line grand">
      <span>ΣΥΝΟΛΟ</span>
      <span>${data.estimated_total_cost.toFixed(2)}€</span>
    </div>
    <div class="line remaining">
      <span>Διαφορά από budget</span>
      <span>${data.remaining_budget.toFixed(2)}€</span>
    </div>
  `;

  receiptFooter.textContent = "ΕΚΤΙΜΩΜΕΝΕΣ ΤΙΜΕΣ · ΟΧΙ ΤΕΛΙΚΕΣ";
}
