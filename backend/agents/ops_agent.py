"""
Ops Agent — MediFlow Agent 2
=============================
Monitors clinic operations and provides actionable suggestions to
administrators using the LLM.
"""

import json
import logging
from typing import Any, Dict, List

from services.llm_router import llm_router, AllProvidersExhausted

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the MediFlow Ops Intelligence Agent. Your goal is to analyze clinic metrics 
and recent activity to provide 3 actionable, high-impact suggestions for clinic managers.

Each suggestion must include:
1. title: A concise action (e.g., "Open 4 new slots for Dr. Khan").
2. impact: Predicted outcome (e.g., "−12 min avg wait").
3. confidence: A float between 0.0 and 1.0.

Metrics to consider:
- bookingVolume30m: High volume might need more slots.
- p95LatencyMs: High latency might indicate system stress.
- avgWait: High wait times need optimization.
- doctor availability: Doctors nearing capacity need load balancing.

Response MUST be a JSON list of objects:
[
  {"id": "s1", "title": "...", "impact": "...", "confidence": 0.9},
  ...
]
"""

class OpsAgent:
    async def get_suggestions(
        self, 
        metrics: Dict[str, Any], 
        activity: List[Dict[str, Any]],
        doctors: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generates suggestions based on current clinic state.
        """
        prompt = f"""
        Current Metrics: {json.dumps(metrics)}
        Recent Activity: {json.dumps(activity[:5])}
        Doctor Statuses: {json.dumps(doctors)}
        
        Generate 3 high-impact suggestions in JSON format.
        """
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = await llm_router.call(
                messages=messages,
                task_type="extraction",
                system=SYSTEM_PROMPT,
                temperature=0.3
            )
            
            # Extract JSON from response
            text = response.text.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start != -1 and end != -1:
                suggestions = json.loads(text[start:end])
                return suggestions
                
        except Exception as e:
            logger.error(f"OpsAgent failed to generate suggestions: {e}")
            
        # Fallback suggestions if LLM fails
        return [
            {"id": "f1", "title": "Review wait times for Dr. Malik", "impact": "Balance load", "confidence": 0.7},
            {"id": "f2", "title": "Check system latency alerts", "impact": "Stabilize API", "confidence": 0.8},
        ]

ops_agent = OpsAgent()
