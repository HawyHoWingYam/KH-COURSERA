backend
cd GeminiOCR/backend     
uvicorn app:app --reload
or
cd GeminiOCR/backend  
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4

frontend
cd GeminiOCR/frontend  
npm run dev