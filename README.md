backend
cd GeminiOCR/backend     
uvicorn app:app --reload
or 
uvicorn app:app --host 0.0.0.0 --port 8000

frontend
cd GeminiOCR/frontend  
npm run dev