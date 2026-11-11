import os
import sys
from pathlib import Path

# Configuration déterministe : aucun vrai modèle, aucune vraie clé, aucun coût.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-enough-randomness")
os.environ.setdefault("AI_MODEL", "test")
os.environ.setdefault("API_KEY_WORLD", "test-key")
os.environ.setdefault("MAMMOUTH_KEY", "")

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
