# -*- coding: utf-8 -*-
"""
Created on Fri Dec 29 11:03:56 2023

@author: INBHV3
"""

import os
#import io
import openai
import streamlit as st
from PyPDF2 import PdfReader
from langchain.chat_models import AzureChatOpenAI
from streamlit_extras.add_vertical_space import add_vertical_space
from PIL import Image
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.document_loaders import PyPDFLoader
import pickle
import fitz
import requests
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
import pandas as pd
from streamlit_chat import message
import docx2txt
import base64
import json
import streamlit.components.v1 as components
import googletrans as GT
from langdetect import detect
import textract
#import pypandoc
import tempfile
from doc2docx import convert
import pythoncom
import subprocess
import glob
# import pypandoc
# from io import BytesIO
# from docx import Document
#from werkzeug.utils import secure_filename
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

import azure.cognitiveservices.speech as speechsdk
speech_key, service_region = '9009b3a6617c4e169a38b3338057063f', 'centralus'
#temp_audio_file = 'translated_audio.wav'
openai.api_type = "azure"
openai.api_base = "https://rfq-abb.openai.azure.com/"
openai.api_key = "192d27f4fc584d76abd8a5eb978dcedf"
openai.api_version = "2023-07-01-preview" #"2023-03-15-preview"

docai_endpoint = "https://docai-trained-bhanu.cognitiveservices.azure.com/"
docai_key = "6943fe9ad42e478a8841ae77c1b8d12e"

epoch =1
i_loop = 0
translator = GT.Translator()
# Ensure COM is initialized
pythoncom.CoInitialize()

#GPT Model used in Azure
#Model: gpt-4-32k, engine="rfq", 


