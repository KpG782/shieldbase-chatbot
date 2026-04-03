from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


CURRENT_YEAR = datetime.now(UTC).year


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    field: str | None = None
    message: str | None = None


def validate_quote_inputs(insurance_type: str, data: dict[str, Any]) -> ValidationResult:
    validators = {
        "auto": _validate_auto,
        "home": _validate_home,
        "life": _validate_life,
    }
    validator = validators.get(insurance_type)
    if validator is None:
        return ValidationResult(False, None, "Unsupported insurance type.")
    return validator(data)


def calculate_quote(insurance_type: str, data: dict[str, Any]) -> dict[str, Any]:
    calculators = {
        "auto": _calculate_auto,
        "home": _calculate_home,
        "life": _calculate_life,
    }
    calculator = calculators.get(insurance_type)
    if calculator is None:
        raise ValueError(f"Unsupported insurance type: {insurance_type}")
    return calculator(data)


def _validate_auto(data: dict[str, Any]) -> ValidationResult:
    year = int(data["vehicle_year"])
    if year <= 1900 or year > CURRENT_YEAR:
        return ValidationResult(False, "vehicle_year", f"Vehicle year must be between 1901 and {CURRENT_YEAR}.")

    vehicle_make = str(data["vehicle_make"]).strip()
    if len(vehicle_make) < 2:
        return ValidationResult(False, "vehicle_make", "Vehicle make must be at least 2 characters.")

    vehicle_model = str(data["vehicle_model"]).strip()
    if len(vehicle_model) < 2:
        return ValidationResult(False, "vehicle_model", "Vehicle model must be at least 2 characters.")

    driver_age = int(data["driver_age"])
    if driver_age < 16 or driver_age > 120:
        return ValidationResult(False, "driver_age", "Driver age must be between 16 and 120.")

    accidents = int(data["accidents_last_5yr"])
    if accidents < 0:
        return ValidationResult(False, "accidents_last_5yr", "Accident count cannot be negative.")

    coverage = str(data["coverage_level"]).lower()
    if coverage not in {"basic", "standard", "comprehensive"}:
        return ValidationResult(False, "coverage_level", "Coverage level must be basic, standard, or comprehensive.")

    return ValidationResult(True)


def _validate_home(data: dict[str, Any]) -> ValidationResult:
    property_type = str(data["property_type"]).lower()
    if property_type not in {"house", "condo", "apartment"}:
        return ValidationResult(False, "property_type", "Property type must be house, condo, or apartment.")

    location = str(data["location"]).strip()
    if len(location) < 2:
        return ValidationResult(False, "location", "Location must be at least 2 characters.")

    estimated_value = float(data["estimated_value"])
    if estimated_value <= 0:
        return ValidationResult(False, "estimated_value", "Estimated property value must be greater than 0.")

    year_built = int(data["year_built"])
    if year_built <= 1800 or year_built > CURRENT_YEAR:
        return ValidationResult(False, "year_built", f"Year built must be between 1801 and {CURRENT_YEAR}.")

    coverage = str(data["coverage_level"]).lower()
    if coverage not in {"basic", "standard", "comprehensive"}:
        return ValidationResult(False, "coverage_level", "Coverage level must be basic, standard, or comprehensive.")

    return ValidationResult(True)


def _validate_life(data: dict[str, Any]) -> ValidationResult:
    age = int(data["age"])
    if age < 18 or age > 85:
        return ValidationResult(False, "age", "Age must be between 18 and 85.")

    health_status = str(data["health_status"]).lower()
    if health_status not in {"excellent", "good", "fair", "poor"}:
        return ValidationResult(False, "health_status", "Health status must be excellent, good, fair, or poor.")

    coverage_amount = float(data["coverage_amount"])
    if coverage_amount <= 0:
        return ValidationResult(False, "coverage_amount", "Coverage amount must be greater than 0.")

    term_years = int(data["term_years"])
    if term_years not in {10, 20, 30}:
        return ValidationResult(False, "term_years", "Term years must be 10, 20, or 30.")

    return ValidationResult(True)


def _calculate_auto(data: dict[str, Any]) -> dict[str, Any]:
    base = 780.0
    age = int(data["driver_age"])
    accidents = int(data["accidents_last_5yr"])
    vehicle_year = int(data["vehicle_year"])
    coverage = str(data["coverage_level"]).lower()

    age_factor = 1.35 if age < 25 else 1.0 if age < 65 else 1.12
    history_factor = 1.0 + (0.18 * accidents)
    vehicle_age = max(0, CURRENT_YEAR - vehicle_year)
    vehicle_age_factor = 1.0 + min(vehicle_age, 20) * 0.01
    coverage_factor = {"basic": 0.92, "standard": 1.0, "comprehensive": 1.28}[coverage]
    premium = round(base * age_factor * history_factor * vehicle_age_factor * coverage_factor, 2)

    return {
        "product_type": "auto",
        "premium": premium,
        "currency": "USD",
        "coverage_level": coverage,
        "summary": f"Auto insurance quote for a {data['vehicle_year']} {data['vehicle_make']} {data['vehicle_model']}",
        "driver_age": age,
        "accidents_last_5yr": accidents,
    }


def _calculate_home(data: dict[str, Any]) -> dict[str, Any]:
    base = 640.0
    estimated_value = float(data["estimated_value"])
    year_built = int(data["year_built"])
    coverage = str(data["coverage_level"]).lower()

    property_value_factor = max(0.8, estimated_value / 350000.0)
    age_factor = 1.0 + min(max(CURRENT_YEAR - year_built, 0), 100) * 0.003
    coverage_factor = {"basic": 0.9, "standard": 1.0, "comprehensive": 1.24}[coverage]
    premium = round(base * property_value_factor * age_factor * coverage_factor, 2)

    return {
        "product_type": "home",
        "premium": premium,
        "currency": "USD",
        "coverage_level": coverage,
        "summary": f"Home insurance quote for a {data['property_type']} in {data['location']}",
        "estimated_value": estimated_value,
        "year_built": year_built,
    }


def _calculate_life(data: dict[str, Any]) -> dict[str, Any]:
    base = 420.0
    age = int(data["age"])
    health_status = str(data["health_status"]).lower()
    smoker = _to_bool(data["smoker"])
    coverage_amount = float(data["coverage_amount"])
    term_years = int(data["term_years"])
    coverage = str(data["coverage_level"]).lower()

    age_factor = 1.0 + max(age - 30, 0) * 0.018
    health_factor = {"excellent": 0.82, "good": 1.0, "fair": 1.2, "poor": 1.52}[health_status]
    smoker_factor = 1.55 if smoker else 1.0
    term_factor = {10: 0.85, 20: 1.0, 30: 1.18}[term_years]
    amount_factor = max(0.8, coverage_amount / 250000.0)
    coverage_factor = {"basic": 0.92, "standard": 1.0, "comprehensive": 1.16}[coverage]
    premium = round(base * age_factor * health_factor * smoker_factor * term_factor * amount_factor * coverage_factor, 2)

    return {
        "product_type": "life",
        "premium": premium,
        "currency": "USD",
        "coverage_level": coverage,
        "summary": f"Life insurance quote for a {term_years}-year term",
        "age": age,
        "health_status": health_status,
        "smoker": smoker,
        "coverage_amount": coverage_amount,
        "term_years": term_years,
    }


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "y", "1", "smoker"}
