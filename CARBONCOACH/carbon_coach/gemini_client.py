"""
Pure Python Gemini REST API Client with Tool / Function Calling.
Directly interfaces with Google Gemini models (gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-flash).
Does not require pydantic_core or external compiled DLLs, making it 100% immune to Windows WDAC / AppLocker restrictions.
"""

from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Tuple

from carbon_coach.tools import (
    calculate_travel_emissions,
    calculate_electricity_emissions,
    calculate_food_emissions,
    calculate_waste_emissions,
    log_activity,
    get_summary,
    suggest_reductions,
    get_campus_leaderboard
)

GEMINI_TOOLS_DECLARATIONS = [
    {
        "name": "calculate_travel_emissions",
        "description": "Calculates carbon emissions in kg CO2e for travel based on mode (bus, car_petrol, car_diesel, car_ev, two_wheeler_petrol, train_metro, auto_rickshaw, bicycle, walking) and distance in km.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "mode": {"type": "STRING", "description": "Mode of transport: 'bus', 'car_petrol', 'car_diesel', 'car_ev', 'two_wheeler_petrol', 'train_metro', 'auto_rickshaw', 'bicycle', 'walking'"},
                "km": {"type": "NUMBER", "description": "Distance travelled in kilometers"}
            },
            "required": ["mode", "km"]
        }
    },
    {
        "name": "calculate_electricity_emissions",
        "description": "Calculates electricity emissions in kg CO2e. Accepts either direct 'kwh' or appliance name (ac, fan, refrigerator, laptop, desktop_pc, geyser, tv) and duration in 'hours'.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "kwh": {"type": "NUMBER", "description": "Direct meter kWh consumed"},
                "appliance": {"type": "STRING", "description": "Appliance name: 'ac', 'fan', 'refrigerator', 'laptop', 'desktop_pc', 'geyser', 'tv'"},
                "hours": {"type": "NUMBER", "description": "Duration in hours the appliance was used"}
            }
        }
    },
    {
        "name": "calculate_food_emissions",
        "description": "Calculates food carbon emissions in kg CO2e based on meal type ('vegan_meal', 'vegetarian_meal', 'dairy_rich_vegetarian', 'chicken_poultry', 'fish_seafood', 'mutton_beef', 'fast_food') and number of servings.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "meal_type": {"type": "STRING", "description": "Meal category: 'vegan_meal', 'vegetarian_meal', 'dairy_rich_vegetarian', 'chicken_poultry', 'fish_seafood', 'mutton_beef', 'fast_food'"},
                "servings": {"type": "INTEGER", "description": "Number of meals or servings (default: 1)"}
            },
            "required": ["meal_type"]
        }
    },
    {
        "name": "calculate_waste_emissions",
        "description": "Calculates emissions from solid waste disposal in kg CO2e.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "waste_type": {"type": "STRING", "description": "Type of waste: 'food_organic_landfill', 'food_composted', 'plastic_landfilled', 'plastic_recycled', 'paper_waste'"},
                "weight_kg": {"type": "NUMBER", "description": "Weight of waste in kilograms"}
            },
            "required": ["waste_type", "weight_kg"]
        }
    },
    {
        "name": "get_summary",
        "description": "Retrieves the aggregated emissions summary, category breakdown, and target benchmarks for the user's current session.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "session_id": {"type": "STRING", "description": "Current session identifier"}
            }
        }
    },
    {
        "name": "suggest_reductions",
        "description": "Analyzes logged activities and produces personalized, actionable reduction tips with exact calculated savings in kg CO2e per week.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "session_id": {"type": "STRING", "description": "Current session identifier"}
            }
        }
    },
    {
        "name": "get_campus_leaderboard",
        "description": "Retrieves rankings of campus hostels and academic departments showing per-capita daily emissions and reduction percentages.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }
]

SYSTEM_PROMPT = """You are the Carbon Coach, an intelligent sustainability assistant built for the DevFest Hackathon.
Your mission is to help people measure, understand, and reduce their carbon footprint.

STRICT ACCURACY RULES:
1. NEVER invent, hallucinate, or estimate emissions numbers yourself.
2. Every emission figure or reduction saving you cite MUST come from tool execution outputs.
3. When the user reports an activity (travel, electricity, food, waste):
   - ALWAYS call the matching calculation tool immediately.
4. When the user asks how they are doing, for a summary, or for reduction advice:
   - Call `get_summary` or `suggest_reductions`.
5. Support English, Hindi, and Telugu natively:
   - If the user talks in Telugu, respond in Telugu.
   - If the user talks in Hindi, respond in Hindi.
   - Default to English.
6. Always state the source (e.g. DEFRA 2023, CEA India Baseline v19, Science 2018) returned by the tool.
"""


