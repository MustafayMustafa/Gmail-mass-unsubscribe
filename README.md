# Mass Unsubscribe Script

This script automates the process of unsubscribing from all emails (excluding blacklisted items). It works by identifying unsubscribe mailto addresses in the emails headers and constructing an appropirate unsubscribe request.

## Prerequisites

1. **Python Environment**: Ensure that Python 3.x is installed on your system.

2. **Gmail API Credentials**: Obtain the `credentials.json` file by following the instructions provided in the [Gmail API Python Quickstart Guide](https://developers.google.com/gmail/api/quickstart/python).

## Setup

**Install Required Packages**:

Navigate to the project directory and install the necessary packages using the following command:

```bash
pip install -r requirements.txt
```

## Usage

1. Prepare the blacklist.txt File:  
    Create a blacklist.txt file in the project directory to specify query filters. Each line should contain a filter to exclude certain emails from the unsubscribe process. For example:

   ```
    -label:finances
    -label:reading_list
   ```

   Note: the script by default excludes all emails older than a year.

2. Execute the script `python3 main.py`
