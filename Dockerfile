FROM python:3.10.13-slim

RUN apt-get update && apt-get install -y curl

# Install dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Copy source code
COPY app /app
WORKDIR /app
ENTRYPOINT ["streamlit", "run", "web/app.py", "--server.port", "8501", "--server.headless", "true", "--server.address", "0.0.0.0"]
