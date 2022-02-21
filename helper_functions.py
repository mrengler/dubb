from __future__ import absolute_import

max_token_input = 1548
max_tokens_output = 250
chars_per_token = 3.70


import youtube_dl
import requests
import pandas as pd
import datetime
import time
import sys
sys.path.append('/Users/samplank/anaconda/envs/py3/lib/python3.9/site-packages')
sys.path.append('/Users/samplank/Downloads/writers-voice-311119-9c625b9d7064.json')

import openai
import datetime
from google.cloud import storage

import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv('OPENAI_API_KEY')
ASSEMBLY_API_KEY = os.getenv('ASSEMBLY_API_KEY')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="/Users/samplank/Downloads/writers-voice-311119-9c625b9d7064.json" 


def download_yt(url, filename):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '256'
        }],
        'postprocessor_args': [
            '-ar', '16000',
            '-ac', '1'
        ],
        'prefer_ffmpeg': True,
        'keepvideo': False, ## needs to be updated if this introduces a bug
        'nocheckcertificate': True,
        'outtmpl': filename,
        'verbose': True,
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def upload_to_gs(bucket_name, source_file_name, destination_file_name):
    """Uploads a file to the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The path to your file to upload
    # source_file_name = "local/path/to/file"
    # The ID of your GCS object
    # destination_file_name = "storage-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_file_name)

    blob.upload_from_filename(source_file_name, timeout=600)

    print(
        "File {} uploaded to {}.".format(
            source_file_name, destination_file_name
        )
    )

def generate_download_signed_url_v4(bucket_name, blob_name):
    """Generates a v4 signed URL for downloading a blob.

    Note that this method requires a service account key file. You can not use
    this if you are using Application Default Credentials from Google Compute
    Engine or from the Google Cloud SDK.
    """

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        version="v4",
        # This URL is valid for 15 minutes
        expiration=datetime.timedelta(minutes=15),
        # Allow GET requests using this URL.
        method="GET",
    )

    return url

def assembly_start_transcribe(audio_file):

    endpoint = "https://api.assemblyai.com/v2/transcript"

    json = {
      "audio_url": audio_file,
      "speaker_labels": True
    }

    headers = {
        "authorization": ASSEMBLY_API_KEY,
        "content-type": "application/json"
    }

    response = requests.post(endpoint, json=json, headers=headers)
    
    transcript_id = response.json()['id']
    
    print(transcript_id)
    
    return transcript_id

def assembly_finish_transcribe(transcript_id, speakers_input, paragraphs):

    endpoint = "https://api.assemblyai.com/v2/transcript/" + transcript_id + '/sentences'

    headers = {
        "authorization": ASSEMBLY_API_KEY,
    }

    response = requests.get(endpoint, headers=headers)
    
    try:
        print(1)
        sentences = response.json()['sentences']
        print(2)
        sentences_diarized = [(sentence['words'][0]['speaker'], sentence['text']) for sentence in sentences]
        print(3)
        speakers_duplicate = [speaker for speaker, sentence in sentences_diarized]
        print(4)
        unique_speakers = list(dict.fromkeys(speakers_duplicate))
        print(5)
        speaker_hash = {}
        print(6)
        for i,speaker in enumerate(speakers_input):
            speaker_hash[unique_speakers[i]] = speaker
        print(7)
        unknown_speakers = list(set(unique_speakers) - set(speaker_hash.keys()))
        print(8)
        for speaker in unknown_speakers:
            speaker_hash[speaker] = 'Unknown'
        print(9)
        speaker_hash['UNK'] = 'Unknown'
        print(10)

        if paragraphs==True:
            cleaned_paragraphs = []
            current_speaker = ''
            current_speaker_sentences = []
            for speaker, sentence in sentences_diarized:
                speaker = speaker_hash[speaker]
                if speaker != current_speaker:
                    if current_speaker != '':
                        current_speaker_sentences_joined = current_speaker + ": " + " ".join(current_speaker_sentences)
                        cleaned_paragraphs.append(current_speaker_sentences_joined)

                    current_speaker = speaker
                    current_speaker_sentences = [sentence]

                else:
                    current_speaker_sentences.append(sentence)

            cleaned_paragraphs.append(current_speaker_sentences_joined)

            return cleaned_paragraphs

        elif paragraphs==False:

            cleaned_sentences = [speaker_hash[speaker] + ": " +  sentence for speaker, sentence in sentences_diarized]

            return cleaned_sentences
    
    except:
        print(response.json())
        return 'waiting'

def get_max_lines(exchanges, n):
    
    
    while n > 0:
        n_chars = []

        for i in range(0, len(exchanges), n):
            exchanges_chunk = exchanges[i:i + n]
            exchanges_chunk_joined = ' '.join(exchanges_chunk)
            n_char = len([char for char in exchanges_chunk_joined])
            n_chars.append(1.0 * n_char / chars_per_token < max_token_input)

        if False not in n_chars:
            return n
        else:
            n += -1
    
    print("Could not get number of summary lines")

def split_transcript(cleaned_sentences, for_transcript, prompt_end_string=''):
        
    prompt_chunks = []
    
    num_chars = max_token_input * chars_per_token
    
    used_chars = 0
    
    chunk = []
    
    chunk_i = 0
    
    for sentence in cleaned_sentences:
        sentence_chars = len([char for char in sentence])
        
        if used_chars + sentence_chars <= num_chars:
            chunk.append(sentence)
            used_chars += sentence_chars
            
        else:
            if for_transcript:
                prompt_chunks.append("Chunk " + str(chunk_i) + ":\n\n"  + "\n".join(chunk) + "\n\n\n")
            else:
                prompt_chunks.append(' ' + "\n".join(chunk) + prompt_end_string)
            used_chars = sentence_chars
            chunk = [sentence]
            chunk_i += 1
            
    prompt_chunks.append("Chunk " + str(chunk_i) + ":\n\n"  + "\n".join(chunk) + "\n\n\n")
    
    return prompt_chunks

    
def content_filter(content_to_classify, user):
    response = openai.Completion.create(
      engine="content-filter-alpha",
      prompt = "<|endoftext|>"+content_to_classify+"\n--\nLabel:",
      temperature=0,
      max_tokens=1,
      top_p=1,
      frequency_penalty=0,
      presence_penalty=0,
      logprobs=10,
      user=user
    )
    
    output_label = response["choices"][0]["text"]

    # This is the probability at which we evaluate that a "2" is likely real
    # vs. should be discarded as a false positive
    toxic_threshold = -0.355

    if output_label == "2":
        # If the model returns "2", return its confidence in 2 or other output-labels
        logprobs = response["choices"][0]["logprobs"]["top_logprobs"][0]

        # If the model is not sufficiently confident in "2",
        # choose the most probable of "0" or "1"
        # Guaranteed to have a confidence for 2 since this was the selected token.
        if logprobs["2"] < toxic_threshold:
            logprob_0 = logprobs.get("0", None)
            logprob_1 = logprobs.get("1", None)

            # If both "0" and "1" have probabilities, set the output label
            # to whichever is most probable
            if logprob_0 is not None and logprob_1 is not None:
                if logprob_0 >= logprob_1:
                    output_label = "0"
                else:
                    output_label = "1"
            # If only one of them is found, set output label to that one
            elif logprob_0 is not None:
                output_label = "0"
            elif logprob_1 is not None:
                output_label = "1"

            # If neither "0" or "1" are available, stick with "2"
            # by leaving output_label unchanged.

    # if the most probable token is none of "0", "1", or "2"
    # this should be set as unsafe
    if output_label not in ["0", "1", "2"]:
        output_label = "2"

    return output_label

def convert(
    user,
    cleaned_sentences, 
    temp, 
    pres_penalty, 
    # n=20, 
    model="davinci:ft-summarize-2022-01-02-20-59-54",
    prompt_end_string="\n\n===\n\n",
    complete_end_string=[" +++"]):
    
    # prompt_chunks = []
    summary_chunks = []
    
    # for i in range(0, len(long_prompt_lines), n):
    #     prompt_chunk_lines = long_prompt_lines[i:i + n]
    #     prompt_chunk = "\n".join(prompt_chunk_lines)
    #     prompt_chunk = ' ' + prompt_chunk
    #     prompt_chunk += prompt_end_string
    #     prompt_chunks.append(prompt_chunk)
    
    # prompt_chunk_lens = [len(chunk.split()) for chunk in prompt_chunks]
    # print(len(prompt_chunk_lens))

    prompt_chunks = split_transcript(cleaned_sentences, for_transcript=False, prompt_end_string=prompt_end_string)
    
    for prompt_chunk in prompt_chunks:
        print(prompt_chunk)
        response = openai.Completion.create(
            model=model,
            prompt=prompt_chunk,
            max_tokens=max_tokens_output,
            temperature=temp,
            presence_penalty=pres_penalty,
            stop=complete_end_string,
            user=user,
        )
        print(response.choices[0].text)

        classification = content_filter(response.choices[0].text, user)
        
        if classification != '2': ##unsafe
            summary_chunk = response.choices[0].text
            summary_chunks.append(summary_chunk)
        else:
            print('UNSAFE RESPONSE:')
            print(response)

    converting = '\n\n'.join(summary_chunks)
    
    return converting

def run_combined(
    url,
    user, 
    speakers_input, 
    filename,
    model="davinci:ft-summarize-2022-01-02-20-59-54",
    bucket_name='writersvoice', 
    temperature=1.0, 
    presence_penalty=0.0, 
    prompt_end_string="\n\n===\n\n",
    complete_end_string=[" +++"],
    skip_upload=False,
    skip_transcribe=False,
    transcript_id='',
    paragraphs=False):
    
    if skip_upload==False:
        download_yt(url, filename)
        ## needs to wait on completion before next
        upload_to_gs(bucket_name, filename, filename)
    ## needs to wait
    audio_file = generate_download_signed_url_v4(bucket_name, filename)
    
    if skip_transcribe==False:
        ## needs to wait
        transcript_id = assembly_start_transcribe(audio_file)
    
    ## needs to wait
    cleaned_sentences = 'waiting'
    while cleaned_sentences == 'waiting':
        print('wait cleaned sentences')
        cleaned_sentences = assembly_finish_transcribe(transcript_id, speakers_input,paragraphs)
        time.sleep(60)
        
    ## needs to wait
    # max_lines = get_max_lines(cleaned_sentences, 100)
    # print('max lines:' + str(max_lines))
    converting = convert(
        user,
        cleaned_sentences, 
        temperature, 
        presence_penalty, 
        model=model,
        prompt_end_string=prompt_end_string,
        complete_end_string=complete_end_string
    )

    return converting, cleaned_sentences
    
def present_article(article):
    print('\n\n'.join([x for x in article.split('\n') if x not in ['', ' ']])) 
    
def get_transcript(
    url,
    speakers_input, 
    filename,
    bucket_name='writersvoice', 
    skip_upload=False,
    skip_transcribe=False,
    transcript_id='',
    write=False,
    write_title='',
    paragraphs=False):   
    
    if skip_upload==False:
        download_yt(url, filename)
        ## needs to wait on completion before next
        upload_to_gs(bucket_name, filename, filename)
    
    if skip_transcribe==False:
        ## needs to wait
        audio_file = generate_download_signed_url_v4(bucket_name, filename)
        ## needs to wait
        transcript_id = assembly_start_transcribe(audio_file)
    
    ## needs to wait
    cleaned_sentences = 'waiting'
    while cleaned_sentences == 'waiting':
        print('wait cleaned sentences')
        cleaned_sentences = assembly_finish_transcribe(transcript_id, speakers_input, paragraphs)
        time.sleep(10)
        
    prompt_chunks = split_transcript(cleaned_sentences, for_transcript=True)

    for prompt in prompt_chunks:
        print(prompt)
    
    if write == True:
        file1 = open('transcript_2022_02_07/' + write_title + ".txt","w")
        file1.writelines(prompt_chunks)
        file1.close()