import os
import requests
from dotenv import load_dotenv

load_dotenv()

class N8NClient:
    def _post(self, env_key, payload):
        url=os.getenv(env_key)
        if not url: raise RuntimeError(f"{env_key} is not configured")
        response=requests.post(url,json=payload,timeout=30); response.raise_for_status()
        try: return response.json()
        except ValueError: return {"success": True, "raw": response.text}

    def check_slots(self,payload): return self._post("N8N_AVAILABLE_SLOTS_WEBHOOK",payload)
    def create_meeting(self,payload): return self._post("N8N_CREATE_EVENT_WEBHOOK",payload)

n8n_client=N8NClient()
