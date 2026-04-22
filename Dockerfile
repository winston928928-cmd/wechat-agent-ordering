FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY static ./static
COPY prompts ./prompts
COPY docs ./docs
COPY README.md .

RUN mkdir -p /app/data/sessions /app/data/memory /app/data/channels

EXPOSE 8787

CMD ["python", "src/agent_server.py"]
