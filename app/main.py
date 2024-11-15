from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager
import os
import glueops.setup_logging
import schedule
import time
import traceback

from utils.github import projects, auth, hooks

# Initialize Logger
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logger = glueops.setup_logging.configure(level=log_level)
logger.debug(f"Logger initialized with level: {log_level}")

# Environment Variables
REQUIRED_ENV_VARS = [
    "GITHUB_APP_ID",
    "GITHUB_APP_PRIVATE_KEY",
    "GITHUB_PROJECT_ID",
    "GITHUB_APP_INSTALLATION_ID"
]
OPTIONAL_ENV_VARS = {
    "GITHUB_ORG_NAME": "GlueOps",
    "LOG_LEVEL": "WARNING"
}

def get_env_variable(var_name: str, default=None):
    """Retrieve environment variable or return default if not set.
    
    Args:
        var_name (str): The name of the environment variable.
        default (Any, optional): The default value if the environment variable is not set.
    
    Returns:
        Any: The value of the environment variable or the default.
    """
    value = os.getenv(var_name, default)
    if var_name in REQUIRED_ENV_VARS:
        if value is None:
            logger.error(f"Environment variable '{var_name}' is not set.")
            raise EnvironmentError(f"Environment variable '{var_name}' is required but not set.")
        else:
            # Avoid logging sensitive information
            if var_name != "GITHUB_APP_PRIVATE_KEY":
                logger.debug(f"Environment variable '{var_name}' retrieved successfully.")
    else:
        logger.debug(f"Optional environment variable '{var_name}' set to: {value}")
    return value

# Retrieve Environment Variables
try:
    GITHUB_APP_ID = get_env_variable('GITHUB_APP_ID')
    GITHUB_APP_PRIVATE_KEY = get_env_variable('GITHUB_APP_PRIVATE_KEY')
    NUM_OF_DAYS_TO_REPROCESS_WEBHOOKS = int(get_env_variable('NUM_OF_DAYS_TO_REPROCESS_WEBHOOKS', 3))
    GITHUB_PROJECT_ID = str(get_env_variable('GITHUB_PROJECT_ID'))
    GITHUB_APP_INSTALLATION_ID = get_env_variable('GITHUB_APP_INSTALLATION_ID')
    GITHUB_ORG_NAME = get_env_variable('GITHUB_ORG_NAME', OPTIONAL_ENV_VARS['GITHUB_ORG_NAME'])
    LOG_LEVEL = get_env_variable('LOG_LEVEL', OPTIONAL_ENV_VARS['LOG_LEVEL'])
    logger.info("All required environment variables retrieved successfully.")
except EnvironmentError as env_err:
    logger.critical(f"Environment setup failed: {env_err}")
    raise

# Initialize GitHub Components
try:
    logger.debug("Initializing GitHubInstallationTokenManager...")
    github_token_manager = auth.GitHubInstallationTokenManager(
        installation_id=GITHUB_APP_INSTALLATION_ID,
        app_id=GITHUB_APP_ID,
        private_key=GITHUB_APP_PRIVATE_KEY
    )
    headers = github_token_manager.get_headers()
    logger.debug("GitHubInstallationTokenManager initialized successfully.")

    logger.debug("Fetching project node ID...")
    PROJECT_NODE_ID = projects.get_project_node_id(
        project_id=GITHUB_PROJECT_ID,
        org_name=GITHUB_ORG_NAME,
        headers=headers
    )
    logger.info(f"Project node ID '{PROJECT_NODE_ID}' retrieved successfully.")
except Exception as e:
    logger.error(f"Failed to initialize GitHub components: {e}")
    logger.debug(traceback.format_exc())
    raise

# Scheduling Function
def run_scheduled_tasks():
    """Run pending scheduled tasks in an infinite loop."""
    logger.debug("Background task for scheduled jobs started.")
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in scheduled tasks: {e}")
            logger.debug(traceback.format_exc())

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event for FastAPI application.

    - Sets up scheduled tasks.
    - Validates required environment variables.
    - Manages application startup and shutdown logs.
    """
    logger.info("Application startup initiated.")

    # Schedule retry_failed_deliveries to run daily at midnight
    schedule.every().day.at("00:00").do(
        hooks.retry_failed_deliveries,
        GITHUB_APP_ID,
        GITHUB_APP_PRIVATE_KEY,
        NUM_OF_DAYS_TO_REPROCESS_WEBHOOKS
    )
    logger.info("Scheduled 'retry_failed_deliveries' job to run daily at midnight.")
    hooks.retry_failed_deliveries(
        GITHUB_APP_ID,
        GITHUB_APP_PRIVATE_KEY,
        NUM_OF_DAYS_TO_REPROCESS_WEBHOOKS)
    # Start background task for running scheduled tasks
    background_tasks = BackgroundTasks()
    background_tasks.add_task(run_scheduled_tasks)
    logger.info("Background task for scheduled jobs added.")

    # Validate required environment variables
    missing_vars = [var for var in REQUIRED_ENV_VARS if var not in os.environ]
    if missing_vars:
        error_message = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_message)
        raise EnvironmentError(error_message)
    else:
        logger.info("All environment variables are present.")

    logger.info("Application startup complete.")
    try:
        yield
    finally:
        logger.info("Application shutdown initiated.")
        # Perform any necessary cleanup here
        logger.info("Application shutdown complete.")

# Initialize FastAPI App with Lifespan
app = FastAPI(lifespan=lifespan)
logger.debug("FastAPI application initialized with lifespan manager.")

@app.post("/v1/")
async def trigger_workflow(request: Request):
    """
    Trigger workflow based on GitHub webhook events.

    - Adds issues to a GitHub project when they are opened or reopened.
    """
    logger.debug("Received a request to /v1/ endpoint.")
    event_type = request.headers.get("x-github-event")
    logger.info(f"Webhook event type: {event_type}")

    if event_type == "issues":
        try:
            request_body = await request.json()
            logger.debug(f"Webhook payload received: {request_body}")

            action = request_body.get("action")
            issue = request_body.get("issue", {})
            node_id = issue.get("node_id")

            logger.info(f"Action: {action}, Issue Node ID: {node_id}")

            if action in ["opened", "reopened"] and node_id:
                logger.info(f"Processing action '{action}' for issue with node_id: {node_id}")
                projects.add_to_project(PROJECT_NODE_ID, node_id, headers)
                logger.info(f"Issue '{node_id}' added to project '{PROJECT_NODE_ID}'.")
                return {"message": "Issue added to project."}
            else:
                logger.info("No relevant action or missing issue/node_id in webhook payload.")
        except HTTPException as http_exc:
            logger.warning(f"HTTPException encountered: {http_exc.detail}")
            raise http_exc
        except Exception as e:
            logger.error(f"Unexpected error processing webhook: {e}")
            logger.debug(traceback.format_exc())
            raise HTTPException(status_code=500, detail="Internal Server Error")

    logger.info("Webhook event not relevant for processing.")
    return {"message": "No action taken."}

@app.get("/health")
async def health():
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    logger.debug("Health check endpoint called.")
    return {"status": "healthy"}