# %%
def recognize_from_microphone():
    # This example requires environment variables named "SPEECH_KEY" and "SPEECH_REGION"
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    speech_config.speech_recognition_language="en-US"

    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    #print("Speak into your microphone.")
    speech_recognition_result = speech_recognizer.recognize_once_async().get()

    if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print("Recognized: {}".format(speech_recognition_result.text))
        return speech_recognition_result.text
    elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:
        print("No speech could be recognized: {}".format(speech_recognition_result.no_match_details))
    elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = speech_recognition_result.cancellation_details
        print("Speech Recognition canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))
            print("Did you set the speech resource key and region values?")
# %%

def download_button(object_to_download, download_filename):
    """
    Generates a link to download the given object_to_download.
    Params:
    ------
    object_to_download:  The object to be downloaded.
    download_filename (str): filename and extension of file. e.g. mydata.csv,
    Returns:
    -------
    (str): the anchor tag to download object_to_download
    """
    if isinstance(object_to_download, pd.DataFrame):
        object_to_download = object_to_download.to_csv(index=False)

    # Try JSON encode for everything else
    else:
        object_to_download = json.dumps(object_to_download)

    try:
        # some strings <-> bytes conversions necessary here
        b64 = base64.b64encode(object_to_download.encode()).decode()

    except AttributeError as e:
        b64 = base64.b64encode(object_to_download).decode()

    dl_link = f"""
    <html>
    <head>
    <title>Start Auto Download file</title>
    <script src="http://code.jquery.com/jquery-3.2.1.min.js"></script>
    <script>
    $('<a href="data:text/csv;base64,{b64}" download="{download_filename}">')[0].click()
    </script>
    </head>
    </html>
    """
    return dl_link

def download_df():
    global i_loop
    st.session_state.i_loop = i_loop
    with st.spinner("Please wait..."):
        list_ques=['Is total limitation of liability "100%" of contract value ?',
                    'Is total limitation of liability with carve outs / exceptions?', 
                    'Is the Liquidated Damages (LDs) for Performance in the contract terms less than "5%" of contract value against agreed PG parameters ?',
                    'Is the Liquidated Damages (LDs) for Delay in the contract terms less than "0.5%" per week of delay from contract delivery date or upto "5%" of contract value ?', 
                    'Did the contract contain an express exclusion of liability for consequential losses and if that is to be borne or accepted by the one who accepts the contract ?', 
                    'Is Force Majeure clause mentioned in the contract and acceptable?',
                    'Is the Length of warranty 12 months from commissiong/handover or 18 months from delivery whichever ends earlier ?', 
                    'Has the Customer the right to suspend for ABBs breach? Is there a clause entitling the customer to terminate for convenience?',
                    'Has ABB the right to suspend for customers breach?',
                    'Is there a clause entitling the customer to terminate for convenience?',
                    'Is there Warranty start latest clause in the document? Is Repair/replacement customers exclusive remedy?',
                    'Does the replaced/repaired part carry an evergreen warranty (unlimited in time)?',
                    'Is ABB entitled to cost compensation for delays caused by customer?',
                    'Is ABB entitled to time extension for delays caused by customer?',
                    'Any Advance payment and retention?',
                    'What are the payment terms and Price Format?'
                    ]
        
        query_ques=['Give me a list of total limitation of liability. Also, if the total limitation of liability or aggregrate of liability is not exceeding contract value (or purchase order price, "100%" or MUSD 10) then add "yes, positive" in your response, if not then include in your response "no, negative"   ',
                    'Is total limitation of liability with carveouts/exceptions or with complaints?. Also, if the total limitation of liability is with carve outs then add "yes, positive" in your response, if not then include in your response "no, negative"  ', 
                    'Give me a list of Liquidated Damages (LDs) for Performance in the contract. Also, if the Liquidated Damages (LDs) for Performance in the contract terms is less than (or shall not exceed) "5%" of contract value (or purchase order value) against agreed PG parameters then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Give me a list of Liquidated Damages (LDs) for Delay in the contract. Also, if the Liquidated Damages (LDs) for Delay is less than 0.5% per week of delay from contract delivery date or if the Liquidated Damages (LDs) for Delay is less than (or shall not exceed) "5%" of contract value then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'What is express exclusion of liability in the contract? Also, if the contract contain an express exclusion of liability for consequential losses and if that is to be borne or accepted by the one who accepts the contract then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Is Force Majeure clause mentioned in the contract and acceptable? Also, if Force Majeure is not acceptable in the contract then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Give me the warranty details as mentioned in the contract. Also, if the Length of warranty is 12 months from commissioning/handover or 18 months from delivery whichever ends earlier then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Give me the list of customer rights for suspension and termination (along with mentioned clauses). Also, if the termination clause is satisfactory as to profit coverage to the company then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Has ABB has the right to suspend for customers breach? Also, if ABBs termination right for customers breach (e.g. non payment) is included in the document then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Is there a clause entitling the customer to terminate for convenience? Also, if the clause entitling the customer to terminate for convenience is satisfactory as to profit coverage to ABB then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Is there Warranty start latest clause in the document? Also, if Repair/replacement is customers exclusive remedy then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Does the replaced/repaired part carry an evergreen warranty (unlimited in time)? If yes then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'Is ABB entitled to cost compensation for delays caused by customer? If yes then add "yes, positive" in your response, if not then include in your response "no, negative"   ',
                    'Is ABB entitled to time extension for delays caused by customer? If yes then add "yes, positive" in your response, if not then include in your response "no, negative"   ',
                    'Give me the advance payment and retention terms as mentioned in the contract. Also, if the advance payment is "10%" or more than "10%" of the full contract value then add "yes, positive" in your response, if not then include in your response "no, negative"  ',
                    'What are the payment terms and Price Format (Price/Full Cost Model & Cash Flow Payment Terms)? Also, if the price format is lumpsum/fixed price or unit rate or both then add "yes, positive" in your response, if not then include in your response "no, negative"  '
                    ]
        
        # data=pd.DataFrame({"Contract Terms & Condition":list_ques,
        #                     "Customer_Enquiry":"",
        #                     "Go or No-Go status as per AI":""
        #                     })
        data_xl = pd.DataFrame(columns=["Contract Terms & Condition", "Customer_Enquiry", "Go or No-Go status as per AI" ])
        
        new_template = """You are an expert in reading RFQ's and Tender/contract Document that helps Finance Team to find Relevant information. 
        You are given a Tender document and a question.
        You need to find the answer to the question in the Tender document.
        
        Inlude in your answer the page numbers from where you fetched the information. 
        If the answer is not in the document just say "Information Not Available".
        {context}
        Question: {question}
        Helpful Answer:
        """
        new_prompt_template = PromptTemplate.from_template(new_template)
        
        st.session_state.risk_total_counter = 0
        st.session_state.risk_counter =0
        for query1 in query_ques: 
            #response=generate_response({"query":query1})
            response = generate_response(st.session_state.llm, 
                                                    st.session_state.retriever, 
                                                    new_prompt_template, 
                                                    query1)
            
            if 'yes, positive' in response.strip().lower():
                ai_outcome = 'OK'
                st.session_state.risk_counter+=1
                st.session_state.risk_total_counter+=1
            elif 'no, negative' in response.strip().lower():
                ai_outcome = 'Not OK'
                st.session_state.risk_total_counter+=1
            else:
                ai_outcome = 'Sorry, couldnt find this information'

            data_xl.loc[len(data_xl)] = [list_ques[st.session_state.i_loop], str(response), ai_outcome]
            st.session_state.i_loop +=1


        # if st.session_state.risk_total_counter != 0: 
        #     risk_percent = (st.session_state.risk_counter / st.session_state.risk_total_counter)*100
        #     if risk_percent >= 80:
        #         st.sidebar.markdown("<span style='color:green; font-size:24px'><i><b>This contract meets ABB expectation (score >80%)</b></i></span>  🔥", unsafe_allow_html=True)
        #         #st.warning("<span style='color:green; font-size:24px'><i><b>This contract meets ABB expectation</b></i></span>", icon="🔥")
        #     elif risk_percent>=60 and risk_percent<80:
        #         st.sidebar.markdown("<span style='color:orange; font-size:24px'><i><b>This contract partially meets ABB expectation (score >60% but <80%)</b></i></span>  ⚠️ ", unsafe_allow_html=True)
        #         #st.warning("<span style='color:orange; font-size:24px'><i><b>This contract partially meets ABB expectation</b></i></span>", icon="⚠️")
        #     else:
        #         st.sidebar.markdown("<span style='color:red; font-size:24px'><i><b>This contract didnot meet ABB expectation (score <60%)</b></i></span>  🚨", unsafe_allow_html=True)
        #         #st.warning("<span style='color:red; font-size:24px'><i><b>This contract didnot meet ABB expectation</b></i></span>", icon="🚨")
        #     #st.write("Score according to AI, out of 6: ",counter)
        # else:
        #     st.sidebar.markdown("<span style='color:red; font-size:24px'><i><b>Couldn't find scorable information</b></i></span>  🚨", unsafe_allow_html=True)
        #     #st.text(" Couldn't find any information!")
          
        #data_xl.loc[len(data_xl)] = [list_ques[st.session_state.i_loop], str(response), ai_outcome]
        #st.session_state.i_loop +=1
        # df = pd.DataFrame(st.session_state.col_values, columns=[st.session_state.col_name])
        components.html(download_button(data_xl, 'Risk_Analysis.csv'),height=0,)

def generate_response(llm, retriever_data, prompt_template, query_text):    
    
    qa_interface2 = RetrievalQA.from_chain_type(llm=llm,
                                                retriever=retriever_data,
                                                chain_type_kwargs={"prompt":prompt_template},  
                                                return_source_documents=True)
    return qa_interface2(query_text)['result']



# %%
with st.sidebar:
    st.title("Ask the Doc")
    st.markdown("This is an AI powered chatbot that can answer your questions about RFQs")
    # add_vertical_space(5)
    
    st.write(" ")

    col1, col2 = st.sidebar.columns([1,3])
    with col1: 
        st.write("Made by: ")
    with col2:
        image = Image.open('ABB Logo.png') 
        st.image(image, width=100)
        
    #st.write(" ")
    st.write(" ")
    
    # %% ... Below code block to create 'AI Risk Analysis" button
    # analytics_request = st.button("View Risk Analysis by AI")
    
    # if analytics_request:
    #     analytics_ques_list = ['if total limitation of liability is 100% of contract value or if this information is not available in the document, then give a single word string answer as "yes" else give answer as "no" ',
    #                            'if the Liquidated Damages (LDs) for Performance in the contract terms is less than 5% of contract value against agreed PG parameters or if this information is not available in the document, then give a single word string answer as "yes" else give answer as "no" ',
    #                            'if the Liquidated Damages (LDs) for Delay in the contract terms is less than 0.5% per week of delay from contract delivery date or upto 5% of contract value or if this information is not available in the document, then give a single word string answer as "yes" else give answer as "no" ',
    #                            'if defect liability period is till warranty period or if this information is not available in the document,, then give a single word string answer as "yes" else give answer as "no" ',
    #                            'if the contract contain an express exclusion of liability for consequential losses and if that is to be borne or accepted by the one who accepts the contract or if this information is not available in the document, then give a single word string answer as "yes" else give answer as "no" ',
    #                            'if the Length of warranty is 12 months from commissiong/handover or 18 months from delivery whichever ends earlier or if this information is not available in the document, then give a single word string answer as "yes" else give answer as "no" '
    #                            #'if the Length of warranty is 12 months from commissiong/handover or 18 months from delivery whichever ends earlier, then give a single word answer as "yes" else give answer as "no" ',
    #                            ]
    #     counter = 0
    #     with st.spinner("...Processing your request.....please wait"):
    #         for anlyt_query in analytics_ques_list:
    #             #print(anlyt_query)
    #             #print('\n')
    #             generated_response = generate_response(st.session_state.llm, 
    #                                                    st.session_state.retriever, 
    #                                                    None, anlyt_query)
    #             if generated_response.strip().lower()=='yes':
    #                 counter+=1
    #             #st.write(generated_response)
    #         #st.write("counter =", counter)
    #         if counter >=4:
    #             st.markdown("<span style='color:green; font-size:24px'><i><b>This contract meets ABB expectation</b></i></span>  🔥", unsafe_allow_html=True)
    #             #st.warning("<span style='color:green; font-size:24px'><i><b>This contract meets ABB expectation</b></i></span>", icon="🔥")
    #         elif counter>=2 and counter<4:
    #             st.markdown("<span style='color:orange; font-size:24px'><i><b>This contract partially meets ABB expectation</b></i></span>  ⚠️ ", unsafe_allow_html=True)
    #             #st.warning("<span style='color:orange; font-size:24px'><i><b>This contract partially meets ABB expectation</b></i></span>", icon="⚠️")
    #         else:
    #             st.markdown("<span style='color:red; font-size:24px'><i><b>This contract didnot meet ABB expectation</b></i></span>  🚨", unsafe_allow_html=True)
    #             #st.warning("<span style='color:red; font-size:24px'><i><b>This contract didnot meet ABB expectation</b></i></span>", icon="🚨")
    #         st.write("Score according to AI, out of 6: ",counter)
           
        
    # %%.....Below code to generate Excel sheet......##
    if 'epoch' in st.session_state:
        #global i_loop
        # st.session_state.i_loop = i_loop
        # excel_download = st.button("Download Chat & Risk Analysis")
        down_button = st.button("View & Download Risk Analysis", on_click=download_df)
        if down_button:
            if st.session_state.risk_total_counter != 0: 
                risk_percent = (st.session_state.risk_counter / st.session_state.risk_total_counter)*100
                if risk_percent >= 80:
                    st.sidebar.markdown("<span style='color:green; font-size:24px'><i><b>This contract meets ABB expectation (score >80%)</b></i></span>  🔥", unsafe_allow_html=True)
                    #st.warning("<span style='color:green; font-size:24px'><i><b>This contract meets ABB expectation</b></i></span>", icon="🔥")
                elif risk_percent>=60 and risk_percent<80:
                    st.sidebar.markdown("<span style='color:orange; font-size:24px'><i><b>This contract partially meets ABB expectation (score >60% but <80%)</b></i></span>  ⚠️ ", unsafe_allow_html=True)
                    #st.warning("<span style='color:orange; font-size:24px'><i><b>This contract partially meets ABB expectation</b></i></span>", icon="⚠️")
                else:
                    st.sidebar.markdown("<span style='color:red; font-size:24px'><i><b>This contract didnot meet ABB expectation (score <60%)</b></i></span>  🚨", unsafe_allow_html=True)
                    #st.warning("<span style='color:red; font-size:24px'><i><b>This contract didnot meet ABB expectation</b></i></span>", icon="🚨")
                #st.write("Score according to AI, out of 6: ",counter)
            else:
                st.sidebar.markdown("<span style='color:red; font-size:24px'><i><b>Couldn't find scorable information</b></i></span>  🚨", unsafe_allow_html=True)
                #st.text(" Couldn't find any information!")
        

def main():
    import time
    start_time = time.time()
    st.header("RFQ/Contract Summarization")
    #pdf = st.file_uploader("Upload your RFQ", type=["pdf"])
    # Create an empty list to store the uploaded files
    uploaded_files = []
    
    # Loop through the uploaded files and append them to the list
    for file in st.file_uploader("Upload your files here", accept_multiple_files=True):
        uploaded_files.append(file)
    
    global epoch
    global i_loop
    # Initialize session state variables
    if 'epoch' not in st.session_state:
        st.session_state.epoch = 1
        st.session_state.vectorstore = None
        st.session_state.retriever = None
        llm = AzureChatOpenAI(deployment_name="rfq8k", 
                              openai_api_key = openai.api_key, 
                              openai_api_version = openai.api_version, 
                              openai_api_base = openai.api_base) #openai_api_base=openai.api_base, engine="rfq"
        st.session_state.llm = llm
        #st.session_state.embeddings = embeddings
        
    if 'generated' not in st.session_state:
        st.session_state['generated'] = []
    if 'past' not in st.session_state:
        st.session_state['past'] = []
    
    #####........Block to run if PDF is uploaded......
    if uploaded_files:
        if st.session_state.epoch == 1:#epoch ==1:
            with st.spinner("Processing your request.....Please Wait"):
                ####...........Creating chunks, vectors and Embeddings
                # Run this loop only once to avoid wastage of time
                embeddings = OpenAIEmbeddings(chunk_size = 1, 
                                              openai_api_key = openai.api_key,
                                              openai_api_version = openai.api_version,
                                              openai_api_base = openai.api_base,
                                              deployment_id="rfq-embeddings"
                                              ) #deployment_name="rfq", openai_api_base=openai.api_base,
                
                # file_path = os.path.join(pdf.name) # Is 'file_path' required? can we directly use 'pdf' ?
                # with open(file_path,"wb") as f: 
                #     f.write(pdf.getbuffer())         
                #     #st.success("Saved File")
                # pdf_file=fitz.open(file_path)
                # text=""
                # for page in pdf_file:
                #     text+=page.get_text()
                
                ###### Create document intelligence client
                document_analysis_client = DocumentAnalysisClient(
                    endpoint=docai_endpoint, credential=AzureKeyCredential(docai_key)
                )
                # Create an empty string to store the text from the files
                text = ""
                # Loop through the files, extract the text, and append it to the string
                for file in uploaded_files:
                    file_type = os.path.splitext(file.name)[1]
                    if file_type == ".pdf" or file_type == ".PDF":
                        try:
                            pdf_file = fitz.open(stream=file.getvalue(), filetype="pdf")
                            for page in pdf_file:
                                text += page.get_text()
                        except:
                            # Load the PDF content
                            with open(file, "rb") as fd:
                                pdf_data = fd.read()
                            #....Using Document AI Intelligence
                            poller = document_analysis_client.begin_analyze_document(
                                    "prebuilt-read", pdf_data)
                            result = poller.result()
                            for page in result.pages:
                                for line in page.lines:
                                    text += line.content                    
                    elif file_type == ".docx":
                        try:
                            text += docx2txt.process(file)
                        except:
                            # Load the docx content
                            with open(file, "rb") as fd:
                                pdf_data = fd.read()
                            #....Using Document AI Intelligence
                            poller = document_analysis_client.begin_analyze_document(
                                    "prebuilt-read", pdf_data)
                            result = poller.result()
                            for page in result.pages:
                                for line in page.lines:
                                    text += line.content
                    elif file_type == ".doc":
                        ##Create a temporary directory
                        for doc in glob.iglob(file):
                            # print(doc)
                            subprocess.call(['lowriter', '--headless', '--convert-to', 'docx', doc])
                            
                        # temp_dir = tempfile.mkdtemp()
                        # # Save the uploaded file to the temporary directory
                        # doc_file_path = os.path.join(temp_dir, "uploaded.doc")
                        # with open(doc_file_path, "wb") as temp_file:
                        #     temp_file.write(file.read())

                        # # Convert the DOC file to DOCX
                        # docx_file_path = os.path.join(temp_dir, "output.docx")
                        # convert(doc_file_path, docx_file_path)
                        # text += docx2txt.process(docx_file_path)

                        # # Cleanup: Delete the temporary directory and its contents
                        # os.remove(doc_file_path)
                        # os.remove(docx_file_path)
                        # os.rmdir(temp_dir)
                    try: 
                        result = detect(text)
                    except:
                        # Load the PDF content
                        # with open(file, "rb") as fd:
                        #     pdf_data = fd.read()
                        #....Using Document AI Intelligence
                        poller = document_analysis_client.begin_analyze_document(
                                "prebuilt-read", file)
                        result = poller.result()
                        for page in result.pages:
                            for line in page.lines:
                                text += line.content
                        
                
                try:
                    result = detect(text)
                    if result!='en':
                        raw_trans = translator.translate(text, dest="en") 
                        translated_text = raw_trans.text
                        st.text('...doc is not in english...')
                    else:
                        translated_text =  text
                except:
                    st.text('something wrong')
                
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                splits = text_splitter.split_text(text)
        
                directory="vector_store"
                vectorstore = FAISS.from_texts(splits, embedding=embeddings)
                vectorstore.save_local(directory)
                vector_index = FAISS.load_local('vector_store', 
                                                OpenAIEmbeddings(openai_api_key = openai.api_key,
                                                                deployment_id = "rfq-embeddings" #deployment_name = "rfq"
                                                                ))
                retriever = vector_index.as_retriever(search_type="similarity", 
                                            search_kwargs={"k":10})
                template = """You are an expert in reading RFQ's and Tender/contract Document that helps Finance Team to find Relevant information in a PO. 
                You are given a Tender document and a question.
                You need to find the answer to the question in the Tender document.
                
                Give me the commercial values if present in the document.
                Highlight the keywords and numbers or values with '**'. 
                For Example:
                **Daily LD Amount**
                **Daily Drawing LD Amount**
                    
                Give the answer in sentences or bullet points instead of a paragraph.
                If the answer is not in the document just say "Information Not Available".
                {context}
                Question: {question}
                Helpful Answer:"""
                prompt_template = PromptTemplate.from_template(template)
                
                # Save values to session state
                # Save values to session state
                # st.session_state.file_path = file_path
                st.session_state.prompt_template = prompt_template
                st.session_state.vectorstore = vectorstore
                st.session_state.retriever = retriever
            
                st.success("Saved File")
                # Increment epoch
                st.session_state.epoch += 1
                ####.......End of creating chunks, vectors and embeddings
        
        list_ques=['','Give the Summary of Liabilities and consequential losses',
                   'What are the payment terms/conditions and Price Formats?',
                   'What are the suspension and termination rights and clauses?',
                   'What are the Liquidated Damages (LDs) for Performance and Delays?',
                   'What are penalty amounts or liability for Delayed Liquidated Damages?',
                   'List the Guarantees/waranty terms and clauses',
                   'What are the Governing laws, claims, and dispute mechanisms?',
                   'Who has the dispute resolution authority in this Contract?'  ]
        
        col1, col2 = st.columns([4.5,1])
        with col1:
            st.empty()
            user_input=st.selectbox("Select the question",list_ques)
        with col2: 
            st.write('')
            st.write('')
            submit=st.button("Submit")
            
            
        if submit:
            with st.spinner("...Processing your request.....please wait"):
                st.session_state.past.append(user_input)
                generated_response = generate_response(st.session_state.llm,
                                                       st.session_state.retriever, 
                                                       st.session_state.prompt_template,
                                                       user_input)
                st.session_state.generated.append(generated_response)
                # st.markdown(generated_response)
                
                chat_history = st.empty()
                if st.session_state['generated']:
                    chat_history.markdown("")
                    for i in range(len(st.session_state['generated'])-1, -1, -1):
                        chat_history.markdown(st.session_state["generated"][i])
                        chat_history.markdown(st.session_state['past'][i])
                        
        text_col, button_col = st.columns([4, 1])
        
        # Define styling for both elements
        style = """
        <style>
          #stButtonVoice {
            position: fixed;
            bottom: 0;
            // right: 0;
            margin-left: 1rem;
          }
          
          .stTextInput {
            position: fixed;
            bottom: 0;
            // left: 0;
            margin-right: 1rem;
          }
        </style>
        """
        
        # Inject the styling code for both elements
        st.markdown(style, unsafe_allow_html=True)
        if "my_text" not in st.session_state:
                st.session_state.my_text = ""

        def submit():
            st.session_state.my_text = st.session_state.widget
            st.session_state.widget = ""
        
        
        # Add your text input and button
        with text_col:
           st.text_input("Any further query?",key="widget", on_change=submit, placeholder ="Search here...")
           text_input = st.session_state.my_text
        
        with button_col:
            voice_search_button = st.button("Voice Search", key="stButtonVoice")

        if voice_search_button: 
            translated_text = recognize_from_microphone()
            text_input = translated_text

        search_text = text_input
        
        if search_text:
            with st.spinner("Processing your request..."):
                st.session_state.past.append(search_text)
                generated_response = generate_response(st.session_state.llm,
                                                       st.session_state.retriever, 
                                                       st.session_state.prompt_template,
                                                       search_text)
                st.session_state.generated.append(generated_response)
                # st.markdown(generated_response)

        if st.session_state['generated']:
            for i in range(len(st.session_state['generated'])):
                message(st.session_state["generated"][i], key=str(i))
                message(st.session_state['past'][i], is_user=True, key=str(i) + '_user')
        endtime=time.time()
        st.write("Time taken:    ", endtime-start_time)

if __name__=="__main__":
    main()

   