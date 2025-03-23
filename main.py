from fastapi import FastAPI, Query, HTTPException, Depends, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader, APIKey
from mta_data.subway import get_service, get_union_square_trains, get_times_square_trains, get_station_trains
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import uuid
from fastapi.responses import JSONResponse

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("api.log")
    ]
)
logger = logging.getLogger(__name__)

# Get API key from environment
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable is not set")

# Define models for our API
class Station(BaseModel):
    id: str
    name: str
    borough: str
    lines: List[str]
    description: Optional[str] = None

# Error response model
class ErrorResponse(BaseModel):
    detail: str

# Initial station data
STATIONS = {
    "union-square": Station(
        id="union-square",
        name="Union Square",
        borough="Manhattan",
        lines=["4", "5", "6", "N", "Q", "R", "W", "L"],
        description="Major transfer point connecting the 4/5/6, N/Q/R/W, and L lines"
    ),
    # ... [rest of the stations] ...
    "times-square-42nd": Station(
        id="times-square-42nd",
        name="Times Square-42nd Street",
        borough="Manhattan",
        lines=["1", "2", "3", "7", "N", "Q", "R", "W", "S"],
        description="Major transit hub in Midtown, connecting multiple lines with Port Authority Bus Terminal"
    ),
    "grand-central-42nd": Station(
        id="grand-central-42nd",
        name="Grand Central-42nd Street",
        borough="Manhattan",
        lines=["4", "5", "6", "7", "S"],
        description="Major transit hub connected to Grand Central Terminal with Metro-North Railroad connections"
    ),
    "herald-square-34th": Station(
        id="herald-square-34th",
        name="34th Street-Herald Square",
        borough="Manhattan",
        lines=["B", "D", "F", "M", "N", "Q", "R", "W"],
        description="Major shopping district station near Macy's and the Empire State Building"
    ),
    "penn-station-34th": Station(
        id="penn-station-34th",
        name="34th Street-Penn Station",
        borough="Manhattan",
        lines=["1", "2", "3", "A", "C", "E"],
        description="Station connected to Penn Station with Amtrak, LIRR, and NJ Transit connections"
    ),
    # ... [rest of the stations] ...
}

# Map FastAPI station IDs to config station IDs
STATION_ID_MAPPING = {
    "union-square": "union_square",
    "times-square-42nd": "times_square",
    "grand-central-42nd": "grand_central",
    "herald-square-34th": "herald_square",
    "penn-station-34th": "penn_station",
    # Add more mappings as needed
}

# Map of station data fetch functions
STATION_DATA_FUNCTIONS = {
    "union-square": get_union_square_trains,
    "times-square-42nd": get_times_square_trains,
    # Other stations will use the generic function
}

# Request ID middleware for tracking requests
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Add request ID to logger context
        logger_context = {"request_id": request_id}
        
        # Log the incoming request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra=logger_context
        )
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Log the completed request
            process_time = time.time() - start_time
            logger.info(
                f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {process_time:.3f}s",
                extra=logger_context
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
            
        except Exception as e:
            # Log any unhandled exceptions
            logger.exception(
                f"Request failed: {request.method} {request.url.path} - Error: {str(e)}",
                extra=logger_context
            )
            raise

# API Key security scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# API Key dependency
async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key header is missing",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key_header

# Create FastAPI app with metadata
app = FastAPI(
    title="NYC MTA Station API",
    description="API for fetching train arrival information at NYC subway stations",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    }
)

# Add middlewares
app.add_middleware(RequestIdMiddleware)

# Add CORS middleware with more restrictive settings for production
app.add_middleware(
    CORSMiddleware,
    #allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),  # Comma-separated origins from env
    allow_origins=["*"],  # Comma-separated origins from env
    allow_credentials=True,
    allow_methods=["GET"],  # Restrict to only necessary methods
    allow_headers=["*"],
)

# Error handler for uncaught exceptions
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

# Root endpoint
@app.get("/", tags=["Info"])
async def root():
    return {
        "message": "Welcome to the NYC MTA Station API", 
        "documentation": "/api/docs",
        "endpoints": [
            "/api/stations",
            "/api/stations/{station_id}",
            "/api/stations/{station_id}/trains"
        ],
        "version": app.version
    }

