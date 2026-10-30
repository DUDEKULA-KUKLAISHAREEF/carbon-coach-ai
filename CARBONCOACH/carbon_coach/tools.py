"""
Carbon Coach Tools: Standard Python functions exposed to Google ADK Gemini agents.
Every tool performs deterministic, verified calculations using certified emission factors.
NO made-up numbers: all outputs originate strictly from these functions.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from carbon_coach.engine import CarbonEngine
from carbon_coach.memory_store import ActivityMemoryStore


def calculate_travel_emissions(mode: str, km: float) -> Dict[str, Any]:
    """
    Calculates carbon emissions in kg CO2e for travel based on transport mode and distance in kilometers.
    Supported modes: 'bus', 'train_metro', 'car_petrol', 'car_diesel', 'car_ev', 'two_wheeler_petrol',
    'two_wheeler_electric', 'auto_rickshaw', 'bicycle', 'walking', 'flight_economy'.
    Source: UK DEFRA 2023 & TERI Urban Mobility.
    """
    return CarbonEngine.calculate_travel_emissions(mode=mode, km=km)


def calculate_electricity_emissions(
    kwh: Optional[float] = None,
    appliance: Optional[str] = None,
    hours: Optional[float] = None,
    region: str = "india"
) -> Dict[str, Any]:
    """
    Calculates carbon emissions in kg CO2e for electricity consumption.
    Accepts either direct meter reading 'kwh', or appliance name (e.g. 'ac', 'fan', 'refrigerator',
    'desktop_pc', 'laptop', 'geyser', 'tv') and usage duration in 'hours'.
    Uses the Central Electricity Authority (CEA) India baseline grid factor (0.82 kg CO2e / kWh) by default.
    """
    return CarbonEngine.calculate_electricity_emissions(
        kwh=kwh, appliance=appliance, hours=hours, region=region
    )


def calculate_food_emissions(meal_type: str, servings: int = 1) -> Dict[str, Any]:
    """
    Calculates carbon emissions in kg CO2e for dietary choices based on meal type and servings.
    Supported meal types: 'vegan_meal', 'vegetarian_meal', 'dairy_rich_vegetarian',
    'chicken_poultry', 'fish_seafood', 'mutton_beef', 'fast_food'.
    Source: Poore & Nemecek, Science (2018) / Our World in Data.
    """
    return CarbonEngine.calculate_food_emissions(meal_type=meal_type, servings=servings)


def calculate_waste_emissions(waste_type: str, weight_kg: float) -> Dict[str, Any]:
    """
    Calculates carbon emissions in kg CO2e for solid waste generation and disposal.
    Supported waste types: 'food_organic_landfill', 'food_composted', 'plastic_landfilled',
    'plastic_recycled', 'paper_waste'.
    Source: US EPA WARM (Waste Reduction Model).
    """
    return CarbonEngine.calculate_waste_emissions(waste_type=waste_type, weight_kg=weight_kg)


def log_activity(
    category: str,
    details: str,
    emissions_kg: float,
    session_id: str = "default_session",
    entity_name: str = "User",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Logs a verified activity with calculated emissions into the user's session memory.
    Category must be one of: 'travel', 'electricity', 'food', 'waste', 'other'.
    """
    return ActivityMemoryStore.log_activity(
        session_id=session_id,
        category=category,
        description=details,
        emissions_kg=emissions_kg,
        entity_name=entity_name,
        metadata=metadata
    )


def get_summary(
    session_id: str = "default_session",
    period: str = "all_time"
) -> Dict[str, Any]:
    """
    Retrieves the aggregated emissions summary, category breakdown, activity count,
    and comparison against student daily targets (3.5 kg CO2e) and national baselines.
    """
    return ActivityMemoryStore.get_summary(session_id=session_id, period=period)


def suggest_reductions(session_id: str = "default_session") -> Dict[str, Any]:
    """
    Analyzes logged session activities and provides personalized, high-impact reduction recommendations
    with strictly calculated potential savings in kg CO2e per week and month.
    """
    activities = ActivityMemoryStore.get_activities(session_id=session_id)
    suggestions = CarbonEngine.compute_personalized_reductions(activities)
    summary = ActivityMemoryStore.get_summary(session_id=session_id)
    
    total_potential_weekly_savings = sum(s.get("weekly_saving_kg", 0.0) for s in suggestions)
    
    return {
        "status": "success",
        "current_total_kg": summary.get("total_emissions_kg_co2e", 0.0),
        "total_potential_weekly_savings_kg": round(total_potential_weekly_savings, 2),
        "total_potential_monthly_savings_kg": round(total_potential_weekly_savings * 4, 2),
        "recommendations": suggestions
    }


def get_campus_leaderboard() -> Dict[str, Any]:
    """
    Fetches the live campus leaderboard comparing hostels and academic departments
    by daily per-capita emissions and percentage reductions.
    """
    board = ActivityMemoryStore.get_campus_leaderboard()
    return {
        "status": "success",
        "campus": "DevFest Green Campus Benchmark 2026",
        "leaderboard": board
    }


# Tool list exported for Google ADK Agent
ALL_TOOLS = [
    calculate_travel_emissions,
    calculate_electricity_emissions,
    calculate_food_emissions,
    calculate_waste_emissions,
    log_activity,
    get_summary,
    suggest_reductions,
    get_campus_leaderboard
]
