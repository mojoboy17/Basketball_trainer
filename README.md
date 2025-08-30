# NBA Coach/Trainer AI

An interactive basketball trainer powered by OpenAI and NBA stats.

## Features
- Ask shooting form questions
- Get personalized training plans
- “Mirror a player” mode (e.g. Jordan Poole)
- General basketball Q&A

## Setup
```bash
git clone https://github.com/<mojoboy17>/basketball-trainer-ai.git
cd basketball-trainer-ai
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your keys
python coach_chat.py
