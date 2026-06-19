FROM python:3.11-slim

WORKDIR /app

# Check karein ki files exist karti hain ya nahi
COPY requirements.txt .
COPY bot.py .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run bot
CMD ["python", "bot.py"]
