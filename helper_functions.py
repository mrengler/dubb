from __future__ import absolute_import

max_token_input = 3000
max_tokens_output = 1000
max_tokens_facts_quotes = 500
max_tokens_output_base_model = 4097
max_tokens_output_is_ad = 10
max_tokens_output_image_description = 120
max_tokens_output_article_final = 2000
chars_per_token = 3.55
num_image_audios_to_produce = 3
double = 2
frame_rate = 10
min_video_length = 20


import youtube_dl
import requests
import pandas as pd
import datetime
import time
import replicate
from pydub import AudioSegment
import re
import math
import subprocess
import shutil
import random
import string
from fuzzywuzzy import process
import sys
sys.path.append('/Users/samplank/anaconda/envs/py3/lib/python3.9/site-packages')

import openai
import datetime
from google.cloud import storage

import os
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.environ.get('OPENAI_API_KEY')
ASSEMBLY_API_KEY = os.environ.get('ASSEMBLY_API_KEY')
REPLICATE_API_TOKEN = os.environ.get('REPLICATE_API_TOKEN')
MAILGUN_API_KEY = os.environ["MAILGUN_API_KEY"]
MAILGUN_DOMAIN = os.environ["MAILGUN_DOMAIN"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]


def millsecond_to_timestamp(ms):
    millis = int(ms)
    seconds=(millis/1000)%60
    seconds = int(seconds)
    minutes=(millis/(1000*60))%60
    minutes = int(minutes)
    hours=(millis/(1000*60*60))%24
    hours=int(hours)

    return "%d:%02d:%02d" % (hours, minutes, seconds)


def download_yt(url, filename):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }],
            'postprocessor_args': [
                '-ar', '16000',
                '-ac', '1'
            ],
            'prefer_ffmpeg': True,
            'keepvideo': False,
            'nocheckcertificate': True,
            'outtmpl': filename,
            'verbose': True,
            'ignoreerrors': False,
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return 'passed'
    except:
        return 'failed'


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

