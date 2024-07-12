## README

# Email Fetcher and Summarizer

This project retrieves email data and metadata from the last 24 hours from a Gmail inbox and processes the emails to extract relevant information. It uses Python's `imaplib` to connect to the Gmail server, fetch emails, and handle different email encodings. 

## Features
- Fetch emails from the last 24 hours.
- Extract subject, sender, recipient, date, and body of each email.
- Handle different email encodings and multipart emails.
- Log the process for easy debugging and monitoring.

## Prerequisites

Before you begin, ensure you have the following installed on your local machine:
- Python 3.7 or higher
- `pydub` library
- `openai` library
- `ffmpeg` installed and configured

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/your-username/email-fetcher.git
    cd email-fetcher
    ```

2. Set up a virtual environment:
    ```sh
    python3 -m venv venv
    source venv/bin/activate   # On Windows, use `venv\Scripts\activate`
    ```

3. Install the required libraries:
    ```sh
    pip install -r requirements.txt
    ```

4. Ensure `ffmpeg` is installed and available in your PATH. You can download it from [here](https://ffmpeg.org/download.html).

5. Create an OpenAI key and store it in the venv as an environment variable
   ```
   export OPENAI_API_KEY='your-openai-api-key'
   ```

7. Create a `credentials.yaml` file in the root directory of the project to store your Gmail credentials securely:
    ```yaml
      user: your-email@gmail.com
      password: your-app-password
    ```

8. For creating an app password, refer to the instructions provided [here](https://knowledge.workspace.google.com/kb/how-to-create-app-passwords-000009237).

## Usage

1. Run the script to fetch and process emails from the last 24 hours:
    ```sh
    python3 emailSummarizer.py
    ```
    
### Logging

The script uses Python's `logging` module to log debug and error messages. This helps in tracking the flow of execution and diagnosing issues.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Make your changes.
4. Commit your changes (`git commit -m 'Add some feature'`).
5. Push to the branch (`git push origin feature-branch`).
6. Open a pull request.

## Contact

For any questions or suggestions, please open an issue or contact nbalamurugan@checkbook.io
