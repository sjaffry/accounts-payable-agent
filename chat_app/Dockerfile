FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "google-cloud-aiplatform>=1.151.0" \
    streamlit \
    streamlit-authenticator \
    bcrypt \
    pyyaml

COPY chat_app.py .
COPY auth_config.yaml .

EXPOSE 8080

CMD ["streamlit", "run", "chat_app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true"]
