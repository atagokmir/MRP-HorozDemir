"""
FastAPI main application for the Horoz Demir MRP System.
Configures middleware, exception handlers, and API routes.
"""

from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger
import uvicorn

from app.config import settings
from app.exceptions import MRPException, create_http_exception
from app.api.auth import router as auth_router
from app.api.master_data import router as master_data_router
from app.api.inventory import router as inventory_router
from app.api.bom import router as bom_router
from app.api.production import router as production_router
from app.api.procurement import router as procurement_router
from app.api.reporting import router as reporting_router


# Rate limiting setup
limiter = Limiter(key_func=get_remote_address)


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    
    # Create FastAPI app with custom documentation
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
    )
    
    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Total-Count"]
    )
    
    # Add trusted host middleware for production
    if not settings.DEBUG:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS
        )
    
    return app


# Create application instance
app = create_application()


# Request/Response logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log requests and responses for debugging and monitoring."""
    start_time = datetime.now()
    
    # Generate request ID if not present
    request_id = request.headers.get("X-Request-ID", f"req_{int(start_time.timestamp() * 1000000)}")
    
    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path} | "
        f"ID: {request_id} | "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.4f}s"
        
        # Log response
        logger.info(
            f"Response: {response.status_code} | "
            f"ID: {request_id} | "
            f"Duration: {duration:.4f}s"
        )
        
        return response
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(
            f"Error: {str(e)} | "
            f"ID: {request_id} | "
            f"Duration: {duration:.4f}s"
        )
        raise


# Exception handlers
@app.exception_handler(MRPException)
async def mrp_exception_handler(request: Request, exc: MRPException):
    """Handle custom MRP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "error_code": "HTTP_ERROR",
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle FastAPI request validation errors with detailed information."""
    logger.error(f"Validation error for {request.method} {request.url}: {exc.errors()}")
    
    # Get the raw request body for debugging
    try:
        body = await request.body()
        body_str = body.decode('utf-8') if body else "Empty body"
        logger.error(f"Request body that caused validation error: {body_str}")
    except Exception as e:
        logger.error(f"Could not read request body: {e}")
        body_str = "Could not decode body"
    
    # Ensure errors are JSON serializable
    try:
        error_details = []
        for error in exc.errors():
            error_dict = {
                "type": error.get("type", "unknown"),
                "loc": list(error.get("loc", [])),
                "msg": str(error.get("msg", "Unknown error")),
                "input": str(error.get("input", "")) if error.get("input") is not None else None
            }
            error_details.append(error_dict)
    except Exception as e:
        logger.error(f"Error processing validation errors: {e}")
        error_details = [{"type": "processing_error", "msg": "Could not process validation errors"}]
    
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Validation error",
            "error_code": "REQUEST_VALIDATION_ERROR",
            "details": error_details,
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors with detailed information."""
    logger.error(f"Pydantic validation error for {request.method} {request.url}: {exc.errors()}")
    
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Data validation error",
            "error_code": "PYDANTIC_VALIDATION_ERROR",
            "details": exc.errors(),
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle value errors as validation errors."""
    logger.error(f"Value error for {request.method} {request.url}: {str(exc)}")
    
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": str(exc),
            "error_code": "VALIDATION_ERROR",
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error" if not settings.DEBUG else str(exc),
            "error_code": "INTERNAL_ERROR",
            "timestamp": datetime.now().isoformat(),
            "path": str(request.url)
        }
    )


# Health check endpoints
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with system information."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": settings.PROJECT_DESCRIPTION,
        "status": "operational",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now().isoformat(),
        "checks": {
            "api": "ok",
            "database": "ok",  # TODO: Add actual database health check
            "cache": "ok"      # TODO: Add actual Redis health check
        }
    }


@app.get("/version", tags=["System"])
async def version_info():
    """Version information endpoint."""
    return {
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "timestamp": datetime.now().isoformat()
    }


# Include API routers with /api/v1 prefix
app.include_router(
    auth_router,
    prefix="/api/v1/auth",
    tags=["Authentication"],
    responses={
        401: {"description": "Authentication failed"},
        403: {"description": "Insufficient permissions"}
    }
)

app.include_router(
    master_data_router,
    prefix="/api/v1/master-data",
    tags=["Master Data"],
    dependencies=[],  # Authentication will be handled at endpoint level
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Resource not found"}
    }
)

app.include_router(
    inventory_router,
    prefix="/api/v1/inventory",
    tags=["Inventory Management"],
    dependencies=[],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Insufficient stock or conflict"}
    }
)

app.include_router(
    bom_router,
    prefix="/api/v1/bom",
    tags=["Bill of Materials"],
    dependencies=[],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        400: {"description": "Invalid BOM or circular reference"}
    }
)

app.include_router(
    production_router,
    prefix="/api/v1/production-orders",
    tags=["Production Management"],
    dependencies=[],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Production order conflict"}
    }
)

app.include_router(
    procurement_router,
    prefix="/api/v1/procurement",
    tags=["Procurement"],
    dependencies=[],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"}
    }
)

app.include_router(
    reporting_router,
    prefix="/api/v1/reports",
    tags=["Reporting & Analytics"],
    dependencies=[],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Report generation failed"}
    }
)


# Custom OpenAPI schema
def custom_openapi():
    """Generate custom OpenAPI schema with additional metadata."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.PROJECT_DESCRIPTION,
        routes=app.routes,
    )
    
    # Add custom security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    # Add tags metadata
    openapi_schema["tags"] = [
        {
            "name": "System",
            "description": "System health and information endpoints"
        },
        {
            "name": "Authentication",
            "description": "User authentication and authorization"
        },
        {
            "name": "Master Data",
            "description": "Warehouses, products, and suppliers management"
        },
        {
            "name": "Inventory Management",
            "description": "Stock operations with FIFO allocation logic"
        },
        {
            "name": "Bill of Materials",
            "description": "BOM management with explosion and costing"
        },
        {
            "name": "Production Management",
            "description": "Production orders and manufacturing workflows"
        },
        {
            "name": "Procurement",
            "description": "Purchase orders and supplier management"
        },
        {
            "name": "Reporting & Analytics",
            "description": "Business reports and analytics"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Development server
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=settings.DEBUG
    )