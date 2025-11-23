FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Cloud Run will set PORT env var, default 8080
ENV PORT=8080

# Start FastAPI app with uvicorn and bind to 0.0.0.0:$PORT
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
