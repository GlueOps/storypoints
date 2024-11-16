# storypoints


This project is a FastAPI application designed to handle GitHub webhooks and automate the process of adding issues to GitHub Projects V2. It listens for specific events from GitHub, such as when an issue is opened or reopened, and automatically adds the issue to a specified GitHub Project V2. This automation helps maintain an up-to-date project board without manual intervention, allowing your team to focus on resolving issues rather than managing them.

## Features

- **Webhook Handling**: Listens for GitHub webhook events and processes them.
- **Project Management**: Adds issues to a specified GitHub Project V2 when they are opened or reopened.
- **Retry Mechanism**: Retries failed webhook deliveries.

## Requirements

- Python 3.11
- pip
- Docker (optional)

## Setup

1. **Clone the repository**:
    ```sh
    git clone https://github.com/yourusername/python-webhook-add-to-github-projects.git
    cd python-webhook-add-to-github-projects
    ```

2. **Create a virtual environment**:
    ```sh
    python -m venv env
    source env/bin/activate  # On Windows use `env\Scripts\activate`
    ```

3. **Install dependencies**:
    ```sh
    pip install -r requirements.txt
    ```

4. **Set environment variables**:
    Create a `.env` file in the root directory and add the following variables:
    ```env
    GITHUB_APP_ID=your_github_app_id
    GITHUB_APP_PRIVATE_KEY=your_github_app_private_key
    GITHUB_PROJECT_ID=your_github_project_id
    GITHUB_APP_INSTALLATION_ID=your_github_app_installation_id
    GITHUB_ORG_NAME=your_github_org_name
    LOG_LEVEL=DEBUG
    ```

    - [GITHUB_APP_ID](http://_vscodecontentref_/0): The ID of your GitHub App. This is used to authenticate API requests.
    - [GITHUB_APP_PRIVATE_KEY](http://_vscodecontentref_/1): The private key of your GitHub App. This is used to sign JWT tokens for authentication.
    - [GITHUB_PROJECT_ID](http://_vscodecontentref_/2): The ID of the GitHub Project V2 where issues will be added.
    - [GITHUB_APP_INSTALLATION_ID](http://_vscodecontentref_/3): The installation ID of your GitHub App. This is used to generate installation access tokens.
    - [GITHUB_ORG_NAME](http://_vscodecontentref_/4): The name of your GitHub organization. This is used to identify the organization where the project resides.
    - [LOG_LEVEL](http://_vscodecontentref_/5): The logging level for the application. Set to `DEBUG` for detailed logs, `INFO` for general logs, `WARNING` for warnings, `ERROR` for errors, and `CRITICAL` for critical issues.


5. **Source the environment variables**:
    ```sh
    source .env
    ```

## Running the Application

1. **Start the FastAPI server**:
    ```sh
    fastapi dev
    ```

2. **Docker**:
    Alternatively, you can use Docker to run the application:
    ```sh
    docker build -t python-webhook-add-to-github-projects .
    docker run -p 8000:8000 python-webhook-add-to-github-projects
    ```

## Endpoints

- **POST /v1/**: Handles GitHub webhook events.
- **GET /health**: Health check endpoint.

## Logging

Logs are configured using the `glueops.setup_logging` module. The log level can be set using the `LOG_LEVEL` environment variable.