# Health check endpoint
@app.get("/api/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns a 200 OK response if the service is healthy.
    """
    # In a more complex app, you might check database connections, cache, etc.
    return {"status": "healthy", "version": app.version}

# Get all stations
@app.get(
    "/api/stations", 
    response_model=List[Station],
    tags=["Stations"],
    summary="Get all stations",
    response_description="List of all subway stations"
)
async def get_stations(api_key: APIKey = Depends(get_api_key)):
    """
    Get a list of all available stations.
    
    Returns a list of station objects with metadata.
    
    Authentication required:
    - API Key must be provided in the X-API-Key header
    """
    return list(STATIONS.values())

# Get single station
@app.get(
    "/api/stations/{station_id}",
    response_model=Station,
    tags=["Stations"],
    summary="Get station details",
    response_description="Details for a specific station",
    responses={404: {"model": ErrorResponse}}
)
async def get_station(
    station_id: str,
    api_key: APIKey = Depends(get_api_key)
):
    """
    Get information about a specific station.
    
    Path parameter:
    - station_id: The ID of the station
    
    Authentication required:
    - API Key must be provided in the X-API-Key header
    """
    if station_id not in STATIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Station '{station_id}' not found"
        )
    
    return STATIONS[station_id]

# Get station train arrivals
@app.get(
    "/api/stations/{station_id}/trains",
    tags=["Trains"],
    summary="Get train arrivals",
    response_description="Upcoming train arrivals at the specified station",
    responses={
        404: {"model": ErrorResponse},
        501: {"model": ErrorResponse}
    }
)
async def station_trains(
    station_id: str,
    line: Optional[str] = Query(None, description="Filter by line group: 456, nqrw, l, etc."),
    api_key: APIKey = Depends(get_api_key)
):
    """
    Get upcoming train arrivals at the specified station.
    
    Path parameter:
    - station_id: The ID of the station
    
    Query parameter:
    - line: Optional filter by line group (456, nqrw, or l)
    
    Authentication required:
    - API Key must be provided in the X-API-Key header
    """
    # Check if station exists
    if station_id not in STATIONS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Station '{station_id}' not found"
        )
    
    try:
        # Get train data for the station
        if station_id in STATION_DATA_FUNCTIONS:
            # Use dedicated function if available
            result = STATION_DATA_FUNCTIONS[station_id]()
        elif station_id in STATION_ID_MAPPING:
            # Use generic function with mapped ID
            config_station_id = STATION_ID_MAPPING[station_id]
            result = get_station_trains(config_station_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED, 
                detail=f"Train data for station '{station_id}' is not yet implemented"
            )
        
        # Filter by line if requested
        if line and line in result["lines"]:
            filtered_result = {
                "station": result["station"],
                "timestamp": result["timestamp"],
                "formatted_time": result["formatted_time"],
                "lines": {line: result["lines"][line]},
            }
            
            # Filter all_trains to only include specified line
            if line == "456":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] in ["4", "5", "6"]]
            elif line == "nqrw":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] in ["N", "Q", "R", "W"]]
            elif line == "l":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] == "L"]
            elif line == "123":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] in ["1", "2", "3"]]
            elif line == "ace":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] in ["A", "C", "E"]]
            elif line == "bdfm":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] in ["B", "D", "F", "M"]]
            elif line == "7":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] == "7"]
            elif line == "g":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] == "G"]
            elif line == "jz":
                filtered_result["all_trains"] = [t for t in result["all_trains"] if t["route_id"] in ["J", "Z"]]
                
            return filtered_result
        
        return result
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error
        logger.error(f"Error fetching train data for station {station_id}: {str(e)}")
        # Return a friendly error message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching train arrival data. Please try again later."
        )

# Run with Uvicorn when script is executed directly
if __name__ == "__main__":
    import uvicorn
    # Use environment variables for host and port
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    # Run with production settings
    uvicorn.run(
        "app:app",  # Assuming this file is named app.py
        host=host,
        port=port,
        workers=int(os.getenv("WORKERS", "4")),  # Number of worker processes
        log_level="info",
        proxy_headers=True,  # Trust X-Forwarded-* headers
        forwarded_allow_ips="*"  # Allow all IPs for X-Forwarded-* headers
    )