"""Setup configuration for gRPC MCP SDK."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements
requirements = []
with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="grpc-mcp-sdk",
    version="1.0.0",
    author="gRPC MCP SDK Team",
    author_email="support@grpc-mcp-sdk.com",
    description="A modern Python framework for building high-performance MCP tools with gRPC",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/grpc-mcp-sdk/grpc-mcp-sdk",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "security": [
            "cryptography>=41.0.0",
            "pyjwt>=2.8.0",
        ],
        "monitoring": [
            "prometheus-client>=0.17.0",
            "opentelemetry-api>=1.20.0",
            "opentelemetry-sdk>=1.20.0",
        ],
        "all": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
            "cryptography>=41.0.0",
            "pyjwt>=2.8.0",
            "prometheus-client>=0.17.0",
            "opentelemetry-api>=1.20.0",
            "opentelemetry-sdk>=1.20.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "grpc-mcp=grpc_mcp_sdk:main",
        ],
    },
    include_package_data=True,
    package_data={
        "grpc_mcp_sdk": [
            "proto/*.proto",
            "py.typed",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/grpc-mcp-sdk/grpc-mcp-sdk/issues",
        "Source": "https://github.com/grpc-mcp-sdk/grpc-mcp-sdk",
        "Documentation": "https://grpc-mcp-sdk.readthedocs.io/",
    },
    keywords="grpc mcp sdk protocol-buffers ai-tools streaming authentication",
    zip_safe=False,
)