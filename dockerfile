FROM python:3.12
WORKDIR /usr/local/app

COPY requirements.txt ./
COPY python_bot.py ./
COPY cogs ./cogs

RUN pip install --no-cache-dir -r requirements.txt --break-system-packages

RUN useradd -m botuser
USER botuser

CMD ["python", "python_bot.py"]