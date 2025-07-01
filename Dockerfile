FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (just curl)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy app files
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application files
COPY . .

EXPOSE 8501

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--browser.gatherUsageStats", "false"]