def execute_tool_by_name(tool_name: str, args: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    """Routes function call to the corresponding certified Python tool and records in session memory."""
    if tool_name == "calculate_travel_emissions":
        mode = args.get("mode", "bus")
        km = float(args.get("km", 0.0))
        res = calculate_travel_emissions(mode=mode, km=km)
        log_activity("travel", f"{km} km by {mode}", res["emissions_kg_co2e"], session_id=session_id, metadata=res)
        return res
    elif tool_name == "calculate_electricity_emissions":
        kwh = args.get("kwh")
        if kwh is not None:
            kwh = float(kwh)
        appliance = args.get("appliance")
        hours = args.get("hours")
        if hours is not None:
            hours = float(hours)
        res = calculate_electricity_emissions(kwh=kwh, appliance=appliance, hours=hours)
        desc = f"{kwh} kWh electricity" if kwh is not None else f"{hours} hrs {appliance} usage"
        log_activity("electricity", desc, res["emissions_kg_co2e"], session_id=session_id, metadata=res)
        return res
    elif tool_name == "calculate_food_emissions":
        meal = args.get("meal_type", "vegetarian_meal")
        servings = int(args.get("servings", 1))
        res = calculate_food_emissions(meal_type=meal, servings=servings)
        log_activity("food", f"{servings}x {meal}", res["emissions_kg_co2e"], session_id=session_id, metadata=res)
        return res
    elif tool_name == "calculate_waste_emissions":
        waste = args.get("waste_type", "food_organic_landfill")
        weight = float(args.get("weight_kg", 1.0))
        res = calculate_waste_emissions(waste_type=waste, weight_kg=weight)
        log_activity("waste", f"{weight} kg {waste}", res["emissions_kg_co2e"], session_id=session_id, metadata=res)
        return res
    elif tool_name == "get_summary":
        sid = args.get("session_id") or session_id
        return get_summary(session_id=sid)
    elif tool_name == "suggest_reductions":
        sid = args.get("session_id") or session_id
        return suggest_reductions(session_id=sid)
    elif tool_name == "get_campus_leaderboard":
        return get_campus_leaderboard()
    return {"status": "error", "message": f"Unknown tool {tool_name}"}


def run_gemini_agent(message: str, session_id: str, api_key: str, model: str = "gemini-2.5-flash") -> Tuple[str, List[Dict[str, Any]]]:
    """
    Executes a complete Gemini conversational agent session with real Tool / Function Calling.
    """
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    # Initial payload
    contents = [
        {"role": "user", "parts": [{"text": message}]}
    ]

    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "tools": [
            {"functionDeclarations": GEMINI_TOOLS_DECLARATIONS}
        ]
    }

    tool_calls_trace = []

    # Maximum 3 tool call iterations
    for _ in range(3):
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=req_data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            raise RuntimeError(f"Gemini API HTTP {e.code}: {err_body}")
        except Exception as e:
            raise RuntimeError(f"Gemini API request failed: {e}")

        candidates = resp_json.get("candidates", [])
        if not candidates:
            return "No response from Gemini model.", tool_calls_trace

        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])

        # Check for function calls
        function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

        if not function_calls:
            # Model returned final text
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            final_reply = "".join(text_parts).strip()
            return final_reply, tool_calls_trace

        # Model requested function calls: execute each
        contents.append(content)  # Append model's tool call turn

        response_parts = []
        for fc in function_calls:
            t_name = fc["name"]
            t_args = fc.get("args", {})

            # Execute tool
            output = execute_tool_by_name(t_name, t_args, session_id)
            tool_calls_trace.append({
                "agent": "gemini_agent",
                "tool": t_name,
                "args": t_args,
                "output": output
            })

            response_parts.append({
                "functionResponse": {
                    "name": t_name,
                    "response": output
                }
            })

        contents.append({
            "role": "user",
            "parts": response_parts
        })
        payload["contents"] = contents

    # Fallback if loop ended
    return "I calculated your activities and saved them to your session log.", tool_calls_trace
