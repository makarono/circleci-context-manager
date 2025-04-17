# Get circle ci organization id
Find your organization ID in CircleCI Organization Settings in circle ci web ui

# CircleCI Context Manager

A command-line utility for managing CircleCI contexts and environment variables from a YAML configuration file.

## Overview

This tool automates the creation and management of CircleCI contexts and their environment variables. It allows you to define your contexts and their variables in a simple YAML file and synchronize them with your CircleCI organization.

## Features

- Create contexts that don't already exist in your CircleCI organization
- Add or update environment variables within contexts
- Support for organization-level contexts
- Dry-run mode to simulate operations without making actual changes
- Comprehensive logging

## Installation

### Prerequisites

- Python 3.6 or higher
- A CircleCI API token with appropriate permissions
- Your CircleCI Organization ID

### Installation Steps

1. Clone this repository or download the script:

```bash
git clone https://github.com/yourusername/circleci-context-manager.git
# or just download context.py
```

2. Install required dependencies:

```bash
python3 -m venv env
source env/bin/activate
uv pip install -r ./requirements.txt
```

3. Make the script executable:

```bash
chmod u+x context.py
```

## API Token Setup

The script looks for your CircleCI API token in the following locations:

1. CircleCI CLI configuration file (`~/.circleci/cli.yml`)
2. Environment variable `CI_TOKEN`

To set up your token:

### Option 1: Using CircleCI CLI config

Create or edit `~/.circleci/cli.yml`:

```yaml
token: your-circleci-api-token
```

### Option 2: Using environment variable

```bash
export CI_TOKEN=your-circleci-api-token
```

## Usage

### Basic Usage

```bash
./context.py --config your-config.yml --org-id your-organization-id
```

### With Dry Run

```bash
./context.py --config your-config.yml --org-id your-organization-id --dry-run
```

### Command Line Arguments

- `-c, --config`: Path to your YAML configuration file (required)
- `--org-id`: Your CircleCI Organization ID (required)
- `--dry-run`: Simulate operations without making actual changes
- `-h, --help`: Show help message

## Configuration File Format

Create a YAML file with the following structure:

```yaml
context-name-1:
  - VARIABLE_NAME_1: "value1"
  - VARIABLE_NAME_2: "value2"

context-name-2:
  - DATABASE_URL: "postgres://user:pass@localhost:5432/db"
  - API_KEY: "secret-key-value"
```

Each context is defined as a top-level key, with a list of environment variables as its value. Each environment variable is represented as a single key-value pair.

## Examples

### Example Configuration File

```yaml
# contexts.yml
production:
  - DATABASE_URL: "postgres://user:pass@prod-db:5432/myapp"
  - API_KEY: "prod-api-key-12345"
  - DEBUG: "false"

staging:
  - DATABASE_URL: "postgres://user:pass@staging-db:5432/myapp"
  - API_KEY: "staging-api-key-67890"
  - DEBUG: "true"

development:
  - DATABASE_URL: "postgres://user:pass@localhost:5432/myapp"
  - API_KEY: "dev-api-key-abcde"
  - DEBUG: "true"
```

### Running the Script

```bash
# Find your organization ID in CircleCI Organization Settings
export ORG_ID="abcd1234-5678-efgh-9012-ijklmnopqrst"

# Run with the example configuration
./context.py --config contexts.yml --org-id $ORG_ID
```

### Running in Dry Run Mode

```bash
./context.py --config contexts.yml --org-id $ORG_ID --dry-run
```

## Finding Your Organization ID

Your CircleCI Organization ID can be found in the Organization Settings page in the CircleCI web interface  under "organization settings"

## Integration with CI/CD Pipeline

You can use this script as part of your infrastructure-as-code approach:

```yaml
# .circleci/config.yml example
version: 2.1
jobs:
  update_contexts:
    docker:
      - image: cimg/python:3.9
    steps:
      - checkout
      - run:
          name: Install dependencies
          command: pip install requests pyyaml
      - run:
          name: Update CircleCI contexts
          command: |
            export CI_TOKEN=$CIRCLECI_API_TOKEN
            python ./context.py --config ./contexts.yml --org-id $ORG_ID

workflows:
  version: 2
  update_contexts:
    jobs:
      - update_contexts:
          filters:
            branches:
              only: main
```

## Troubleshooting

- Ensure your API token has the appropriate permissions
- Check that your Organization ID is correct
- Run with `--dry-run` first to validate your configuration
- Review the logs for detailed error messages

## License

[MIT License](LICENSE)