# gRPC MCP SDK - Project Structure

This document outlines the complete project structure for the gRPC MCP SDK.

## Directory Structure

```
grpc-mcp-sdk/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI/CD
├── grpc_mcp_sdk/                  # Main package
│   ├── __init__.py               # Package initialization and exports
│   ├── py.typed                  # Type hints marker
│   ├── auth/                     # Authentication & authorization
│   │   ├── __init__.py
│   │   ├── base.py              # Base auth classes
│   │   ├── token_auth.py        # Token authentication
│   │   ├── api_key_auth.py      # API key authentication
│   │   ├── jwt_auth.py          # JWT authentication
│   │   ├── decorators.py        # Auth decorators
│   │   └── middleware.py        # Auth middleware
│   ├── core/                     # Core functionality
│   │   ├── __init__.py
│   │   ├── client.py            # gRPC client
│   │   ├── decorators.py        # Tool decorators
│   │   ├── registry.py          # Tool registry
│   │   ├── server.py            # gRPC server
│   │   └── types.py             # Core types
│   ├── logging/                  # Logging & monitoring
│   │   ├── __init__.py
│   │   └── logger.py            # Advanced logging
│   ├── proto/                    # Protocol buffers
│   │   ├── __init__.py
│   │   ├── mcp.proto            # Protocol definitions
│   │   ├── mcp_pb2.py           # Generated protobuf
│   │   └── mcp_pb2_grpc.py      # Generated gRPC
│   ├── security/                 # Security features
│   │   ├── __init__.py
│   │   ├── input_sanitizer.py   # Input sanitization
│   │   ├── rate_limiter.py      # Rate limiting
│   │   └── security_middleware.py # Security middleware
│   └── utils/                    # Utilities
│       ├── __init__.py
│       ├── errors.py            # Error definitions
│       └── validation.py        # Input validation
├── examples/                     # Example implementations
│   ├── authenticated_client.py   # Auth client example
│   ├── authenticated_server.py   # Auth server example
│   ├── basic_server.py          # Basic server example
│   ├── client_example.py        # Client example
│   └── secure_server.py         # Secure server example
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── conftest.py              # Test configuration
│   └── test_basic.py            # Basic tests
├── .gitignore                    # Git ignore rules
├── CONTRIBUTING.md               # Contribution guidelines
├── LICENSE                       # MIT license
├── MANIFEST.in                   # Package manifest
├── PROJECT_STRUCTURE.md          # This file
├── QUICKSTART.md                 # Quick start guide
├── README.md                     # Project documentation
├── pyproject.toml                # Project configuration
├── requirements.txt              # Dependencies
└── setup.py                      # Package setup
```

## Key Components

### Core Package (`grpc_mcp_sdk/`)

- **`__init__.py`**: Main package exports and CLI entry point
- **`py.typed`**: Type hints marker for mypy compatibility

### Authentication (`auth/`)

- **`base.py`**: Abstract base classes for authentication
- **`token_auth.py`**: Token-based authentication
- **`api_key_auth.py`**: API key authentication
- **`jwt_auth.py`**: JWT authentication with signing/verification
- **`decorators.py`**: Authentication decorators for tools
- **`middleware.py`**: gRPC authentication middleware

### Core Functionality (`core/`)

- **`server.py`**: Main gRPC server implementation
- **`client.py`**: gRPC client for connecting to servers
- **`registry.py`**: Tool registry with rate limiting
- **`decorators.py`**: Tool decorators (@mcp_tool, @streaming_tool)
- **`types.py`**: Core types and data structures

### Protocol Buffers (`proto/`)

- **`mcp.proto`**: Protocol buffer definitions
- **`mcp_pb2.py`**: Generated Python protobuf code
- **`mcp_pb2_grpc.py`**: Generated gRPC service code

### Security (`security/`)

- **`rate_limiter.py`**: Advanced rate limiting with token bucket
- **`input_sanitizer.py`**: Input sanitization and validation
- **`security_middleware.py`**: Comprehensive security middleware

### Utilities (`utils/`)

- **`errors.py`**: Error definitions and handling
- **`validation.py`**: Input validation utilities

### Logging (`logging/`)

- **`logger.py`**: Advanced logging with structured output

## Development Files

### Configuration

- **`setup.py`**: Package setup and distribution
- **`pyproject.toml`**: Modern Python project configuration
- **`requirements.txt`**: Runtime dependencies
- **`MANIFEST.in`**: Package manifest for distribution

### Documentation

- **`README.md`**: Main project documentation
- **`QUICKSTART.md`**: Quick start guide
- **`CONTRIBUTING.md`**: Contribution guidelines
- **`PROJECT_STRUCTURE.md`**: This file

### CI/CD

- **`.github/workflows/ci.yml`**: GitHub Actions workflow
- **`.gitignore`**: Git ignore rules

### Examples

- **`basic_server.py`**: Basic MCP server
- **`authenticated_server.py`**: Server with authentication
- **`secure_server.py`**: Production-ready secure server
- **`client_example.py`**: Client usage examples
- **`authenticated_client.py`**: Client with authentication

### Testing

- **`tests/`**: Test suite with pytest
- **`conftest.py`**: Test configuration
- **`test_basic.py`**: Basic functionality tests

## Key Features Implemented

### ✅ Core Features

1. **gRPC Server & Client**: High-performance Protocol Buffer communication
2. **Tool System**: Easy tool creation with decorators
3. **Streaming Support**: Real-time streaming tools
4. **Type Safety**: Full type hints and validation

### ✅ Security Features

1. **Authentication**: Token, API key, and JWT authentication
2. **Authorization**: Role-based permissions
3. **Rate Limiting**: Token bucket and sliding window algorithms
4. **Input Sanitization**: XSS, SQL injection, and command injection protection

### ✅ Production Features

1. **Comprehensive Logging**: Structured logging with audit trails
2. **Error Handling**: Robust error management
3. **Performance Optimization**: Connection pooling and efficient serialization
4. **Monitoring**: Health checks and metrics

### ✅ Developer Experience

1. **Simple API**: Easy-to-use decorators
2. **Comprehensive Examples**: Real-world usage examples
3. **Documentation**: Clear guides and API documentation
4. **Testing**: Test suite and CI/CD pipeline

## Usage Examples

### Basic Tool

```python
from grpc_mcp_sdk import mcp_tool, MCPToolResult

@mcp_tool(description="Calculate square")
def square(x: float) -> MCPToolResult:
    return MCPToolResult().add_text(f"{x}² = {x*x}")
```

### Authenticated Tool

```python
from grpc_mcp_sdk import requires_auth

@mcp_tool(description="Secure operation")
@requires_auth()
def secure_operation():
    return MCPToolResult().add_text("Authenticated!")
```

### Streaming Tool

```python
from grpc_mcp_sdk import streaming_tool

@streaming_tool(description="Real-time counter")
async def counter(n: int = 10):
    for i in range(n):
        yield f"Count: {i}"
```

## Next Steps

The project is production-ready with core functionality. Future enhancements could include:

- CLI tools for project scaffolding
- Advanced monitoring and observability
- A2A (Agent-to-Agent) protocol extensions
- Docker and Kubernetes deployment configurations
- Additional authentication methods
- Performance benchmarking and optimization

This structure provides a solid foundation for a high-performance, secure, and production-ready gRPC MCP SDK.