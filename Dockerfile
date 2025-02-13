FROM python:3.9

# Install tesseract-ocr
RUN apt-get update && apt-get install -y tesseract-ocr

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--reload"]