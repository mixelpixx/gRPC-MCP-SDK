# Contributing to gRPC MCP SDK

Thank you for your interest in contributing to the gRPC MCP SDK! This guide will help you get started.

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/grpc-mcp-sdk.git
   cd grpc-mcp-sdk
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Generate protobuf files**:
   ```bash
   python -m grpc_tools.protoc --python_out=grpc_mcp_sdk/proto --grpc_python_out=grpc_mcp_sdk/proto --proto_path=grpc_mcp_sdk/proto grpc_mcp_sdk/proto/mcp.proto
   
   # Fix import in generated file
   sed -i 's/import mcp_pb2/from . import mcp_pb2/' grpc_mcp_sdk/proto/mcp_pb2_grpc.py
   ```

5. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   ```

## Code Standards

### Code Style

- **Python**: Follow PEP 8 style guide
- **Line length**: Maximum 127 characters
- **Formatting**: Use `black` for code formatting
- **Imports**: Use `isort` for import sorting
- **Type hints**: Add type hints to all public functions
- **Docstrings**: Use Google-style docstrings

### Code Quality

- **Linting**: Use `flake8` for linting
- **Type checking**: Use `mypy` for static type checking
- **Security**: Use `bandit` for security analysis
- **Testing**: Write comprehensive tests with `pytest`

### Running Quality Checks

```bash
# Format code
black grpc_mcp_sdk/
isort grpc_mcp_sdk/

# Lint code
flake8 grpc_mcp_sdk/

# Type check
mypy grpc_mcp_sdk/

# Security check
bandit -r grpc_mcp_sdk/

# Run tests
pytest tests/ -v --cov=grpc_mcp_sdk
```

## Contributing Guidelines

### 1. Issues

- **Bug reports**: Use the bug report template
- **Feature requests**: Use the feature request template
- **Questions**: Use GitHub Discussions

### 2. Pull Requests

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make your changes** following the code standards
4. **Add tests** for new functionality
5. **Update documentation** if needed
6. **Commit your changes**: Use conventional commit messages
7. **Push to your fork**: `git push origin feature/your-feature`
8. **Create a pull request** with a clear description

### 3. Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
```
feat(auth): add JWT authentication support
fix(server): handle connection errors gracefully
docs(readme): update installation instructions
```

## Development Workflow

### Adding New Features

1. **Design**: Discuss the feature in an issue first
2. **Implement**: Follow the existing code patterns
3. **Test**: Add comprehensive tests
4. **Document**: Update README and docstrings
5. **Examples**: Add examples if applicable

### Testing

- **Unit tests**: Test individual components
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test complete workflows
- **Security tests**: Test authentication and authorization
- **Performance tests**: Test with realistic loads

### Documentation

- **Code documentation**: Comprehensive docstrings
- **API documentation**: Auto-generated from docstrings
- **User guides**: Clear examples and tutorials
- **Architecture docs**: Design decisions and patterns

## Areas for Contribution

### High Priority

- **Performance optimization**: Improve gRPC performance
- **Security enhancements**: Additional authentication methods
- **Error handling**: Better error messages and recovery
- **Testing**: Increase test coverage

### Medium Priority

- **CLI tools**: Project scaffolding and management
- **Monitoring**: Metrics and observability
- **Documentation**: Tutorials and guides
- **Examples**: Real-world use cases

### Low Priority

- **A2A extensions**: Agent-to-agent communication
- **Deployment**: Docker and Kubernetes support
- **Integrations**: Third-party service connectors
- **Performance**: Benchmarking and profiling

## Community

- **GitHub Discussions**: For questions and general discussion
- **Issues**: For bug reports and feature requests
- **Pull Requests**: For code contributions
- **Code of Conduct**: Be respectful and inclusive

## Release Process

1. **Version bump**: Update version in `setup.py` and `__init__.py`
2. **Changelog**: Update CHANGELOG.md
3. **Tests**: Ensure all tests pass
4. **Documentation**: Update documentation
5. **Tag**: Create a git tag for the release
6. **PyPI**: Publish to PyPI

## Getting Help

- **Documentation**: Check the README and docs
- **Examples**: Look at the examples directory
- **Issues**: Search existing issues
- **Discussions**: Ask questions in GitHub Discussions
- **Contact**: Reach out to maintainers

Thank you for contributing to gRPC MCP SDK! 🚀