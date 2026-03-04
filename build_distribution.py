#!/usr/bin/env python3
"""
Build script for gRPC MCP SDK distribution files.

This script automates the process of building wheel and source distribution files.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and handle errors."""
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        if e.stdout:
            print(f"Stdout: {e.stdout}")
        if e.stderr:
            print(f"Stderr: {e.stderr}")
        return False


def generate_protobuf_files():
    """Generate protobuf files from .proto definitions."""
    print("\n=== Generating Protocol Buffer Files ===")
    
    proto_dir = Path("grpc_mcp_sdk/proto")
    proto_file = proto_dir / "mcp.proto"
    
    if not proto_file.exists():
        print(f"Error: {proto_file} not found!")
        return False
    
    # Generate protobuf files
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        f"--proto_path={proto_dir}",
        str(proto_file)
    ]
    
    if not run_command(cmd, "Generating protobuf files"):
        return False
    
    # Fix import in generated gRPC file
    grpc_file = proto_dir / "mcp_pb2_grpc.py"
    if grpc_file.exists():
        try:
            content = grpc_file.read_text()
            content = content.replace("import mcp_pb2", "from . import mcp_pb2")
            grpc_file.write_text(content)
            print("Fixed import in mcp_pb2_grpc.py")
        except Exception as e:
            print(f"Warning: Could not fix import in {grpc_file}: {e}")
    
    return True


def clean_build_artifacts():
    """Clean previous build artifacts."""
    print("\n=== Cleaning Build Artifacts ===")
    
    import shutil
    
    dirs_to_clean = [
        "build",
        "dist",
        "grpc_mcp_sdk.egg-info",
        "*.egg-info"
    ]
    
    for dir_pattern in dirs_to_clean:
        if "*" in dir_pattern:
            # Handle glob patterns
            from glob import glob
            for path in glob(dir_pattern):
                if os.path.isdir(path):
                    shutil.rmtree(path)
                    print(f"Removed: {path}")
        else:
            if os.path.exists(dir_pattern):
                if os.path.isdir(dir_pattern):
                    shutil.rmtree(dir_pattern)
                else:
                    os.remove(dir_pattern)
                print(f"Removed: {dir_pattern}")


def build_distributions():
    """Build wheel and source distributions."""
    print("\n=== Building Distributions ===")
    
    # Use modern build system
    cmd = [sys.executable, "-m", "build"]
    
    if not run_command(cmd, "Building wheel and source distribution"):
        print("Modern build failed, trying setuptools directly...")
        
        # Fallback to setuptools
        cmd = [sys.executable, "setup.py", "sdist", "bdist_wheel"]
        if not run_command(cmd, "Building with setuptools"):
            return False
    
    return True


def verify_distributions():
    """Verify the built distributions."""
    print("\n=== Verifying Distributions ===")
    
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("Error: dist/ directory not found!")
        return False
    
    wheel_files = list(dist_dir.glob("*.whl"))
    tar_files = list(dist_dir.glob("*.tar.gz"))
    
    if not wheel_files:
        print("Error: No wheel files found!")
        return False
    
    if not tar_files:
        print("Error: No source distribution files found!")
        return False
    
    print("Built distributions:")
    for file in wheel_files + tar_files:
        size_mb = file.stat().st_size / (1024 * 1024)
        print(f"  - {file.name} ({size_mb:.2f} MB)")
    
    # Verify wheel contents
    wheel_file = wheel_files[0]
    cmd = [sys.executable, "-m", "zipfile", "-l", str(wheel_file)]
    run_command(cmd, f"Listing contents of {wheel_file.name}")
    
    return True


def check_distribution_quality():
    """Check distribution quality with twine."""
    print("\n=== Checking Distribution Quality ===")
    
    try:
        # Check if twine is available
        subprocess.run([sys.executable, "-m", "twine", "--version"], 
                      check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Twine not available, skipping quality check")
        print("Install with: pip install twine")
        return True
    
    cmd = [sys.executable, "-m", "twine", "check", "dist/*"]
    return run_command(cmd, "Checking distribution quality")


def main():
    """Main build process."""
    print("🚀 gRPC MCP SDK Distribution Builder")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("setup.py").exists():
        print("Error: setup.py not found! Are you in the project root?")
        sys.exit(1)
    
    if not Path("grpc_mcp_sdk").exists():
        print("Error: grpc_mcp_sdk/ directory not found!")
        sys.exit(1)
    
    steps = [
        ("Generate protobuf files", generate_protobuf_files),
        ("Clean build artifacts", clean_build_artifacts),
        ("Build distributions", build_distributions),
        ("Verify distributions", verify_distributions),
        ("Check distribution quality", check_distribution_quality),
    ]
    
    for step_name, step_func in steps:
        print(f"\n{'='*20} {step_name} {'='*20}")
        if not step_func():
            print(f"❌ Failed: {step_name}")
            sys.exit(1)
        print(f"✅ Completed: {step_name}")
    
    print("\n" + "="*50)
    print("🎉 Distribution build completed successfully!")
    print("\nDistribution files created:")
    
    dist_dir = Path("dist")
    for file in dist_dir.glob("*"):
        print(f"  📦 {file.name}")
    
    print("\n📝 Next steps:")
    print("  1. Test the wheel: pip install dist/*.whl")
    print("  2. Upload to PyPI: twine upload dist/*")
    print("  3. Upload to GitHub releases")


if __name__ == "__main__":
    main()