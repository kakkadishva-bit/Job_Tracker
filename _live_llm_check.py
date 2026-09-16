"""Live check: does the interview LLM provider actually get called?"""
import os
from dotenv import load_dotenv
load_dotenv()

from services.llm.grok_provider import get_interview_llm

llm = get_interview_llm()
print("PROVIDER:", llm.model_info())
print("HEALTH:", llm.health_check())

out = llm.generate_json(
    "Return JSON {\"question\": \"...\"} asking one question about the bias-variance tradeoff.",
    system_prompt="You are an interviewer. Output ONLY valid JSON.")
print("JSON OUT:", out)

txt = llm.generate("In one short sentence, define overfitting.")
print("TEXT OUT:", txt[:200])
