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
python -m uvicorn backend.main:app --reload
```

# Start UI
```
cd frontend
npm start
```
