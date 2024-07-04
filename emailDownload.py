# Import necessary packages
import imaplib
import email
import os, re
import pandas as pd
from email.header import decode_header
import logging
import json
import yaml
import datetime
from email import policy
from email.parser import BytesParser
# Setup basic configuration for logging
# This configuration logs informational and more severe messages with timestamps and severity level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



# Function to load credentials from a YAML file
def load_credentials(filepath):
    """
    Load user credentials from a YAML file for email login.
    
    Parameters:
        filepath (str): The path to the YAML file containing the credentials.
        
    Returns:
        tuple: Returns a tuple containing the username and password if successful.
        
    Raises:
        FileNotFoundError: If the YAML file cannot be found.
        ValueError: If credentials are not correctly formatted or are missing.
        yaml.YAMLError: If there is an error parsing the YAML.
    """
    try:
        with open(filepath, 'r') as file:
            content = file.read()
            credentials = yaml.load(content, Loader=yaml.FullLoader)
            user = credentials.get('user')
            password = credentials.get('password')
            
            if not user or not password:
                logging.error("User or password missing in the provided YAML file.")
                raise ValueError("Credentials not found or incomplete in yaml file.")
            return user, password
    except FileNotFoundError:
        logging.error("The specified YAML file was not found: {}".format(filepath))
        raise
    except yaml.YAMLError as e:
        logging.error("Error parsing YAML file: {}".format(e))
        raise



# Function to connect to Gmail's IMAP server
def connect_to_gmail_imap(user, password):
    """
    Connect to the Gmail IMAP server and log in using the provided credentials.
    
    Parameters:
        user (str): The username (email address) for Gmail.
        password (str): The password for the Gmail account.
        
    Returns:
        IMAP4_SSL: An imaplib IMAP4_SSL object with the 'Inbox' selected.
        
    Raises:
        imaplib.IMAP4.error: If there are issues during the login or selecting the inbox.
        Exception: For handling other unexpected errors.
    """
    imap_url = 'imap.gmail.com'
    try:
        my_mail = imaplib.IMAP4_SSL(imap_url)
        my_mail.login(user, password)
        my_mail.select('Inbox') #my_mail.select('All-Daily-read')
        logging.info("Connected to Gmail and selected Inbox successfully.")
        return my_mail
    except imaplib.IMAP4.error as e:
        logging.error("Error during IMAP login or Inbox selection: {}".format(e))
        raise
    except Exception as e:
        logging.error("Unexpected error: {}".format(e))
        raise


def get_emails_from_last_24h(mail):
    """
    Retrieve email data and metadata from the last 24 hours.
    
    Parameters:
        mail (imaplib.IMAP4_SSL): An authenticated IMAP4_SSL object connected to Gmail.
        
    Returns:
        list: A list of dictionaries containing email data and metadata from the last 24 hours.
        
    Raises:
        imaplib.IMAP4.error: If there are issues during the search or fetching of emails.
        Exception: For handling other unexpected errors.
    """
    try:
        # Calculate the date for 24 hours ago
        date_format = "%d-%b-%Y"
        now = datetime.datetime.now()
        since_date = (now - datetime.timedelta(days=1)).strftime(date_format)
        before_date = now.strftime(date_format)

        print("Since Date: ", since_date, "\n Before Date: ", before_date, )

        # Search for emails from the last 24 hours
        result, data = mail.search(None, '(SINCE "{}" BEFORE "{}")'.format(since_date, before_date))
        
        if result == 'OK':
            email_list = []
            for num in data[0].split():
                result, data = mail.fetch(num, '(RFC822)')
                if result == 'OK':
                    raw_email = data[0][1]
                    email_message = BytesParser(policy=policy.default).parsebytes(raw_email)

                    # Extract email metadata
                    email_data = {
                        'subject': email_message['subject'],
                        'from': email_message['from'],
                        'to': email_message['to'],
                        'date': email_message['date'],
                        'body': get_email_body(email_message)
                    }
                    email_list.append(email_data)

            logging.info("Retrieved email data from the last 24 hours.")
            return email_list
        else:
            logging.error("Error during email search: {}".format(data))
            raise imaplib.IMAP4.error("Error during email search")
    except imaplib.IMAP4.error as e:
        logging.error("Error during email search or fetching: {}".format(e))
        raise
    except Exception as e:
        logging.error("Unexpected error: {}".format(e))
        raise

def get_email_body(email_message):
    """
    Get the body of the email message.
    
    Parameters:
        email_message (email.message.Message): An email message object.
        
    Returns:
        str: The body of the email message.
    """
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                return part.get_payload(decode=True).decode()  # decode
    else:
        return email_message.get_payload(decode=True).decode()  # decode

    return ""

def clean_text(text):
    """
    Clean the email content.
    
    Parameters:
        text (str): The email content.
        
    Returns:
        str: The cleaned email content.
    """
    # Remove HTML tags
    text = re.sub(r'<.*?>', '', text)
    # Remove URLs
    text = re.sub(r'http\S+|www.\S+', '', text)
    # Remove special characters and multiple spaces
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'&\w+;', '', text)
    return text


def main():
    """
    Main function to execute the program.
    
    This function handles the sequence of operations starting from loading credentials, 
    connecting to the Gmail IMAP server, loading a list of email addresses from a file, 
    marking emails for deletion based on those addresses, and finally cleaning up the IMAP session.
    
    The function uses a structured exception handling approach to manage errors that 
    might occur during the loading of credentials or IMAP operations.
    """
    # Path to the YAML file containing credentials for the Gmail account.
    credentials_path = 'credentials.yaml'
    
    try:
        # Attempt to load credentials from the specified YAML file.
        user, password = load_credentials(credentials_path)
    except Exception as e:
        # Handle any exceptions that occur during credential loading and exit the program.
        print("Failed to load credentials: {}".format(e))
        return  # Exit the function if credentials can't be loaded.

    # Assuming credentials are loaded successfully, establish an IMAP connection.
    try:
        mail = connect_to_gmail_imap(user, password)
    except Exception as e:
        # Handle possible exceptions during the connection to the IMAP server.
        print("Failed to connect to Gmail IMAP: {}".format(e))
        return  # Exit the function if the connection can't be established.

    #print the subject of the emails from the last 24 hours
    try:
        # Retrieve email data and metadata from the last 24 hours.
        emails = get_emails_from_last_24h(mail)
        #for email in emails:
            #print(email)
    except Exception as e:
        # Handle possible exceptions during the email retrieval process.
        print("Failed to retrieve emails: {}".format(e))
        return  # Exit the function if emails can't be retrieved
    
    
    # Always execute cleanup regardless of earlier errors.
    finally:
        # Clean up IMAP session: mark emails for deletion, close connection, and logout.
        try:
            mail.expunge()  # Permanently remove emails marked for deletion.
            mail.close()    # Close the currently selected mailbox.
            mail.logout()   # Logout from the server.
        except Exception as e:
            print("Failed during cleanup of IMAP session: {}".format(e))

if __name__ == "__main__":
    main()