def download_from_gs(bucket_name, source_file_name, destination_file_name):
    """Downloads a blob from the bucket."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"

    # The ID of your GCS object
    # source_blob_name = "storage-object-name"

    # The path to which the file should be downloaded
    # destination_file_name = "local/path/to/file"

    storage_client = storage.Client()

    bucket = storage_client.bucket(bucket_name)

    # Construct a client side representation of a blob.
    # Note `Bucket.blob` differs from `Bucket.get_blob` as it doesn't retrieve
    # any content from Google Cloud Storage. As we don't need additional data,
    # using `Bucket.blob` is preferred here.
    blob = bucket.blob(source_file_name)
    blob.download_to_filename(destination_file_name)


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


def assembly_finish_transcribe(transcript_id, speakers_input, paragraphs, user):

    endpoint = "https://api.assemblyai.com/v2/transcript/" + transcript_id + '/sentences'

    headers = {
        "authorization": ASSEMBLY_API_KEY,
    }

    response = requests.get(endpoint, headers=headers)
    
    try:
        sentences = response.json()['sentences']
        sentences_diarized = [(sentence['words'][0]['speaker'], sentence['text'], millsecond_to_timestamp(sentence['start']), sentence['start']) for sentence in sentences]
        speakers_duplicate = [speaker for speaker, sentence, start_time, start_time_unformatted in sentences_diarized]
        unique_speakers = list(dict.fromkeys(speakers_duplicate))

        # speaker_hash = {}
        # for unique_speaker in unique_speakers:
        #     window_len = 20
        #     num_occurences = 100
        #     speaker_appearances = [i for i, (speaker, text, timestamp_formatted, timestamp_unformatted) in enumerate(sentences_diarized) if speaker == unique_speaker]
        #     speaker_appearances = speaker_appearances[:num_occurences]
        #     window = []
        #     for appearance_i in speaker_appearances:
        #         window_i = ['Speaker ' + speaker + ": " + text for (speaker, text, _, _) in sentences_diarized[max(appearance_i - window_len, 0):min(appearance_i + window_len, len(sentences_diarized))]]
        #         window += window_i
        #     window = list(dict.fromkeys(window))

        #     # first_appearance_i = next(i for i, (speaker, text, timestamp_formatted, timestamp_unformatted) in enumerate(sentences_diarized) if speaker == unique_speaker)
        #     # window = ['Speaker ' + speaker + ": " + text for (speaker, text, _, _) in sentences_diarized[max(first_appearance_i - window_len, 0):min(first_appearance_i + window_len, len(sentences_diarized))]]
        #     find_speaker_input = '\n\n'.join(window)
        #     ## reduce to fit into model window
        #     buffer = 250
        #     find_speaker_input = find_speaker_input[:int((max_tokens_output_base_model - buffer) * chars_per_token)]

        #     choose_pre = """The transcript:\n\n"""
        #     choose_post = """\n\n\nWhat is Speaker """ + unique_speaker + """'s name?:\n\nSpeaker """ + unique_speaker + ' is "'
        #     choose_text = choose_pre + find_speaker_input + choose_post
        #     print('This is choose_text for Speaker ' + unique_speaker)
        #     print(choose_text)
        #     choose = openai.Completion.create(
        #                 model='text-davinci-002',
        #                 prompt=choose_text,
        #                 max_tokens=20,
        #                 temperature=0.9,
        #                 presence_penalty=0.0,
        #                 user=user,
        #                 stop='"',
        #                 n=3
        #             )
        #     print('this is choose')
        #     print(choose)
        #     predicted_speaker = choose.choices[0].text
        #     print('This is predicted speaker for Speaker ' + unique_speaker)
        #     print(predicted_speaker)
        #     speaker = process.extract(predicted_speaker, speakers_input, limit=1)[0][0]
        #     speaker_hash[unique_speaker] = speaker

        current_speaker_sentences_joined = ''

        max_num_sentences = 15
        num_sentences_used = 0

        if paragraphs==True:
            cleaned_paragraphs = []
            cleaned_paragraphs_no_ads = []
            current_speaker = ''
            current_speaker_sentences = []
            start_times = []
            start_times_unformatted = []
            for speaker, sentence, start_time, start_time_unformatted in sentences_diarized:
                # speaker = speaker_hash[speaker]
                if (speaker != current_speaker) or (num_sentences_used >= max_num_sentences):
                    if current_speaker != '':
                        current_speaker_sentences_joined = current_speaker + ": " + " ".join(current_speaker_sentences)
                        cleaned_paragraphs.append(current_speaker_sentences_joined)

                        ## filter ads
                        ad_prompt = 'The transcript:\n\n' + '[' + str(start_time) + '] ' + current_speaker_sentences_joined + '\n\nIs this the transcript of an ad? Respond with either "yes" or "no".'
                        print(ad_prompt)
                        is_ad_response = openai.Completion.create(
                            model='text-davinci-002',
                            prompt=ad_prompt,
                            max_tokens=max_tokens_output_is_ad,
                            temperature=0.0,
                            user=user,
                        )

                        is_ad_response = is_ad_response.choices[0].text
                        print(is_ad_response)
                        is_ad_response = is_ad_response.lower()

                        ## filter promos
                        promo_prompt = 'The transcript:\n\n' + '[' + str(start_time) + '] ' + current_speaker_sentences_joined + '\n\nIs this the transcript of a promotion for another podcast? Respond with either "yes" or "no".'
                        print(promo_prompt)
                        is_promo_response = openai.Completion.create(
                            model='text-davinci-002',
                            prompt=promo_prompt,
                            max_tokens=max_tokens_output_is_ad,
                            temperature=0.0,
                            user=user,
                        )

                        is_promo_response = is_promo_response.choices[0].text
                        print(is_promo_response)
                        is_promo_response = is_promo_response.lower()

                        if ('no' in is_ad_response) and ('no' in is_promo_response):
                            cleaned_paragraphs_no_ads.append(current_speaker_sentences_joined)

                    current_speaker = speaker
                    current_speaker_sentences = [sentence]
                    start_times.append(start_time)
                    start_times_unformatted.append(start_time_unformatted)
                    num_sentences_used = 1

                else:
                    current_speaker_sentences.append(sentence)
                    num_sentences_used += 1

            current_speaker_sentences_joined = current_speaker + ": " + " ".join(current_speaker_sentences)

            cleaned_paragraphs.append(current_speaker_sentences_joined)

            ## filter ads
            ad_prompt = 'The transcript:\n\n' + '[' + str(start_time) + '] ' + current_speaker_sentences_joined + '\n\nIs this the transcript of an ad? Respond with either "yes" or "no".'
            print(ad_prompt)
            is_ad_response = openai.Completion.create(
                model='text-davinci-002',
                prompt=ad_prompt,
                max_tokens=max_tokens_output_is_ad,
                temperature=0.0,
                user=user,
            )

            is_ad_response = is_ad_response.choices[0].text
            print(is_ad_response)
            is_ad_response = is_ad_response.lower()

            ## filter promos
            promo_prompt = 'The transcript:\n\n' + '[' + str(start_time) + '] ' + current_speaker_sentences_joined + '\n\nIs this the transcript of a promotion for another podcast? Respond with either "yes" or "no".'
            print(promo_prompt)
            is_promo_response = openai.Completion.create(
                model='text-davinci-002',
                prompt=promo_prompt,
                max_tokens=max_tokens_output_is_ad,
                temperature=0.0,
                user=user,
            )

            is_promo_response = is_promo_response.choices[0].text
            print(is_promo_response)
            is_promo_response = is_promo_response.lower()

            if ('no' in is_ad_response) and ('no' in is_promo_response):
                cleaned_paragraphs_no_ads.append(current_speaker_sentences_joined)

            ## determine the names of the speakers
            speaker_hash = {}
            for unique_speaker in unique_speakers:
                window_len = 10
                num_occurences = 100
                speaker_appearances = [i for i, line in enumerate(cleaned_paragraphs_no_ads) if line.split(':')[0] == unique_speaker]
                speaker_appearances = speaker_appearances[:num_occurences]
                window = []
                for appearance_i in speaker_appearances:
                    window_i = [line for line in cleaned_paragraphs_no_ads[max(appearance_i - window_len, 0):min(appearance_i + window_len, len(cleaned_paragraphs_no_ads))]]
                    window += window_i
                window = list(dict.fromkeys(window))

                # first_appearance_i = next(i for i, (speaker, text, timestamp_formatted, timestamp_unformatted) in enumerate(sentences_diarized) if speaker == unique_speaker)
                # window = ['Speaker ' + speaker + ": " + text for (speaker, text, _, _) in sentences_diarized[max(first_appearance_i - window_len, 0):min(first_appearance_i + window_len, len(sentences_diarized))]]
                find_speaker_input = '\n\n'.join(window)
                ## reduce to fit into model window
                buffer = 250
                find_speaker_input = find_speaker_input[:int((max_tokens_output_base_model - buffer) * chars_per_token)]

                choose_pre = """The transcript:\n\n"""
                choose_post = """\n\n\nWhat is Speaker """ + unique_speaker + """'s name?:\n\nSpeaker """ + unique_speaker + ' is "'
                choose_text = choose_pre + find_speaker_input + choose_post
                print('This is choose_text for Speaker ' + unique_speaker)
                print(choose_text)
                choose = openai.Completion.create(
                            model='text-davinci-002',
                            prompt=choose_text,
                            max_tokens=20,
                            temperature=0.9,
                            presence_penalty=0.0,
                            user=user,
                            stop='"',
                        )
                print('this is choose')
                predicted_speaker = choose.choices[0].text
                print('This is predicted speaker for Speaker ' + unique_speaker)
                print(predicted_speaker)
                speaker = process.extract(predicted_speaker, speakers_input, limit=1)[0][0]
                speaker_hash[unique_speaker] = speaker

            cleaned_paragraphs = [speaker_hash[line.split(':')[0]] + ':' + ':'.join(line.split(':')[1:]) for line in cleaned_paragraphs]
            cleaned_paragraphs_no_ads = [speaker_hash[line.split(':')[0]] + ':' + ':'.join(line.split(':')[1:]) for line in cleaned_paragraphs_no_ads]

            print(cleaned_paragraphs)
            print(cleaned_paragraphs_no_ads)    

            return cleaned_paragraphs, start_times, cleaned_paragraphs_no_ads, start_times_unformatted, sentences_diarized

        ##TODO this should be cleaned up since we're never using paragraphs==False
        elif paragraphs==False:

            cleaned_sentences = [speaker_hash[speaker] + ": " +  sentence for speaker, sentence, start_time, start_time_unformatted in sentences_diarized]
            start_times = [start_time for speaker, sentence, start_time, start_time_unformatted in sentences_diarized]
            start_times_unformatted = [start_time_unformatted for speaker, sentence, start_time, start_time_unformatted in sentences_diarized]

            return cleaned_sentences, start_times, cleaned_sentences, start_times_unformatted, sentences_diarized
        
    except:
        return 'waiting', None, None, None, None


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


