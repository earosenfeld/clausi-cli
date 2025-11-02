"""Utility functions for AI system."""

def validate_input(data):
    """Validate input data."""
    if not data:
        raise ValueError("Input cannot be empty")

    if len(data) > 10000:
        raise ValueError("Input too large")

    return True


def process_data(data):
    """Process data for AI model."""
    # Data processing logic
    validated = validate_input(data)

    if not validated:
        return None

    # Transform data
    processed = data.lower().strip()
    return processed
