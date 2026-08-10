FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501

# Agora o Docker vai iniciar o SEU script que roda tudo!
CMD ["python", "rodar_tudo.py"]