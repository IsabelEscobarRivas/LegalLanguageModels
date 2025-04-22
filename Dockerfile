FROM python:3.9
# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# Download spaCy model
RUN python -m spacy download en_core_web_sm
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--reload"]