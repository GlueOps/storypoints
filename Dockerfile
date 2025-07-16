# Use an official Python runtime as a parent image
FROM python:3.11.13-alpine@sha256:a25e12e5f7bd9ce4578bc87eadec231cc3aa7d6a03723601d3e6f82639969d3a AS builder

# Set working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Use a smaller base image for the final image
FROM python:3.11.13-alpine@sha256:a25e12e5f7bd9ce4578bc87eadec231cc3aa7d6a03723601d3e6f82639969d3a

# Set working directory
WORKDIR /app

# Copy the dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

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