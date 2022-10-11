# syntax=docker/dockerfile:1
FROM python:3.10-slim-buster

WORKDIR /bot

# Does build process with the least amount of layers
COPY requirements.txt requirements.txt
RUN apt-get update \
    && apt-get install -y build-essential \
    && pip3 install -r "requirements.txt" \
    && apt-get -y remove build-essential \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Then finally run the bot
CMD ["python3", "/bot/main.py"]
