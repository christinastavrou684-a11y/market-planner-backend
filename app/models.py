from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict


class SuggestRequest(BaseModel):
    weekly_budget: float = Field(..., gt=0, description="Εβδομαδιαίο budget σε ευρώ")
    household_size: int = Field(1, ge=1, description="Αριθμός ατόμων στο νοικοκυριό")
    diet_type: Literal["classic", "vegetarian", "vegan"] = Field(
        "classic", description="Τύπος διατροφής"
    )
    gender: Literal["male", "female"] = Field(
        "female", description="Χρησιμοποιείται για προσαρμογή μερίδας/ποσοτήτων"
    )
    supermarket: Literal["sklavenitis", "mymarket"] = Field(
        "sklavenitis", description="Σούπερ μάρκετ αναφοράς για τις τιμές (placeholder προς το παρόν)"
    )
    excluded_ingredients: list[str] = Field(
        default_factory=list,
        description="Τροφές προς αποφυγή (αλλεργίες/δυσανεξίες/απλή προτίμηση), π.χ. ['γάλα', 'ξηροί καρποί']"
    )
    max_daily_kcal: Optional[float] = Field(
        None, gt=0, description="Προαιρετικό ανώτατο όριο ημερήσιων θερμίδων"
    )
    use_live_prices: bool = Field(
        True, description="Αν True, ψάχνει ζωντανές τιμές από το επιλεγμένο σούπερ μάρκετ"
    )


class SwapMealRequest(BaseModel):
    plan_recipe_ids: Dict[str, Dict[str, str]] = Field(
        ..., description="Τρέχον πλάνο: {ημέρα: {γεύμα: recipe_id}}"
    )
    day: str
    meal: str
    diet_type: Literal["classic", "vegetarian", "vegan"] = "classic"
    household_size: int = Field(1, ge=1)
    gender: Literal["male", "female"] = "female"
    supermarket: Literal["sklavenitis", "mymarket"] = "sklavenitis"
    weekly_budget: float = Field(..., gt=0)
    excluded_ingredients: list[str] = Field(default_factory=list)
    max_daily_kcal: Optional[float] = Field(None, gt=0)
    use_live_prices: bool = True