def split_transcript(cleaned_paragraphs, for_transcript, prompt_end_string=''):
        
    prompt_chunks = []
    num_chars = max_token_input * chars_per_token
    used_chars = 0
    chunk = []
    chunk_i = 0
    
    for sentence in cleaned_paragraphs:
        sentence_chars = len([char for char in sentence])
        
        if used_chars + sentence_chars <= num_chars:
            chunk.append(sentence)
            used_chars += sentence_chars
            
        else:
            if for_transcript==True:
                prompt_chunks.append("Chunk " + str(chunk_i) + ":\n\n"  + "\n".join(chunk) + "\n\n\n")
            elif for_transcript==False:
                prompt_chunks.append(' ' + "\n\n".join(chunk) + prompt_end_string)
            used_chars = sentence_chars
            chunk = [sentence]
            chunk_i += 1
    
    if for_transcript==True:        
        prompt_chunks.append("Chunk " + str(chunk_i) + ":\n\n"  + "\n".join(chunk) + "\n\n\n")
    elif for_transcript==False:
        prompt_chunks.append(' ' + "\n\n".join(chunk) + prompt_end_string)

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


def clean_chunk(txt):
    txt_split = re.split('\n\n', txt)
    txt_groups = []
    for s in txt_split:
        s = s.lstrip()
        if s[-1:] not in ['.', '!', '?']:
            s_sub = re.split('(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', s)
            s_keep = s_sub[:-1]
            s = ' '.join(s_keep)
        txt_groups.append(s)
    
    txt = '\n\n'.join(txt_groups)
    return txt


