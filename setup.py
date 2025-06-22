"""
Setup script for gRPC MCP SDK
"""

from setuptools import setup, find_packages
import os

# Read README
def read_readme():
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="grpc-mcp-sdk",
    version="1.0.0",
    author="gRPC MCP SDK Team",
    author_email="contact@grpc-mcp-sdk.com",
    description="A modern Python framework for building high-performance MCP tools with gRPC",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/grpc-mcp-sdk/grpc-mcp-sdk",
    project_urls={
        "Bug Tracker": "https://github.com/grpc-mcp-sdk/grpc-mcp-sdk/issues",
        "Documentation": "https://grpc-mcp-sdk.readthedocs.io/",
        "Source Code": "https://github.com/grpc-mcp-sdk/grpc-mcp-sdk",
    },
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
        "Topic :: System :: Distributed Computing",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "docs": [
            "sphinx>=7.0.0",
            "sphinx-rtd-theme>=1.3.0",
            "sphinx-autodoc-typehints>=1.24.0",
        ],
        "monitoring": [
            "prometheus-client>=0.17.0",
            "psutil>=5.9.0",
        ],
        "security": [
            "cryptography>=41.0.0",
            "pyjwt>=2.8.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "grpc-mcp=grpc_mcp_sdk:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords=[
        "grpc",
        "mcp",
        "model-context-protocol",
        "ai",
        "tools",
        "api",
        "microservices",
        "rpc",
        "protocol-buffers",
        "streaming",
        "performance",
        "enterprise",
    ],
)