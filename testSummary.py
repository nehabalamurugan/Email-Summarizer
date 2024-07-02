import asyncio
import os, re
from email import policy
from email.parser import BytesParser
from langchain.chains import AnalyzeDocumentChain
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain_community.document_loaders import UnstructuredEmailLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_fixed


# Define a function to read the email content from a .eml file
def read_email(file_path):
    with open(file_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)    
    from_address = msg['from']
    subject = msg['subject']
    body = msg.get_body(preferencelist=('plain')).get_content()
    return from_address, subject, body

# Define a function to clean the email content
def clean_text(text):
    # Remove HTML tags
    text = re.sub(r'<.*?>', '', text)
    # Remove URLs
    text = re.sub(r'http\S+|www.\S+', '', text)
    # Remove special characters and multiple spaces
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'&\w+;', '', text)
    return text

# Define the prompt templates for summarization
question_prompt_template = """
Please provide a summary of the following text in bullet points:
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

# Path to the downloaded email file
email_file_path = '/Users/nehabalamurugan/Downloads/PJemail.eml'

# Read the email content and metadata from the file
from_address, subject, email_content = read_email(email_file_path)

# Clean the email content
cleaned_content = clean_text(email_content)

# Use the chain to summarize the cleaned email content
summary = chain.invoke(cleaned_content, return_only_outputs=True)

# Print the summary
print("From:", from_address)
print("Subject:", subject)
print("Summary:")
print(summary["output_text"])