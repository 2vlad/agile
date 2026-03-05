FROM python:3.12-slim
WORKDIR /app
RUN useradd -r -s /bin/false appuser
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appuser . .
USER appuser
EXPOSE 8080
CMD ["uvicorn", "bot.main:app", "--host", "0.0.0.0", "--port", "8080"]
