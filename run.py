"""
run.py — Ponto de entrada da aplicação Flask NeuralNotes.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / '.env')

from app import criar_app

app = criar_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000)) 
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'

    print(f"Iniciando NeuralNotes em http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)



