"""Autorise l'accès Gmail (lecture des alertes + libellé `traité`) et enregistre le jeton.

À lancer une fois, sur ta machine (ouvre le navigateur) :
    cd pipeline && uv run python ../scripts/gmail_auth.py
Connecte-toi au compte qui REÇOIT les alertes. Le jeton est écrit dans credentials/ (hors dépôt).
"""
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / "credentials" / "gmail_client.json"
TOKEN = ROOT / "credentials" / "gmail_token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
PORT = 8765  # fixe : plus simple à rediriger sous WSL


def main() -> int:
    if not CLIENT.exists():
        print(f"Fichier manquant : {CLIENT}", file=sys.stderr)
        return 1
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES)
    print("1. Copie le lien ci-dessous dans ton navigateur et connecte-toi au compte des alertes.")
    print("2. NE FERME PAS ce terminal : il attend le retour de Google (jusqu'à 5 minutes).\n")
    creds = flow.run_local_server(
        port=PORT, open_browser=False, timeout_seconds=300,
        access_type="offline", prompt="consent",
        authorization_prompt_message="Lien : {url}\n",
        success_message="Autorisation reçue : tu peux fermer cet onglet et revenir au terminal.",
    )
    TOKEN.write_text(creds.to_json())
    TOKEN.chmod(0o600)
    print(f"Jeton enregistré : {TOKEN}")
    if not creds.refresh_token:
        print("⚠ Pas de refresh_token : relance après avoir révoqué l'accès sur myaccount.google.com/permissions")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
