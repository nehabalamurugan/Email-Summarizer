# Import necessary packages
import imaplib
import email
import os, re
import logging
import json
import yaml
import datetime
from pydub import AudioSegment
from openai import OpenAI
from email import policy
from email.parser import BytesParser
from email.header import decode_header
from langchain.chains import AnalyzeDocumentChain
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain_community.document_loaders import UnstructuredEmailLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_fixed

# Setup basic configuration for logging
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
        #my_mail.select('All-day') 
        my_mail.select('All-Daily-read')
        logging.info("Connected to Gmail and selected Inbox successfully.")
        return my_mail
    except imaplib.IMAP4.error as e:
        logging.error("Error during IMAP login or Inbox selection: {}".format(e))
        raise
    except Exception as e:
        logging.error("Unexpected error HERE: {}".format(e))
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

        print("Since Date: ", since_date, "\nBefore Date: ", before_date, )

        # Search for emails from the last 24 hours
        result, data = mail.search(None, '(SINCE "{}")'.format(before_date))
        
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
                        'body': clean_text(get_email_body(email_message))
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

def summarize_email(emails):
    """Summarize the body of each email and store the output in a text file."""
    # Attempt to summarize the email content
    # Define the prompt templates for summarization
    question_prompt_template = """
    Imagine you are the CEO of a company and you need to read through the newletters in your inbox to stay update about market trends and businesses. 
    Please provide an intelligent summary of the following text with key points that can be used to make informed decisions. Write in bullet points:
    TEXT: {text}
    SUMMARY:
    """.strip()
    question_prompt = PromptTemplate(
        template=question_prompt_template, input_variables=["text"]
    )

    refine_prompt_template = """
    Write a concise summary of the following text delimited by triple backquotes.
    Return your response in bullet points which covers the key points of the text.
    ```{text}```
    BULLET POINT SUMMARY:
    """.strip()
    refine_prompt = PromptTemplate(
        template=refine_prompt_template, input_variables=["text"]
    )

    # Initialize the ChatOpenAI model with GPT-3.5 Turbo
    llm = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo")

    # Create the summarization chain
    chain = AnalyzeDocumentChain(
        combine_docs_chain=load_summarize_chain(
            llm=llm,
            chain_type="refine",
            question_prompt=question_prompt,
            refine_prompt=refine_prompt,
            return_intermediate_steps=False,
        ),
        text_splitter=RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=2048, chunk_overlap=200
        ),
    )

    summaries = []
    date = datetime.datetime.now()
    for email in emails:
        from_address = email['from']
        subject = email['subject']
        cleaned_content = clean_text(email['body'])
        summary = chain.invoke(cleaned_content)
        email_info = f"From: {from_address}\nSubject: {subject}\nSummary:\n{summary['output_text']}\n\n"
        summaries.append(email_info)
        text_to_speech(email_info)
    
    with open(f"email_summaries{date}.txt", 'w') as f:
        f.writelines(summaries)

def text_to_speech(given_text):
    client = OpenAI()
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=given_text
    )
    temp_audio_path = "audios/temp.mp3"
    response.stream_to_file(temp_audio_path)

    # Load the newly generated audio
    new_audio = AudioSegment.from_file(temp_audio_path)
    output_file = "audios/combined_audio.mp3"

    if os.path.exists(output_file):
        # If the output file exists, load it and append the new audio
        existing_audio = AudioSegment.from_file(output_file)
        combined_audio = existing_audio + new_audio
    else:
        # If the output file does not exist, the new audio is the combined audio
        combined_audio = new_audio

    # Export the combined audio to the output file
    combined_audio.export(output_file, format="mp3")

    # Clean up temporary audio file
    os.remove(temp_audio_path)



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

    # Summarize the email content
    try:
        summarize_email(emails)


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