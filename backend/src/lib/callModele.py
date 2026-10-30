# src/agent.py
import os
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

# "test" = faux modèle (aucune clé requise), sinon un vrai modèle
MODEL_NAME = os.getenv("AI_MODEL", "test")

model = TestModel(custom_output_text="Je suis un agent teste, message suivant bien reçu : ") if MODEL_NAME == "test" else MODEL_NAME

chat_agent = Agent(
    model,
    system_prompt="Tu es un assistant de revue de presse.",
)

def call_modele(prompt:str):
    result = chat_agent.run_sync(prompt)
    response = result.output + "\n" + prompt   
    return response

if __name__ == '__main__':
    prompt = "teste prompt"
    result = call_modele("teste prompt")
    print(f"reponse modele : {result}")