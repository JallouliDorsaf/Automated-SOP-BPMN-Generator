import os
import requests
import os
import requests
from dotenv import load_dotenv


# ==============================================================================

class TogetherModelWrapper:
    def __init__(self, model_name):
        self.model = model_name
        self.api_key = os.getenv("TOGETHER_API_KEY")
        self.api_url = "https://api.together.xyz/inference"

    def __call__(self, prompt: str):
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "prompt": prompt,
                "max_tokens": 512,
                "temperature": 0.7
            }
        )

        if response.status_code != 200:
            raise RuntimeError(f"Together API error: {response.status_code}\n{response.text}")
        raw_output = response.json()["choices"][0]["text"]
        return raw_output.strip().strip("```").strip()


# ✅ Affichage simple du résultat uniquement
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()


    model_name = "mistralai/Mixtral-8x7B-Instruct-v0.1"
    together = TogetherModelWrapper(model_name)
    
    prompt = (
    "Décris uniquement les étapes concrètes du processus de préparation d'une tasse de thé "
    "sous forme d’un paragraphe clair et précis, sans introduction, définition, ni commentaire."
)

    

    
    result = together(prompt)
    print(result)



   



