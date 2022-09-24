# syntax=docker/dockerfile:1
FROM python:3.10-slim-buster

WORKDIR /bot

# Install build time dependencies
RUN apt-get update \
    && apt-get install -y \
        build-essential

# Install runtime dependencies
COPY requirements.txt requirements.txt
RUN pip3 install -r "requirements.txt"

# Cleans up GCC and other build tools to make the final image smaller
RUN apt-get -y remove \
        build-essential \
        && apt-get -y autoremove \
        && apt-get clean

# Then finally run the bot
CMD ["python3", "/bot/main.py"]
