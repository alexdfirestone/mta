# NYC MTA Station API

A FastAPI application that provides real-time train arrival information for NYC subway stations.

## Features

- Get information about NYC subway stations
- Real-time train arrival data for supported stations
- Filter train arrivals by line
- API key authentication
- Request tracking with unique request IDs
- Comprehensive error handling
- Health check endpoint for monitoring
- CORS protection for production environments

## Getting Started

### Prerequisites

- Python 3.7+
- pip (Python package installer)
- MTA API key (for real-time train data)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/nyc-mta-station-api.git
cd nyc-mta-station-api
```

2. Create a virtual environment:

```bash
python -m venv venv
```

3. Activate the virtual environment:

- On Windows:
```bash
venv\Scripts\activate
```

- On macOS/Linux:
```bash
source venv/bin/activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Create a `.env` file in the project root with the following variables:

```
API_KEY=your_api_key_here
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
HOST=0.0.0.0
PORT=8000
WORKERS=4
```

### Running the Application

#### Development Mode

```bash
uvicorn app:app --reload
```

#### Production Mode

```bash
python app.py
```

or

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Documentation

Once the server is running, you can access the API documentation at:

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## API Endpoints

### Base URL

All endpoints are prefixed with `/api` except the root endpoint.

### Available Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| GET | `/` | Welcome message and API information | No |
| GET | `/api/health` | Health check endpoint | No |
| GET | `/api/stations` | Get all stations | API Key |
| GET | `/api/stations/{station_id}` | Get details for a specific station | API Key |
| GET | `/api/stations/{station_id}/trains` | Get real-time train arrivals | API Key |

### Authentication

The API uses API key authentication. Include your API key in the `X-API-Key` header:

```
X-API-Key: your_api_key_here
```

## Example Requests

### Get All Stations

```bash
curl -X 'GET' \
  'http://localhost:8000/api/stations' \
  -H 'X-API-Key: your_api_key_here'
```

### Get Station Details

```bash
curl -X 'GET' \
  'http://localhost:8000/api/stations/union-square' \
  -H 'X-API-Key: your_api_key_here'
```

### Get Train Arrivals

```bash
curl -X 'GET' \
  'http://localhost:8000/api/stations/union-square/trains' \
  -H 'X-API-Key: your_api_key_here'
```

### Filter Train Arrivals by Line

```bash
curl -X 'GET' \
  'http://localhost:8000/api/stations/union-square/trains?line=456' \
  -H 'X-API-Key: your_api_key_here'
```

## Project Structure

```
nyc-mta-station-api/
├── app.py                  # Main FastAPI application
├── mta_data/               # MTA data fetching modules
│   ├── __init__.py
│   └── subway.py           # Module for subway train data
├── .env                    # Environment variables
├── requirements.txt        # Python dependencies
├── api.log                 # API logs
└── README.md               # Project documentation
```

## Adding New Stations

To add support for new stations:

1. Add the station to the `STATIONS` dictionary in `app.py`
2. Create a data fetching function in the appropriate module
3. Add the station ID and function mapping to the `STATION_DATA_FUNCTIONS` dictionary

## Dependencies

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework for building APIs
- [Uvicorn](https://www.uvicorn.org/) - ASGI server
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment variable management
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [requests](https://requests.readthedocs.io/) - HTTP client
- [gtfs-realtime-bindings](https://github.com/google/gtfs-realtime-bindings) - GTFS Realtime binding for Python
- [protobuf-to-dict](https://github.com/benhodgson/protobuf-to-dict) - Convert Protocol Buffers to Python dictionaries

## Requirements File

Create a `requirements.txt` file with the following dependencies:

```
fastapi==0.103.1
uvicorn==0.23.2
python-dotenv==1.0.0
requests==2.31.0
gtfs-realtime-bindings==1.0.0
protobuf-to-dict==0.1.0
pydantic==2.3.0
starlette==0.27.0
python-multipart==0.0.6
```

## Required MTA Dependencies

For accessing the MTA data specifically:

```bash
pip install gtfs-realtime-bindings protobuf-to-dict google-api-python-client
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| API_KEY | Authentication key for the API | (required) |
| ALLOWED_ORIGINS | Comma-separated list of allowed CORS origins | "" |
| HOST | Host address to bind the server | 0.0.0.0 |
| PORT | Port to run the server | 8000 |
| WORKERS | Number of worker processes for Uvicorn | 4 |

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- MTA for providing the GTFS Realtime API
- The FastAPI team for the excellent framework

## Disclaimer

This application is not affiliated with, endorsed by, or in any way officially connected to the MTA. This is an independent project that utilizes publicly available MTA data.
