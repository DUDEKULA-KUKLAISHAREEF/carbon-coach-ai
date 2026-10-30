"""
Google ADK Agent Definition: Carbon Coach Multi-Agent Architecture.
Consists of:
1. Tracker Agent: Specialized in logging activities & calculating emissions using tools.
2. Coach Agent: Specialized in synthesizing memory summaries, benchmarks, and actionable reduction tips.
3. Root Coordinator Agent (root_agent): Orchestrator supporting English, Hindi, and Telugu.
"""

from __future__ import annotations
import os

try:
    from google.adk.agents import Agent
    ADK_AVAILABLE = True
except Exception:
    Agent = None
    ADK_AVAILABLE = False

from carbon_coach.tools import (
    calculate_travel_emissions,
    calculate_electricity_emissions,
    calculate_food_emissions,
    calculate_waste_emissions,
    log_activity,
    get_summary,
    suggest_reductions,
    get_campus_leaderboard,
    ALL_TOOLS,
)

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# 1. Tracker Agent: Focuses on measurement and logging
TRACKER_INSTRUCTION = """
You are the Carbon Tracker Agent. Your sole responsibility is to accurately quantify greenhouse gas emissions
from human activities (travel, electricity, food, waste) and persist them into the user's session memory.

CRITICAL RULES:
1. NEVER invent, estimate, or make up emission numbers yourself.
2. You MUST ALWAYS call the corresponding calculation tool:
   - Travel (bus, car, metro, bike, flight, auto): call `calculate_travel_emissions(mode, km)`
   - Electricity (direct kWh or appliance + hours): call `calculate_electricity_emissions(kwh, appliance, hours)`
   - Food / Meals (veg, vegan, chicken, mutton, fast food): call `calculate_food_emissions(meal_type, servings)`
   - Solid Waste: call `calculate_waste_emissions(waste_type, weight_kg)`
3. After calculating, you MUST call `log_activity(...)` to record the activity in session memory.
4. Always state the emission factor and source returned by the tool (e.g. DEFRA 2023, CEA India 2023, Science 2018).
5. Support English, Hindi, and Telugu input seamlessly.
"""

class MockAgent:
    def __init__(self, name, description="", instruction="", tools=None, sub_agents=None, model=""):
        self.name = name
        self.description = description
        self.instruction = instruction
        self.tools = tools or []
        self.sub_agents = sub_agents or []
        self.model = model

AgentClass = Agent if Agent is not None else MockAgent

tracker_agent = AgentClass(
    name="tracker_agent",
    description="Calculates exact emissions for travel, electricity, food, and waste using certified tools and logs them to memory.",
    model=DEFAULT_MODEL,
    instruction=TRACKER_INSTRUCTION,
    tools=[
        calculate_travel_emissions,
        calculate_electricity_emissions,
        calculate_food_emissions,
        calculate_waste_emissions,
        log_activity,
    ],
)

# 2. Coach Agent: Focuses on analysis, benchmarking, and behavioral nudges
COACH_INSTRUCTION = """
You are the Carbon Coach Agent. Your role is to analyze the user's session emissions memory, evaluate
how they compare to student and campus benchmarks, and provide realistic, high-impact reduction strategies.

CRITICAL RULES:
1. ALWAYS use `get_summary(session_id)` to view logged emissions and category breakdowns.
2. ALWAYS use `suggest_reductions(session_id)` to produce personalized reduction suggestions.
3. ALWAYS use `get_campus_leaderboard()` when the user asks about hostel, department, or campus comparisons.
4. EVERY reduction suggestion must feature an exact calculated saving in kg CO2e from the tool. No hand-waving.
5. Provide encouraging, supportive, and practical advice tailored for students and households.
6. Support English, Hindi, and Telugu responses.
"""

coach_agent = AgentClass(
    name="coach_agent",
    description="Analyzes session footprint summaries, compares campus leaderboards, and provides actionable tips with calculated savings.",
    model=DEFAULT_MODEL,
    instruction=COACH_INSTRUCTION,
    tools=[
        get_summary,
        suggest_reductions,
        get_campus_leaderboard,
    ],
)

# 3. Root Coordinator Agent (Exposed as `root_agent` for Google ADK)
ROOT_INSTRUCTION = """
You are the Carbon Coach, an intelligent sustainability companion built with Google ADK for the DevFest Hackathon.
You help students, families, and campuses measure, understand, and reduce their carbon footprint.

CAPABILITIES:
- Conversational tracking: When the user shares daily activities (e.g. "I travelled 12 km by bus and used AC for 4 hours"),
  call the specialized tools to compute the emissions and log them.
- Session Memory & Insights: When the user asks "How am I doing?" or "Show my summary", retrieve their session footprint.
- Personalized Reductions: Deliver concrete tips with verified kg CO2e savings (e.g. raising AC temp, cycling short trips, green diet swaps).
- Campus Mode: Show how hostels and departments rank on the campus leaderboard.
- Multilingual:
  * If the user speaks Telugu (e.g. "ఈ రోజు నేను 12 కిమీ బస్సులో ప్రయాణించాను"), reply in Telugu.
  * If the user speaks Hindi (e.g. "मैंने आज 12 किमी बस से यात्रा की"), reply in Hindi.
  * Default to English.

ZERO HALLUCINATIONS:
Every carbon figure you cite MUST come from tool output. Do not make up emission factors or savings estimates.
Always celebrate positive steps and encourage sustainable choices!
"""

root_agent = AgentClass(
    name="carbon_coach",
    description="Root Carbon Coach agent that coordinates tracking, memory, and personalized carbon reduction tips.",
    model=DEFAULT_MODEL,
    instruction=ROOT_INSTRUCTION,
    tools=ALL_TOOLS,
    sub_agents=[tracker_agent, coach_agent],
)
