# Setup server (one-time)
From the project root:
For working with python venv:
```
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

# Setup UI (one-time)
```
cd frontend
npm install
```

# Start server
```
cd backend
python -m uvicorn backend.main:app --reload --host 0.0.0.0
```

# Start UI
```
cd frontend
npm start
```

# Testing agent
```
python -m backend.tests.test_agent
```