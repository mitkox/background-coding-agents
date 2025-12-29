#!/bin/bash
# Setup script for Background Coding Agents - Manufacturing Example

echo "========================================"
echo "Background Coding Agents Setup"
echo "Based on Spotify's Engineering Blogs"
echo "========================================"
echo ""

# Check Python version
python3 --version || {
    echo "Error: Python 3.8+ required"
    exit 1
}

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || . venv/Scripts/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "Creating directory structure..."
mkdir -p logs
mkdir -p outputs
mkdir -p fleet-manager/migrations

echo ""
echo "✓ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Review the documentation:"
echo "   - cat GUIDE.md                           # Complete guide"
echo "   - cat docs/implementation-roadmap.md     # Phased rollout plan"
echo ""
echo "2. Explore examples:"
echo "   - cat examples/safety_interlock_update/README.md"
echo ""
echo "3. Understand the architecture:"
echo "   - cat docs/comparison-spotify-vs-manufacturing.md"
echo ""
echo "4. Try a dry-run simulation:"
echo "   - cd fleet-manager"
echo "   - python cli.py --help"
echo ""
echo "========================================"