def get_length(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return float(result.stdout)


def split_txt_into_multi_lines(input_str, line_length): ##from https://stackoverflow.com/questions/50628267/ffmpeg-creating-video-using-drawtext-along-with-word-wrap-and-padding
    words = input_str.split(" ")
    line_count = 0
    split_input = ""
    for word in words:
        line_count += 1
        line_count += len(word)
        if line_count > line_length:
            split_input += "\n"
            line_count = len(word) + 1
            split_input += word
            split_input += " "
        else:
            split_input += word
            split_input += " "
    
    return split_input


def create_video(
    user,
    filename,
    num_image_audios,
    description,
    top_quote,
    top_quote_audio_filename,
    pres_penalty,
    bucket_name,
    visual_style,
    fact_text
    ):

    replicate_model = replicate.models.get("deforum/deforum_stable_diffusion")

    if visual_style == 'low_poly':
        object_text = 'Concept art of '
        style_text = 'low poly'
    elif visual_style == 'painting':
        object_text = 'A digital illustration of '
        style_text = 'by edward hopper'
    elif visual_style == 'spooky':
        object_text = 'A digital illustration of '
        style_text = 'by zdzisław beksiński, dark surrealism'

    print('this is first prompt:')

    prompt_text_pre = "Here are some facts that were discussed in a podcast episode:\n\n" + fact_text +\
    '\n\nHere is the top quote from the podcast episode:\n\n"' + top_quote + '"\n\nUse the top quote and facts to write a description of the image that accompanies the podcast episode:\n\nThe image features'

    print(prompt_text_pre)

    top_quote_image_description_response_pre = openai.Completion.create(
        model='text-davinci-002',
        prompt=prompt_text_pre,
        max_tokens=max_tokens_output_image_description,
        temperature=0.0,
        presence_penalty=pres_penalty,
        user=user,
        n=3
    )

    top_quote_image_description_pre_one = top_quote_image_description_response_pre.choices[0].text
    top_quote_image_description_pre_two = top_quote_image_description_response_pre.choices[1].text
    top_quote_image_description_pre_three = top_quote_image_description_response_pre.choices[2].text

    top_quote_image_description_classifications = []
    top_quote_image_descriptions = []
    for top_quote_image_description_pre in [top_quote_image_description_pre_one, top_quote_image_description_pre_two, top_quote_image_description_pre_three]:

        top_quote_image_description_pre = top_quote_image_description_pre.replace(':', '')
        top_quote_image_description_pre = top_quote_image_description_pre.lstrip()

        prompt_text = 'The description of the image:\n\n' + top_quote_image_description_pre + '\n\nEdit the description of the image so that it only contains physical details:'

        print(prompt_text)

        top_quote_image_description_response = openai.Completion.create(
            model='text-davinci-002',
            prompt=prompt_text,
            max_tokens=max_tokens_output_image_description,
            temperature=1.0,
            presence_penalty=pres_penalty,
            user=user,
        )

        top_quote_image_description = top_quote_image_description_response.choices[0].text

        ## first log the classification
        top_quote_image_description_classification = content_filter(top_quote_image_description, user)
        top_quote_image_description_classifications.append(top_quote_image_description_classification)

        top_quote_image_description = top_quote_image_description.replace(':', '')
        top_quote_image_description = top_quote_image_description.replace('"', '')
        top_quote_image_description = top_quote_image_description.replace('\n\n', '')
        top_quote_image_description = top_quote_image_description.lstrip()    

        print("top_quote_image_description")
        print(top_quote_image_description)

        # top_quote_image_description_part_2 = top_quote_image_description_response.choices[1].text

        # ## first log the classification
        # top_quote_image_description_classification_part_2 = content_filter(top_quote_image_description_part_2, user)

        # top_quote_image_description_part_2 = top_quote_image_description_part_2.replace(':', '')
        # top_quote_image_description_part_2 = top_quote_image_description_part_2.replace('"', '')
        # top_quote_image_description_part_2 = top_quote_image_description_part_2.replace('\n\n', '')
        # top_quote_image_description_part_2 = top_quote_image_description_part_2.lstrip()

        # print("this is top_quote_image_description_part_2")
        # print(top_quote_image_description_part_2)

        # print("this is third prompt:")
     
        # top_quote_image_description_part_3 = top_quote_image_description_response.choices[2].text

        # ## first log the classification
        # top_quote_image_description_classification_part_3 = content_filter(top_quote_image_description_part_3, user)

        # top_quote_image_description_part_3 = top_quote_image_description_part_3.replace(':', '')
        # top_quote_image_description_part_3 = top_quote_image_description_part_3.replace('"', '')
        # top_quote_image_description_part_3 = top_quote_image_description_part_3.replace('\n\n', '')
        # top_quote_image_description_part_3 = top_quote_image_description_part_3.lstrip()

        # print(top_quote_image_description_part_3)

        ## make once sentence, all lowercase
        top_quote_image_description = top_quote_image_description.replace('.', ',').replace('!', ',').replace('?', ',').lower()
        top_quote_image_descriptions.append(top_quote_image_description)
        # top_quote_image_description_part_2 = top_quote_image_description_part_2.replace('.', ',').replace('!', ',').replace('?', ',').lower()
        # top_quote_image_description_part_3 = top_quote_image_description_part_3.replace('.', ',').replace('!', ',').replace('?', ',').lower()    


    if '2' not in top_quote_image_description_classifications: ##unsafe

        image = replicate.predictions.create(
            version=replicate_model.versions.list()[0],
            input={
                "animation_prompts": '0: ' + object_text + top_quote_image_descriptions[0] + ' ' + style_text + ' | 10: '\
                + object_text + top_quote_image_descriptions[1] + ' ' + style_text + ' | 20: ' \
                + object_text + top_quote_image_descriptions[2] + ' ' + style_text,
                "zoom": "0: (1.00)",
                "fps": 10,
                "color_coherence": "Match Frame 0 HSV",
                "sampler": "euler_ancestral",
                }
        )

        src=''
        i = 0
        while ((i < 50) and (src == '')):
            time.sleep(10)
            image.reload()
            if image.status == 'succeeded':
                print(image)
                print(image.output)
                src = image.output
            i += 1

        random_str = ''.join(random.choices(string.ascii_lowercase, k=5))

        ##download from replicate
        image_filename = filename.split('.')[0] + '_image_' + str(num_image_audios) + random_str + ".mp4"
        response = requests.get(src)
        open(image_filename, "wb").write(response.content)


        ##slow looped animation
        slow_multiple = 1.25
        slowed_image_filename = filename.split('.')[0] + '_slowed_' + str(num_image_audios) + random_str + ".mp4"
        os.system("""ffmpeg -i """ + image_filename + """ -vf  "setpts=""" + str(slow_multiple) + """*PTS" """ + slowed_image_filename)

        ##get length and multipliers
        l = get_length(image_filename) * slow_multiple
        fps_full = l * double * frame_rate
        desired_length = get_length(top_quote_audio_filename)
        multiplier = desired_length / (l * 2)
        loop = math.ceil(multiplier)

        ##make looped animation
        image_looped_filename = filename.split('.')[0] + '_looped_' + str(num_image_audios) + random_str + ".mp4"
        os.system("""ffmpeg -i """ + slowed_image_filename + """ -filter_complex "[0]reverse[r];[0][r]concat,loop=""" + str(loop) + """:""" + str(fps_full) + """  " """ + image_looped_filename)

        ###join looped animation with audio
        image_audio_filename = filename.split('.')[0] + '_video_' + str(num_image_audios) + random_str + ".mp4"
        tmp_image_audio_filename = 'tmp_' + image_audio_filename
        os.system("""ffmpeg -i """ + image_looped_filename + """ -i """ + top_quote_audio_filename + """ -c:v copy -c:a aac """ + tmp_image_audio_filename)
        
        ##trim end of video
        os.system("""ffmpeg -i """ + tmp_image_audio_filename + """ -ss 00:00:00 -t """ + millsecond_to_timestamp(math.ceil(desired_length) * 1000) + """ """ + image_audio_filename)

        upload_to_gs(bucket_name, image_audio_filename, image_audio_filename)

        return image_audio_filename


def create_meme(
    user,
    filename,
    num_memes,
    description,
    top_quote,
    pres_penalty,
    bucket_name,
    visual_style,
    fact_text
    ):

    replicate_model = replicate.models.get("stability-ai/stable-diffusion")

    if visual_style == 'low_poly':
        object_text = 'Concept art of '
        style_text = 'low poly'
    elif visual_style == 'painting':
        object_text = 'A digital illustration of '
        style_text = 'by edward hopper'
    elif visual_style == 'spooky':
        object_text = 'A digital illustration of '
        style_text = 'by zdzisław beksiński, dark surrealism'

    prompt_text = "Here are some facts that were discussed in a podcast episode:\n\n" + fact_text +\
    '\n\nHere is the top quote from the podcast episode:\n\n"' + top_quote + '"\n\nUse the top quote and facts to write a description of the image that accompanies the podcast episode:\n\nThe image features'

    print(prompt_text)

    top_quote_image_description_response = openai.Completion.create(
        model='text-davinci-002',
        prompt=prompt_text,
        max_tokens=max_tokens_output_image_description,
        temperature=0.0,
        presence_penalty=pres_penalty,
        user=user,
    )

    top_quote_image_description = top_quote_image_description_response.choices[0].text

    ## first log the classification
    top_quote_image_description_classification = content_filter(top_quote_image_description, user)

    top_quote_image_description = top_quote_image_description.replace(':', '')
    top_quote_image_description = top_quote_image_description.lstrip()

    ## make once sentence, all lowercase
    top_quote_image_description = top_quote_image_description.replace('.', ',').replace('!', ',').replace('?', ',').lower()

    print("top_quote_image_description")
    print(top_quote_image_description)

    if (top_quote_image_description_classification != '2'):

        image = replicate.predictions.create(
            version=replicate_model.versions.list()[0],
            input={
                "prompt": object_text + top_quote_image_description + ' ' + style_text,
                "num_outputs": 1,
                "guidance_scale": 7.5,
                "num_inference_steps": 100,
                }
        )

        src=''
        i = 0
        while ((i < 50) and (src == '')):
            time.sleep(10)
            image.reload()
            if image.status == 'succeeded':
                print(image)
                print(image.output)
                src = image.output[0]
            i += 1

        ##download from replicate
        random_str = ''.join(random.choices(string.ascii_lowercase, k=5))
        image_filename = filename.split('.')[0] + '_imagenomovie_' + str(num_memes) + random_str + ".png"
        response = requests.get(src)
        open(image_filename, "wb").write(response.content)

        ##add text on top
        meme_filename = filename.split('.')[0] + '_meme_' + str(num_memes) + random_str + ".png"
        fontsize = 36
        line_length = 20
        w_padding=100
        l_top_quote = len(top_quote)
        if l_top_quote > 150:
            fontsize = int(fontsize / ((l_top_quote / 150) ** (1/3)))
            line_length = int(math.sqrt(l_top_quote / 150) * line_length)
            w_padding = int(w_padding / ((l_top_quote / 150) ** (1/3)))
        n_lines = math.ceil(l_top_quote / line_length)
        h_px = n_lines * fontsize * 1.33
        h_padding = (512 - h_px) / 2
        print('this is fontsize')
        print(fontsize)
        print('this is line length')
        print(line_length)
        print('this is length of top quote')
        print(len(top_quote))
        print('this is top quote')
        print(top_quote)
        top_quote = top_quote.replace(',', '\\,')
        top_quote = top_quote.replace(':', '')
        top_quote = re.escape(top_quote)
        print('this is os.system')
        print("""ffmpeg -i """ + image_filename + """ -vf "drawtext=text='""" + split_txt_into_multi_lines(top_quote, line_length) + """':bordercolor=black:borderw=3:fontcolor=white:fontsize=""" + str(fontsize) + """:x=""" + str(w_padding) + """:y=""" + str(h_padding) + """:" """ + meme_filename)
        os.system("""ffmpeg -i """ + image_filename + """ -vf "drawtext=text='""" + split_txt_into_multi_lines(top_quote, line_length) + """':bordercolor=black:borderw=3:fontcolor=white:fontsize=""" + str(fontsize) + """:x=""" + str(w_padding) + """:y=""" + str(h_padding) + """:" """ + meme_filename)

        upload_to_gs(bucket_name, meme_filename, meme_filename)

        return meme_filename


def convert(
    user,
    cleaned_paragraphs,
    sentences_diarized,
    speakers_input,
    filename,
    bucket_name, 
    temp, 
    pres_penalty, 
    model,
    prompt_end_string,
    editorial_style
    ):

    audio_filenames = []
    audio_durations = [] 
    facts = []
    quotes = []

    start_times_unformatted = [timestamp for (_, _, _, timestamp) in sentences_diarized]
    sentences_unformatted = [sentence for (_,sentence,_,_) in sentences_diarized]
    prompt_chunks = split_transcript(cleaned_paragraphs, for_transcript=False, prompt_end_string=prompt_end_string)

    print(sentences_diarized)

    print(prompt_chunks)

    ## fact prompt prefix and suffix
    top_facts_prompt_pre = """The transcript:\n\n"""
    top_facts_prompt_post = """\n\nThe 5 most important facts discussed in the transcript are:\n\n1."""
    
    ## quote prompt prefix and suffix
    top_quotes_prompt_pre = """The full transcript:\n\n"""
    top_quotes_prompt_post = '\n\nThe most engaging section of the transcript, exactly how it is written: "'

    for prompt_chunk in prompt_chunks:

        print('this is prompt_chunk')
        print(prompt_chunk)

        fact_prompt_chunk = top_facts_prompt_pre + prompt_chunk + top_facts_prompt_post
        quote_prompt_chunk = top_quotes_prompt_pre + prompt_chunk + top_quotes_prompt_post

        print(fact_prompt_chunk)

        print(quote_prompt_chunk)

        ## get top facts
        r_fact = openai.Completion.create(
                model='text-davinci-002',
                prompt=fact_prompt_chunk,
                max_tokens=max_tokens_facts_quotes,
                temperature=0.0,
                presence_penalty=pres_penalty,
                user=user,
            )
        r_fact_text = r_fact.choices[0].text
        r_fact_text_list = r_fact_text.split('\n\n')
        new_facts = [r_fact_text_list[0][1:]] + [fact[3:] for fact in r_fact_text_list[1:]]
        for fact in new_facts:
            fact_classification = content_filter(fact, user)
            if fact_classification  != '2':
                facts.append(fact)
        
        ## get top quote
        r_quote = openai.Completion.create(
                model='text-davinci-002',
                prompt=quote_prompt_chunk,
                max_tokens=max_tokens_facts_quotes,
                temperature=0.8,
                presence_penalty=pres_penalty,
                user=user,
                stop='"',
                n=3,
            )
        ## TODO abstract this for loop so that it takes however many outputs are given
        quote_one = r_quote.choices[0].text
        quote_two = r_quote.choices[1].text
        quote_three = r_quote.choices[2].text
        for quote in [quote_one, quote_two, quote_three]:
            ## fix common problems in the top quote
            quote = quote.replace("The full transcript:\n\n", '')
            quote = quote.replace("The full transcript: ", '')
            quote = quote.replace("The full transcript:", '')
            for speaker in speakers_input:
                quote = quote.replace(speaker + ": ", '')
                quote = quote.replace("Unknown: ", '')
            if len(quote.split('\n\n')) == 1:
                if quote in prompt_chunk:
                    quote_classification = content_filter(quote, user)
                    if quote_classification  != '2':
                        quotes.append(quote)

                        ## generate audiograms
                        print('this is debug section')
                        print("'" + quote + "'")
                        # try:

                        top_quote_split = re.split('\n\n|(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', quote)
                        print('this is top_quote_split')
                        print(top_quote_split)

                        ## use a different start sentence if the first or last are too short
                        off_index_start = 0
                        for sentence in top_quote_split:
                            if len(sentence) >= 10:
                                break
                            else:
                                off_index_start += 1
                                
                        off_index_end = -1
                        for sentence in reversed(top_quote_split):
                            if len(sentence) >= 10:
                                break
                            else:
                                off_index_end -= 1

                        print('this is start_times_unformatted')
                        print(start_times_unformatted)

                        print('this is sentences_unformatted')
                        print(sentences_unformatted)

                        ## find quote audio start time, end time, duration
                        print('top quote split off')
                        print(top_quote_split[off_index_start].casefold())
                        find_top_quote_start_true_text = process.extract(top_quote_split[off_index_start], sentences_unformatted, limit=1)[0][0]
                        print('this is find_top_quote_start_true_text')
                        print(find_top_quote_start_true_text)
                        tq_start_i = sentences_unformatted.index(find_top_quote_start_true_text)
                        print('this is tq_start_i')
                        print(tq_start_i)
                        tq_start = start_times_unformatted[tq_start_i - off_index_start]
                        print(top_quote_split[off_index_end].casefold())
                        find_top_quote_end_true_text = process.extract(top_quote_split[off_index_end], sentences_unformatted, limit=1)[0][0]
                        print('this is find_top_quote_end_true_text')
                        print(find_top_quote_end_true_text)
                        tq_end_i = sentences_unformatted.index(find_top_quote_end_true_text)
                        print('this is tq_end_i')
                        print(tq_end_i)

                        if tq_end_i < len(sentences_diarized) - 1:
                            tq_end = start_times_unformatted[tq_end_i - off_index_end]
                        elif tq_end_i == len(sentences_diarized) - 1:
                            tq_end = 100000000000

                        tq_duration = (tq_end - tq_start) / 1000

                        ## generate audio segment of quote
                        top_quote_audio = AudioSegment.from_file(filename, format='mp3', start_second=tq_start / 1000, duration=tq_duration)
                        top_quote_audio_filename = filename.split('.')[0] + str(tq_start) + "_" + str(tq_end) + ".mp3"
                        print(top_quote_audio_filename)
                        top_quote_audio.export(top_quote_audio_filename, format="mp3")
                        audio_filenames.append(top_quote_audio_filename)
                        audio_durations.append(tq_duration)
                        upload_to_gs(bucket_name, top_quote_audio_filename, top_quote_audio_filename)
                    else:
                        print('quote classification == 2')
                        print(quote)
                else:
                    print('quote is not verbatim from the text')
                    print(quote)
            else:
                print('quote is multiple paragraphs')
                print(quote)

    ## combine top facts    
    fact_text = """"""
    for i, r in enumerate(facts):
        fact_text += str(i + 1) + ': ' + r + "\n"

    ## combine top quotes 
    quote_text = """"""
    for i, r in enumerate(quotes):
        quote_text += str(i + 1) + ': "' + r + '"\n'

    if editorial_style == 'insightful':
        style_text = "is serious and insightful in tone"
    elif editorial_style == 'funny':
        style_text = "will make the reader laugh"
    elif editorial_style == 'creepy':
        style_text = "will make the reader's skin crawl"
        
    article_prompt = """Here are some quotes taken from a podcast conversation:\n\n"""+\
    quote_text +\
    """\n\nHere are some facts that were discussed in the same conversation:\n\n""" +\
    fact_text + \
    """\n\nUse these quotes and facts to write a coherent article that """ + style_text + """:"""
    
    print(article_prompt)
    
    ## generate article
    r = openai.Completion.create(
                model='text-davinci-002',
                prompt=article_prompt,
                max_tokens=max_tokens_output,
                temperature=temp,
                presence_penalty=pres_penalty,
                user=user,
                n=5,
            )
    ## TODO make this more abstract so that it isn't dependent on the number of generations
    article_one = r.choices[0].text
    article_two = r.choices[1].text
    article_three = r.choices[2].text
    article_four = r.choices[3].text
    article_five = r.choices[4].text
    
    print("\n\nResponse One:")
    print(article_one)
    print("\n\nResponse Two:")
    print(article_two)
    print("\n\nResponse Three:")
    print(article_three)
    print("\n\nResponse Four:")
    print(article_four)
    print("\n\nResponse Five:")
    print(article_five)
    
    choose_pre = """Here are five versions of the same article:\n\n\nVersion One:"""
    choose_post = """\n\n\nChoose the most coherent version:\n\nVersion"""
    choose_text = choose_pre + article_one + '\n\n\nVersion Two:' + article_two +\
    '\n\n\nVersion Three:' + article_three + '\n\n\nVersion Four:' + article_four +\
    '\n\n\nVersion Five:' + article_five + choose_post
    print(choose_text)
    choose = openai.Completion.create(
                model='text-davinci-002',
                prompt=choose_text,
                max_tokens=20,
                temperature=0.0,
                presence_penalty=pres_penalty,
                user=user,
            )
    choice = choose.choices[0].text
    print("\n\nChoice:\n\n")
    print(choice)
    if 'One' in choice:
        article = article_one
    elif 'Two' in choice:
        article = article_two
    elif 'Three' in choice:
        article = article_three
    elif 'Four' in choice:
        article = article_four
    elif 'Five' in choice:
        article = article_five
    else:
        article = article_one

    return article, quotes, audio_filenames, audio_durations, fact_text


def run_combined(
    content,
    content_type,
    user, 
    speakers_input, 
    filename,
    model,
    bucket_name='writersvoice', 
    temperature=0.8, 
    presence_penalty=0.0, 
    prompt_end_string="",
    skip_upload=False,
    skip_transcribe=False,
    transcript_id='',
    paragraphs=False,
    make_videos=True,
    make_memes=True,
    visual_style='painting',
    editorial_style='insightful'
    ):


    if skip_upload==False:
        if content_type=='url':
            status = download_yt(content, filename)
            if status == 'failed':
                return "There was an error accessing that URL. Please try again in a couple of minutes. If that doesn't work, we may not be able to access that URL."
            elif status == 'passed':
                upload_to_gs(bucket_name, filename, filename)
        elif content_type=='file':
            download_from_gs(bucket_name, filename, filename)

    audio_file = generate_download_signed_url_v4(bucket_name, filename)
    
    if skip_transcribe==False:
        transcript_id = assembly_start_transcribe(audio_file)
    
    cleaned_paragraphs = 'waiting'
    while cleaned_paragraphs == 'waiting':
        print('wait cleaned sentences')
        cleaned_paragraphs, start_times, cleaned_paragraphs_no_ads, start_times_unformatted, sentences_diarized = assembly_finish_transcribe(
            transcript_id, 
            speakers_input, 
            paragraphs,
            user
        )
        time.sleep(60)

    article, quotes, audio_filenames, audio_durations, fact_text = convert(
        user,
        cleaned_paragraphs_no_ads,
        sentences_diarized,
        speakers_input,
        filename,
        bucket_name, 
        temperature,
        presence_penalty, 
        model=model,
        prompt_end_string=prompt_end_string,
        editorial_style=editorial_style
    )

    present_sentences_timestamps = ['[' + str(start_time) + '] ' + sentence for sentence, start_time in zip(cleaned_paragraphs, start_times)]
    present_sentences_present = '<br><br>'.join(present_sentences_timestamps)

    present_summary_chunks = article.replace('\n\n', '<br><br>')
    present_top_quotes = '<br><br>'.join(quotes)

    audio_files_nonnull = [audio for audio in audio_filenames if audio is not None]

    present_audio_clips = """<audio controls><source src='https://storage.googleapis.com/writersvoice/""" + """' type='audio/mpeg'></audio><br><br><audio controls><source src='https://storage.googleapis.com/writersvoice/""".join(audio_files_nonnull) + """' type='audio/mpeg'></audio>"""
    
    tmp_email_audio_clips = ['<a href="https://storage.googleapis.com/writersvoice/' + clip + '">' + clip + '</a>' for clip in audio_files_nonnull]

    email_present_audio_clips = '<br><br>'.join(tmp_email_audio_clips)

    prompt_base = article[:int(max_tokens_output_base_model * chars_per_token)]
    title_prompt = "Here are some facts that were discussed in a podcast conversation:\n\n" + fact_text + '\n\nWrite the title of the podcast: "'
    description_prompt = prompt_base + '\n\nWrite one enticing paragraph describing the podcast:\n\nIn this podcast,'
    article_prompt = 'The first draft:\n\n' + prompt_base + '\n\nThe final draft:'

    title_response = openai.Completion.create(
        model='text-davinci-002',
        prompt=title_prompt,
        max_tokens=50,
        temperature=0.9,
        user=user,
        stop='"',
        n=3,
    )

    title_options = [
        title_response.choices[0].text,
        title_response.choices[1].text,
        title_response.choices[2].text
    ]
    title_options = list(set(title_options))

    title = '<br><br>'.join(title_options)

    description_response = openai.Completion.create(
        model='text-davinci-002',
        prompt=description_prompt,
        max_tokens=max_tokens_output,
        temperature=0.9,
        user=user,
        stop='\n',
        n=3,
    )

    description_options = [
        description_response.choices[0].text,
        description_response.choices[1].text,
        description_response.choices[2].text        
    ]

    description_options = [d.lstrip() for d in description_options]
    description_options = [d[0].upper() + d[1:] for d in description_options]

    description = '<br><br>'.join(description_options)

    if int(len(article_prompt) / chars_per_token) + max_tokens_output_article_final < max_tokens_output_base_model:
        print('article short enough for final draft')
        article_response = openai.Completion.create(
            model='text-davinci-002',
            prompt=article_prompt,
            max_tokens=max_tokens_output_article_final,
            temperature=temperature,
            user=user,
        )

        article = article_response.choices[0].text
    else:
        print('article too long for final draft')
        article = prompt_base

    article = article.replace("\n\n\n\n", "<br><br>")
    article = article.replace("\n\n", "<br><br>")
    article = article.replace("<br><br><br><br>", "<br><br>")

    print('this is article:')
    print('"' + article + '"')

    if make_memes or make_videos:

        image_audio_filenames = []
        meme_filenames = []
        num_image_audios = 0
        num_memes = 0

        image_prompts_l = [(a, b, c) for a, b, c in zip(quotes,audio_filenames,audio_durations)]
        sorted_image_prompts_l = sorted(image_prompts_l, key=lambda x: x[2], reverse=True)

        print('this is sorted image prompts')
        print(sorted_image_prompts_l)

        print('this is make_videos')
        print(make_videos)

        for top_quote, top_quote_audio_filename, audio_duration in sorted_image_prompts_l:
            print('make video filters:')
            print(make_videos)
            print(num_image_audios < num_image_audios_to_produce)
            print(top_quote_audio_filename is not None)

            if (make_videos) and (num_image_audios < num_image_audios_to_produce) and (top_quote_audio_filename is not None):
                image_audio_filename = create_video(
                    user,
                    filename,
                    num_image_audios,
                    description_options[0],
                    top_quote,
                    top_quote_audio_filename,
                    presence_penalty,
                    bucket_name,
                    visual_style,
                    fact_text
                )
                image_audio_filenames.append(image_audio_filename)
                num_image_audios += 1

            elif make_memes and (top_quote is not None):
                meme_filename = create_meme(
                    user,
                    filename,
                    num_memes,
                    description_options[0],
                    top_quote,
                    presence_penalty,
                    bucket_name,
                    visual_style,
                    fact_text                
                )
                meme_filenames.append(meme_filename)
                num_memes += 1            

    present_image_audio_clips=''
    email_present_image_audio_clips=''
    video_clips_html = ''
    if make_videos:
        image_audio_filenames = [image_audio_filename for image_audio_filename in image_audio_filenames if image_audio_filename is not None]
        present_image_audio_clips = """<video controls><source src='https://storage.googleapis.com/writersvoice/""" + """' type='video/mp4'></video><br><br><video controls><source src='https://storage.googleapis.com/writersvoice/""".join(image_audio_filenames) + """' type='video/mp4'></video>"""
        tmp_email_image_audio_clips = ['<a href="https://storage.googleapis.com/writersvoice/' + clip + '">' + clip + '</a>' for clip in image_audio_filenames]    
        email_present_image_audio_clips = '<br><br>'.join(tmp_email_image_audio_clips)
        video_clips_html = """<br><a href="#video">Video Clips</a>"""

    present_memes = ''
    email_present_memes = ''
    memes_html = ''
    if make_memes:
        present_memes = """<img src='https://storage.googleapis.com/writersvoice/""" + """'><br><br><img src='https://storage.googleapis.com/writersvoice/""".join(meme_filenames) + """'>"""
        tmp_email_memes = ['<a href="https://storage.googleapis.com/writersvoice/' + meme + '">' + meme + '</a>' for meme in meme_filenames]    
        email_present_memes = '<br><br>'.join(tmp_email_memes)
        memes_html = """<br><a href="#images">Quote Memes</a>"""

    combined_base = """<br><br><b>Result Sections</b>""" \
    + """<br><a href="#title_suggestions">Title Suggestions</a>""" \
    + """<br><a href="#description_suggestions">Description Suggestions</a>""" \
    + """<br><a href="#blog_post">Blog Post</a>""" \
    + """<br><a href="#top_quotes">Top Quotes</a>""" \
    + """<br><a href="#audio">Audio Clips</a>""" \
    + video_clips_html \
    + memes_html \
    + """<br><a href="#transcript">Transcript</a>""" \
    + """<br><br><b><a id="title_suggestions">Title Suggestions</a></b><br><br>""" + title \
    + """<br><br><b><a id="description_suggestions">Description Suggestions</a></b><br><br>""" + description \
    + """<br><br><b><a id="blog_post">Blog Post</a></b>""" + article \
    + """<br><br><b><a id="top_quotes">Top Quotes</a></b><br><br>""" + present_top_quotes

    combined_email = combined_base + """<br><br><b><a id="audio">Audio Clips</a></b><br><br>""" + email_present_audio_clips \
    + """<br><br><b><a id="video">Video Clips</a></b><br><br>""" + email_present_image_audio_clips \
    + """<br><br><b><a id="images">Images</a></b><br><br>""" + email_present_memes \
    + """<br><br><b><a id="transcript">Transcript</a></b><br><br>""" + present_sentences_present
    
    combined_html = combined_base + """<br><br><b><a id="audio">Audio Clips</a></b><br><br>""" + present_audio_clips \
    + """<br><br><b><a id="video">Video Clips</a></b><br><br>""" + present_image_audio_clips \
    + """<br><br><b><a id="images">Quote Memes</a></b><br><br>""" + present_memes \
    + """<br><br><b><a id="transcript">Transcript</a></b><br><br>""" + present_sentences_present


    response = requests.\
        post("https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN,
            auth=("api", MAILGUN_API_KEY),
             data={
                 "from": 'dubb@'+ str(MAILGUN_DOMAIN),
                 "to": str(MAIL_USERNAME), ## to be updated to email
                 "subject": "Dubb results",
                 "text": '<b>TO BE REMOVED: </b>' + user + '<b>TO BE REMOVED</b>' + combined_email,
                 "html": '<b>TO BE REMOVED: </b>' + user + '<b>TO BE REMOVED</b>' + combined_email
             }
         )

    response = requests.\
        post("https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN,
            auth=("api", MAILGUN_API_KEY),
             data={
                 "from": 'dubb@'+ str(MAILGUN_DOMAIN),
                 "to": user, ## to be updated to email
                 "subject": "Dubb results",
                 "text": combined_email,
                 "html": combined_email
             }
         )
    
    return combined_html, user
    

def present_article(article):
    print('\n\n'.join([x for x in article.split('\n') if x not in ['', ' ']])) 
    

def get_transcript(
    url,
    speakers_input, 
    filename,
    user,
    bucket_name='writersvoice', 
    skip_upload=False,
    skip_transcribe=False,
    transcript_id='',
    write=False,
    write_title='',
    paragraphs=False,
    for_transcript=True):   
    
    if skip_upload==False:
        download_yt(url, filename)
        upload_to_gs(bucket_name, filename, filename)
    
    if skip_transcribe==False:
        audio_file = generate_download_signed_url_v4(bucket_name, filename)
        transcript_id = assembly_start_transcribe(audio_file)
    
    cleaned_paragraphs = 'waiting'
    while cleaned_paragraphs == 'waiting':
        print('wait cleaned sentences')
        cleaned_paragraphs, start_times, cleaned_paragraphs_no_ads, start_times_unformatted, sentences_diarized = assembly_finish_transcribe(
            transcript_id, 
            speakers_input, 
            paragraphs,
            user
        )
        time.sleep(10)
        
    prompt_chunks = split_transcript(cleaned_paragraphs, for_transcript=for_transcript)

    for prompt in prompt_chunks:
        print(prompt)
    
    if write == True:
        ## TODO: the below should be updated
        file1 = open('transcript_2022_02_07/' + write_title + ".txt","w")
        file1.writelines(prompt_chunks)
        file1.close()

    return prompt_chunks