# Use an official Python runtime as a parent image
FROM python:3.14.1-alpine@sha256:b80c82b1a282283bd3e3cd3c6a4c895d56d1385879c8c82fa673e9eb4d6d4aa5

# Set working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt



# Copy the application files
COPY app /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Accept build arguments for versioning
ARG VERSION=unknown
ARG COMMIT_SHA=unknown
ARG BUILD_TIMESTAMP=unknown

ENV VERSION=${VERSION}
ENV COMMIT_SHA=${COMMIT_SHA}
ENV BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

# Create a non-root user and switch to it
RUN adduser -D appuser
USER appuser

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Use ENTRYPOINT to ensure the container runs as expected
ENTRYPOINT ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
