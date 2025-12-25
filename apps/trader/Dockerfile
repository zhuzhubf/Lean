FROM python:3.11-slim

WORKDIR /opt/trader

COPY apps/trader/requirements.txt requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY apps/trader/src ./src
ENV PYTHONPATH=/opt/trader/src

CMD ["python", "-m", "trader", "health"]
