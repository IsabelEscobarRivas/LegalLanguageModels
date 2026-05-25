FROM python:3.11
# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# Install spaCy model directly from wheel (spacy download command is broken in 3.7.2)
RUN pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--reload"]