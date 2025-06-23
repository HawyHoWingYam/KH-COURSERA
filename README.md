backend
cd GeminiOCR/backend     
uvicorn app:app --reload
or 
uvicorn app:app --host 0.0.0.0 --port 8000

frontend
cd GeminiOCR/frontend  
npm run dev


sudo systemctl restart gemini-ocr
npm run build
sudo systemctl restart gemini-frontend

To stop your backend and frontend services running on your EC2 instance, you can use the following commands:

### Stop the Backend (FastAPI)
If you're using systemd (which you are based on your previous setup):


```bash
sudo systemctl stop gemini-ocr
```

To verify it's stopped:
```bash
sudo systemctl status gemini-ocr
```

### Stop the Frontend (Next.js)
If you're using systemd:

```bash
sudo systemctl stop gemini-frontend
```

To verify it's stopped:
```bash
sudo systemctl status gemini-frontend
```

### Other Cleanup (Optional)

1. If you want to stop Nginx as well:
```bash
sudo systemctl stop nginx
```

2. If you used PM2 for any part of your setup:
```bash
pm2 stop all
```

### Disable Auto-start on Boot (Optional)

If you also want to prevent the services from starting automatically when the EC2 instance reboots:

```bash
sudo systemctl disable gemini-ocr
sudo systemctl disable gemini-frontend
sudo systemctl disable nginx  # if you want to disable Nginx too
```

These commands will gracefully shut down your services. You can always start them again later using the corresponding `start` commands:

```bash
sudo systemctl start gemini-ocr
sudo systemctl start gemini-frontend
sudo systemctl start nginx
```
