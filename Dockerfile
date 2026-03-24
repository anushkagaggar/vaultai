FROM python:3.11-slim

WORKDIR /code

# Install torch CPU-only first (smaller)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies
COPY ./backend/requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt

# Copy backend code only
COPY ./backend /code

# Create user and fix ownership
RUN useradd -m -u 1000 user && chown -R user:user /code

USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH

WORKDIR /code

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]