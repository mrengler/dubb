from __future__ import absolute_import

# token values for gpt3 context window
max_token_input = 3000
max_tokens_output = 1000
max_tokens_facts_quotes = 500
max_tokens_output_base_model = 4097
max_tokens_output_is_ad = 10
max_tokens_output_image_description = 120
max_tokens_output_article_final = 2000

# rough approximation of string characters per token 
chars_per_token = 3.55

# max audio and video clips to produce
num_audios_to_produce = 5
num_videos_to_produce = 3

# constants for video creation
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
REPLICATE_ANIMATION_MODEL = os.environ.get('REPLICATE_ANIMATION_MODEL')
REPLICATE_MEME_MODEL = os.environ.get('REPLICATE_MEME_MODEL')
MAILGUN_API_KEY = os.environ["MAILGUN_API_KEY"]
MAILGUN_DOMAIN = os.environ["MAILGUN_DOMAIN"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]


# formatting timestamps
def millsecond_to_timestamp(ms):
    millis = int(ms)
    seconds=(millis/1000)%60
    seconds = int(seconds)
    minutes=(millis/(1000*60))%60
    minutes = int(minutes)
    hours=(millis/(1000*60*60))%24
    hours=int(hours)

    return "%d:%02d:%02d" % (hours, minutes, seconds)

# download the audio of a url (google podcasts or youtube)
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

# upload a file to Google Cloud
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

# download a file from Google Cloud
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

# signed url for downloading
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

# call transcription api with audio file
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

# retrieve transcription and format
def assembly_finish_transcribe(transcript_id, speakers_input, paragraphs, user):

    endpoint_transcript = "https://api.assemblyai.com/v2/transcript/" + transcript_id + '/sentences'
    endpoint_srt = "https://api.assemblyai.com/v2/transcript/" + transcript_id + '/srt'

    headers = {
        "authorization": ASSEMBLY_API_KEY,
    }

    # get the transcript response from assemblyAI
    response_transcript = requests.get(endpoint_transcript, headers=headers)
    response_transcript_json = response_transcript.json()

    print('this is response')
    print(response_transcript)
    print(response_transcript_json)

    # check if the transcript is done
    if 'sentences' in response_transcript_json:
    
        sentences = response_transcript.json()['sentences']
        sentences_diarized = [(sentence['words'][0]['speaker'], sentence['text'], millsecond_to_timestamp(sentence['start']), sentence['start']) for sentence in sentences]
        speakers_duplicate = [speaker for speaker, sentence, start_time, start_time_unformatted in sentences_diarized]
        unique_speakers = list(dict.fromkeys(speakers_duplicate))

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
                if (speaker != current_speaker) or (num_sentences_used >= max_num_sentences):
                    if current_speaker != '':
                        current_speaker_sentences_joined = current_speaker + ": " + " ".join(current_speaker_sentences)
                        cleaned_paragraphs.append(current_speaker_sentences_joined)

                        '''
                        The following code filters ads, but I commented it out because it was causing 
                        too many calls to openai api and delaying results. It would be valuable to have
                        back though because sometimes ads contaminate results.  
                        '''

                        # ## filter ads
                        # ad_prompt = 'The transcript:\n\n' + '[' + str(start_time) + '] ' + current_speaker_sentences_joined + '\n\nIs this the transcript of an ad? Respond with either "yes" or "no".'
                        # print(ad_prompt)
                        # is_ad_response = openai.Completion.create(
                        #     model='text-davinci-003',
                        #     prompt=ad_prompt,
                        #     max_tokens=max_tokens_output_is_ad,
                        #     temperature=0.0,
                        #     user=user,
                        # )

                        # is_ad_response = is_ad_response.choices[0].text
                        # print(is_ad_response)
                        # is_ad_response = is_ad_response.lower()

                        # ## filter promos
                        # promo_prompt = 'The transcript:\n\n' + '[' + str(start_time) + '] ' + current_speaker_sentences_joined + '\n\nIs this the transcript of a promotion for another podcast? Respond with either "yes" or "no".'
                        # print(promo_prompt)
                        # is_promo_response = openai.Completion.create(
                        #     model='text-davinci-003',
                        #     prompt=promo_prompt,
                        #     max_tokens=max_tokens_output_is_ad,
                        #     temperature=0.0,
                        #     user=user,
                        # )

                        # is_promo_response = is_promo_response.choices[0].text
                        # print(is_promo_response)
                        # is_promo_response = is_promo_response.lower()

                        # if ('no' in is_ad_response) and ('no' in is_promo_response):
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

            # ## filter ads
            # ad_prompt = 'The transcript:\n\n' + '[' + str(start_time) + '] ' + current_speaker_sentences_joined + '\n\nIs this the transcript of an ad? Respond with either "yes" or "no".'
            # print(ad_prompt)
            # is_ad_response = openai.Completion.create(
            #     model='text-davinci-003',
            #     prompt=ad_prompt,
            #     max_tokens=max_tokens_output_is_ad,
            #     temperature=0.0,
            #     user=user,
            # )

            # is_ad_response = is_ad_response.choices[0].text
            # print(is_ad_response)
            # is_ad_response = is_ad_response.lower()

            # ## filter promos
            # promo_prompt = 'The transcript:\n\n' + '[' + str(start_time) + '] ' + current_speaker_sentences_joined + '\n\nIs this the transcript of a promotion for another podcast? Respond with either "yes" or "no".'
            # print(promo_prompt)
            # is_promo_response = openai.Completion.create(
            #     model='text-davinci-003',
            #     prompt=promo_prompt,
            #     max_tokens=max_tokens_output_is_ad,
            #     temperature=0.0,
            #     user=user,
            # )

            # is_promo_response = is_promo_response.choices[0].text
            # print(is_promo_response)
            # is_promo_response = is_promo_response.lower()

            # if ('no' in is_ad_response) and ('no' in is_promo_response):
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

                find_speaker_input = '\n\n'.join(window)
                ## reduce to fit into model window
                buffer = 250
                find_speaker_input = find_speaker_input[:int((max_tokens_output_base_model - buffer) * chars_per_token)]

                choose_pre = """The transcript:\n\n"""
                choose_post = """\n\n\nWhat is Speaker """ + unique_speaker + """'s name?:\n\nSpeaker """ + unique_speaker + ' is "'
                choose_text = choose_pre + find_speaker_input + choose_post
                print('This is choose_text for Speaker ' + unique_speaker)
                print(choose_text)
                tries = 3
                try_i = 0
                success = ''

                while ((try_i < tries) and (success == '')):
                    try:
                        choose = openai.Completion.create(
                                    model='text-davinci-003',
                                    prompt=choose_text,
                                    max_tokens=20,
                                    temperature=0.9,
                                    presence_penalty=0.0,
                                    user=user,
                                    stop='"',
                                )
                        success = 'success'
                    except:
                        try_i += 1
                        time.sleep(10)

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

            # get SRT file
            response_srt = requests.get(endpoint_srt, headers=headers)
            f = open(transcript_id + ".srt", "w")
            f.write(response_srt.content.decode("utf-8"))
            f.close()    

            return cleaned_paragraphs, start_times, cleaned_paragraphs_no_ads, start_times_unformatted, sentences_diarized

    elif 'error' in response_transcript_json:
        ## transcript is still processing
        if response_transcript_json['error'] == "This transcript has a status of 'processing'. Transcripts must have a status of 'completed' before requesting captions.":
            return 'waiting', None, None, None, None
        # error
        elif response_transcript_json['error'] == "This transcript has a status of 'error'. Transcripts must have a status of 'completed' before requesting captions.":
            return 'error', None, None, None, None   
    else:
        return 'error', None, None, None, None

# split transcript into context window chunks
def split_transcript(cleaned_paragraphs, for_transcript, prompt_end_string=''):
        
    prompt_chunks = []
    num_chars = max_token_input * chars_per_token
    used_chars = 0
    chunk = []
    chunk_i = 0
    
    for sentence in cleaned_paragraphs:
        sentence_chars = len([char for char in sentence])
        # keep adding text chunks while still under the context window length
        if used_chars + sentence_chars <= num_chars:
            chunk.append(sentence)
            used_chars += sentence_chars
        #start a new batch    
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

# openai content filter    
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

# get length of audio
def get_length(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return float(result.stdout)

# split text for text overlays on memes
# from https://stackoverflow.com/questions/50628267/ffmpeg-creating-video-using-drawtext-along-with-word-wrap-and-padding
def split_txt_into_multi_lines(input_str, line_length):
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

# create animated video from the audio file
def create_video(
    user,
    filename,
    transcript_id,
    num_videos,
    description,
    top_quote,
    top_quote_audio_filename,
    audio_start_time,
    pres_penalty,
    bucket_name,
    visual_style,
    fact_text
    ):

    replicate_model = replicate.models.get(REPLICATE_ANIMATION_MODEL)

    # set prompt text for the style that the user chose
    if visual_style == 'low_poly':
        object_text = 'Concept art of '
        style_text = 'low poly'
    elif visual_style == 'painting':
        object_text = 'A digital illustration of '
        style_text = 'by edward hopper'
    elif visual_style == 'spooky':
        object_text = 'A digital illustration of '
        style_text = 'by zdzis??aw beksi??ski, dark surrealism'

    print('this is first prompt:')

    prompt_text_pre = "Here are some facts that were discussed in a podcast episode:\n\n" + fact_text +\
    '\n\nHere is the top quote from the podcast episode:\n\n"' + top_quote + '"\n\nUse the top quote and facts to write a description of the image that accompanies the podcast episode:\n\nThe image does not contain any words, quotes, dates, or logos. The image features'

    print(prompt_text_pre)

    tries = 3
    try_i = 0
    success = ''

    while ((try_i < tries) and (success == '')):
        try:
            # generate descriptions of the animation
            top_quote_image_description_response_pre = openai.Completion.create(
                model='text-davinci-003',
                prompt=prompt_text_pre,
                max_tokens=max_tokens_output_image_description,
                temperature=0.8,
                presence_penalty=pres_penalty,
                user=user,
                n=3
            )
            success = 'success'
        except:
            try_i += 1
            time.sleep(10)

    # get the three different image descriptions
    top_quote_image_description_pre_one = top_quote_image_description_response_pre.choices[0].text
    top_quote_image_description_pre_two = top_quote_image_description_response_pre.choices[1].text
    top_quote_image_description_pre_three = top_quote_image_description_response_pre.choices[2].text

    top_quote_image_description_classifications = []
    top_quote_image_descriptions = []
    for top_quote_image_description_pre in [top_quote_image_description_pre_one, top_quote_image_description_pre_two, top_quote_image_description_pre_three]:

        # formatting for each description
        top_quote_image_description_pre = top_quote_image_description_pre.replace(':', '')
        top_quote_image_description_pre = top_quote_image_description_pre.lstrip()

        prompt_text = 'The description of the image:\n\n' + top_quote_image_description_pre + '\n\nEdit the description of the image so that it only contains physical details:\n\nThe image features'

        print(prompt_text)

        tries = 3
        try_i = 0
        success = ''

        # edit each description to remove things that aren't physical details 
        while ((try_i < tries) and (success == '')):
            try:

                top_quote_image_description_response = openai.Completion.create(
                    model='text-davinci-003',
                    prompt=prompt_text,
                    max_tokens=max_tokens_output_image_description,
                    temperature=1.0,
                    presence_penalty=pres_penalty,
                    user=user,
                )
                success = 'success'
            except:
                try_i += 1
                time.sleep(10)

        top_quote_image_description = top_quote_image_description_response.choices[0].text

        ## get the content classification
        top_quote_image_description_classification = content_filter(top_quote_image_description, user)
        top_quote_image_description_classifications.append(top_quote_image_description_classification)

        top_quote_image_description = top_quote_image_description.replace(':', '')
        top_quote_image_description = top_quote_image_description.replace('"', '')
        top_quote_image_description = top_quote_image_description.replace('\n\n', '')
        top_quote_image_description = top_quote_image_description.lstrip()    

        print("top_quote_image_description")
        print(top_quote_image_description)

        ## make once sentence, all lowercase
        top_quote_image_description = top_quote_image_description.replace('.', ',').replace('!', ',').replace('?', ',').lower()
        top_quote_image_descriptions.append(top_quote_image_description)

    if '2' not in top_quote_image_description_classifications: ##2 is unsafe

        # get the animation from replicate
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

        # generate a random string to assign the clip in the data
        random_str = ''.join(random.choices(string.ascii_lowercase, k=5))

        ##download from replicate
        image_filename = filename.split('.')[0] + '_image_' + str(num_videos) + random_str + ".mp4"
        response = requests.get(src)
        open(image_filename, "wb").write(response.content)

        ##slow looped animation
        slow_multiple = 1.25
        slowed_image_filename = filename.split('.')[0] + '_slowed_' + str(num_videos) + random_str + ".mp4"
        os.system("""ffmpeg -i """ + image_filename + """ -vf  "setpts=""" + str(slow_multiple) + """*PTS" """ + slowed_image_filename)

        ##get length and multipliers
        l = get_length(image_filename) * slow_multiple
        fps_full = l * double * frame_rate
        desired_length = get_length(top_quote_audio_filename)
        multiplier = desired_length / (l * 2)
        loop = math.ceil(multiplier)

        ##make looped animation
        image_looped_filename = filename.split('.')[0] + '_looped_' + str(num_videos) + random_str + ".mp4"
        os.system("""ffmpeg -i """ + slowed_image_filename + """ -filter_complex "[0]reverse[r];[0][r]concat,loop=""" + str(loop) + """:""" + str(fps_full) + """  " """ + image_looped_filename)

        ###join looped animation with audio
        image_audio_filename = filename.split('.')[0] + '_video_' + str(num_videos) + random_str + ".mp4"
        tmp_image_audio_filename = 'tmp_' + image_audio_filename
        os.system("""ffmpeg -i """ + image_looped_filename + """ -i """ + top_quote_audio_filename + """ -c:v copy -c:a aac """ + tmp_image_audio_filename)
        
        ##trim end of video
        os.system("""ffmpeg -i """ + tmp_image_audio_filename + """ -ss 00:00:00 -t """ + millsecond_to_timestamp(math.ceil(desired_length) * 1000) + """ """ + image_audio_filename)

        # make srt file that starts at beginning of video
        shifted_srt_filename = transcript_id + "_" + random_str + ".srt"
        os.system("""ffmpeg -ss """ + str(audio_start_time / 1000) + """ -i """ + transcript_id + """.srt -c copy """ + shifted_srt_filename)
        upload_to_gs(bucket_name, shifted_srt_filename, shifted_srt_filename)

        # get video with subtitles
        image_audio_subtitles_filename = filename.split('.')[0] + '_video_' + str(num_videos) + random_str + "_subtitles.mp4"
        os.system("""ffmpeg -i """ + image_audio_filename + """ -vf "subtitles=""" + shifted_srt_filename + """:force_style='Fontname=Roboto,OutlineColour=&H40000000,BorderStyle=3'" """ + image_audio_subtitles_filename)

        ## save videos to google cloud
        upload_to_gs(bucket_name, image_audio_filename, image_audio_filename)
        upload_to_gs(bucket_name, image_audio_subtitles_filename, image_audio_subtitles_filename)

        return image_audio_filename, image_audio_subtitles_filename

# create meme of top quote
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

    replicate_model = replicate.models.get(REPLICATE_MEME_MODEL)

    # set prompt text for the style that the user chose
    if visual_style == 'low_poly':
        object_text = 'Concept art of '
        style_text = 'low poly'
    elif visual_style == 'painting':
        object_text = 'A digital illustration of '
        style_text = 'by edward hopper'
    elif visual_style == 'spooky':
        object_text = 'A digital illustration of '
        style_text = 'by zdzis??aw beksi??ski, dark surrealism'

    prompt_text = "Here are some facts that were discussed in a podcast episode:\n\n" + fact_text +\
    '\n\nHere is the top quote from the podcast episode:\n\n"' + top_quote + '"\n\nUse the top quote and facts to write a description of the image that accompanies the podcast episode:\n\nThe image does not contain any words, quotes, dates, or logos. The image features'

    print(prompt_text)

    # generate descriptions of the image
    top_quote_image_description_response = openai.Completion.create(
        model='text-davinci-003',
        prompt=prompt_text,
        max_tokens=max_tokens_output_image_description,
        temperature=0.0,
        presence_penalty=pres_penalty,
        user=user,
    )

    top_quote_image_description = top_quote_image_description_response.choices[0].text

    # get the classification
    top_quote_image_description_classification = content_filter(top_quote_image_description, user)

    # format the description
    top_quote_image_description = top_quote_image_description.replace(':', '')
    top_quote_image_description = top_quote_image_description.lstrip()

    # make once sentence, all lowercase
    top_quote_image_description = top_quote_image_description.replace('.', ',').replace('!', ',').replace('?', ',').lower()

    print("top_quote_image_description")
    print(top_quote_image_description)

    if (top_quote_image_description_classification != '2'):
        # get the image from replicate 
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

        # download from replicate
        random_str = ''.join(random.choices(string.ascii_lowercase, k=5))
        image_filename = filename.split('.')[0] + '_imagenomovie_' + str(num_memes) + random_str + ".png"
        response = requests.get(src)
        open(image_filename, "wb").write(response.content)

        # add text on top
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
        top_quote = top_quote.replace(',', '\\,')
        top_quote = top_quote.replace(':', '')
        top_quote = re.escape(top_quote)
        print('this is os.system')
        print("""ffmpeg -i """ + image_filename + """ -vf "drawtext=text='""" + split_txt_into_multi_lines(top_quote, line_length) + """':bordercolor=black:borderw=3:fontcolor=white:fontsize=""" + str(fontsize) + """:x=""" + str(w_padding) + """:y=""" + str(h_padding) + """:" """ + meme_filename)
        os.system("""ffmpeg -i """ + image_filename + """ -vf "drawtext=text='""" + split_txt_into_multi_lines(top_quote, line_length) + """':bordercolor=black:borderw=3:fontcolor=white:fontsize=""" + str(fontsize) + """:x=""" + str(w_padding) + """:y=""" + str(h_padding) + """:" """ + meme_filename)

        # save to google cloud
        upload_to_gs(bucket_name, meme_filename, meme_filename)

        return meme_filename

# turn transcript into article, audio clips, top quotes
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

    num_audios = 0

    audio_filenames = []
    audio_start_times = []
    audio_durations = []
    audio_quotes = []
    facts = []
    quotes = []

    # arrays from the transcript
    start_times_unformatted = [timestamp for (_, _, _, timestamp) in sentences_diarized]
    sentences_unformatted = [sentence for (_,sentence,_,_) in sentences_diarized]
    # split the transcript into chunks that fit in the gpt3 context window
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
        tries = 3
        try_i = 0
        success = ''

        while ((try_i < tries) and (success == '')):
            try:
                print('this is prompt_chunk')
                print(prompt_chunk)

                fact_prompt_chunk = top_facts_prompt_pre + prompt_chunk + top_facts_prompt_post
                quote_prompt_chunk = top_quotes_prompt_pre + prompt_chunk + top_quotes_prompt_post

                print(fact_prompt_chunk)

                print(quote_prompt_chunk)

                ## get top facts from that chunk
                r_fact = openai.Completion.create(
                        model='text-davinci-003',
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
                
                ## get top quotes from that chunk
                r_quote = openai.Completion.create(
                        model='text-davinci-003',
                        prompt=quote_prompt_chunk,
                        max_tokens=max_tokens_facts_quotes,
                        temperature=0.8,
                        presence_penalty=pres_penalty,
                        user=user,
                        stop='"',
                        n=3,
                    )
                # TODO abstract this for loop so that it takes however many outputs are given
                quote_options = [
                    r_quote.choices[0].text,
                    r_quote.choices[1].text,
                    r_quote.choices[2].text
                ]
                quote_options = list(set(quote_options))

                for quote in quote_options:
                    # fix common problems in the top quote
                    quote = quote.replace("The full transcript:\n\n", '')
                    quote = quote.replace("The full transcript: ", '')
                    quote = quote.replace("The full transcript:", '')
                    # remove speakers from top quotes
                    for speaker in speakers_input + ['Unknown']:
                        quote = quote.replace(speaker + ": ", '')
                    # check if quote is 1 paragraph and not empty
                    if (len(quote.split('\n\n')) == 1) and (quote != ""):
                        # check that it's a verbatim quote
                        if quote in prompt_chunk:
                            quote_classification = content_filter(quote, user)
                            # check that it's not unsafe
                            if quote_classification  != '2':
                                quotes.append(quote)

                                # generate audiograms
                                if num_audios < num_audios_to_produce:
                                    print('this is debug section')
                                    print("'" + quote + "'")
                                    # try:

                                    top_quote_split = re.split('\n\n|(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', quote)
                                    print('this is top_quote_split')
                                    print(top_quote_split)

                                    # use a different start sentence if the first or last are too short
                                    off_index_start = 0
                                    for sentence in top_quote_split:
                                        if len(sentence) >= 10:
                                            break
                                        else:
                                            off_index_start += 1

                                    # use a different end sentence if the first or last are too short        
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

                                    # find quote audio start time, end time, duration
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
                                    try:
                                        top_quote_audio = AudioSegment.from_file(filename, format='mp3', start_second=tq_start / 1000, duration=tq_duration)
                                    except:
                                        top_quote_audio = AudioSegment.from_file(filename, start_second=tq_start / 1000, duration=tq_duration)
                                    top_quote_audio_filename = filename.split('.')[0] + str(tq_start) + "_" + str(tq_end) + ".mp3"
                                    print(top_quote_audio_filename)
                                    top_quote_audio.export(top_quote_audio_filename, format="mp3")
                                    audio_filenames.append(top_quote_audio_filename)
                                    audio_start_times.append(tq_start)
                                    audio_durations.append(tq_duration)
                                    audio_quotes.append(quote)
                                    # save to google cloud
                                    upload_to_gs(bucket_name, top_quote_audio_filename, top_quote_audio_filename)
                                    num_audios += 1
                            else:
                                print('quote classification == 2')
                                print(quote)
                        else:
                            print('quote is not verbatim from the text')
                            print(quote)
                    else:
                        print("quote is multiple paragraphs or quote == ''")
                        print(quote)

                success = 'success'

            except:
                try_i += 1
                time.sleep(10)



    # combine top facts
    num_facts = min(50, len(facts))
    facts_sample = [
        facts[i] for i in sorted(random.sample(range(len(facts)), num_facts))
    ]
    fact_text = """"""
    for i, r in enumerate(facts_sample):
        fact_text += str(i + 1) + ': ' + r + "\n"

    # combine top quotes
    num_quotes = min(5, len(quotes))
    quotes_sample = [
        quotes[i] for i in sorted(random.sample(range(len(quotes)), num_quotes))
    ]
    quote_text = """"""
    for i, r in enumerate(quotes_sample):
        quote_text += str(i + 1) + ': "' + r + '"\n'

    # set prompt text for the style that the user chose
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
    
    tries = 3
    try_i = 0
    success = ''

    while ((try_i < tries) and (success == '')):
        try:   
            ## generate blog post
            r = openai.Completion.create(
                        model='text-davinci-003',
                        prompt=article_prompt,
                        max_tokens=max_tokens_output,
                        temperature=temp,
                        presence_penalty=pres_penalty,
                        user=user,
                        n=5,
                    )
            success = 'success'
        except:
            try_i += 1
            time.sleep(10)

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
    
    tries = 3
    try_i = 0
    success = ''

    while ((try_i < tries) and (success == '')):
        try:   
            # choose the version of the article that is best
            choose = openai.Completion.create(
                        model='text-davinci-003',
                        prompt=choose_text,
                        max_tokens=20,
                        temperature=0.0,
                        presence_penalty=pres_penalty,
                        user=user,
                    )
            success = 'success'
        except:
            try_i += 1
            time.sleep(10)

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

    return article, quotes, audio_filenames, audio_start_times, audio_durations, audio_quotes, fact_text

# handle audio to all outputs
def run_combined(
    content,
    content_type,
    user, 
    speakers_input, 
    filename,
    model,
    # db,
    bucket_name='writersvoice', 
    temperature=0.8, 
    presence_penalty=0.0, 
    prompt_end_string="",
    skip_upload=False,
    skip_transcribe=False,
    transcript_id='',
    paragraphs=True,
    make_videos=True,
    make_memes=False,
    visual_style='painting',
    editorial_style='insightful'
    ):

    try:
        if skip_upload==False:
            if content_type=='url':
                # if url submission, download the audio
                status = download_yt(content, filename)
                # if audio download fails, send an error email
                if status == 'failed':
                    print('return failed')
                    response = requests.\
                    post("https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN,
                        auth=("api", MAILGUN_API_KEY),
                         data={
                             "from": 'results@'+ str(MAILGUN_DOMAIN),
                             "to": str(MAIL_USERNAME), ## to be updated to email
                             "subject": "Dubb results",
                             "text": '<b>YOUTUBEDL ERROR: </b>' + user + ' Details: ' + filename + ' ' + transcript_id,
                             "html": '<b>YOUTUBEDL ERROR: </b>' + user + ' Details: ' + filename + ' ' + transcript_id
                         }
                     )
                    return ">There was an error. Sorry about that. We will fix it as soon as possible!", user, True
                elif status == 'passed':
                    # save to google cloud
                    upload_to_gs(bucket_name, filename, filename)
            # if user input is a file, it was already uploaded in app.py, download it here
            elif content_type=='file':
                download_from_gs(bucket_name, filename, filename)

        # make a signed url for sending to assemblyAI for transcription
        audio_file = generate_download_signed_url_v4(bucket_name, filename)
        
        if skip_transcribe==False:
            # send for transcription
            transcript_id = assembly_start_transcribe(audio_file)
        
        # wait for transcription to complete
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

        ## transcription error
        if cleaned_paragraphs == 'error':
            response = requests.\
                post("https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN,
                    auth=("api", MAILGUN_API_KEY),
                     data={
                         "from": 'results@'+ str(MAILGUN_DOMAIN),
                         "to": str(MAIL_USERNAME), ## to be updated to email
                         "subject": "Dubb results",
                         "text": '<b>TRANSCRIPTION ERROR: </b>' + user + ' Details: ' + filename + ' ' + transcript_id,
                         "html": '<b>TRANSCRIPTION ERROR: </b>' + user + ' Details: ' + filename + ' ' + transcript_id
                     }
                 )
            return '>There was an error. Sorry about that. We will fix it as soon as possible!', user, True

        # send transcript for processing into blog post, top quotes, audiograms
        article, quotes, audio_filenames, audio_start_times, audio_durations, audio_quotes, fact_text = convert(
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

        # format the outputs for html readability 
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

        # generate titles        
        tries = 3
        try_i = 0
        success = ''

        while ((try_i < tries) and (success == '')):
            try:

                title_response = openai.Completion.create(
                    model='text-davinci-003',
                    prompt=title_prompt,
                    max_tokens=50,
                    temperature=0.9,
                    user=user,
                    stop='"',
                    n=3,
                )
                success = 'success'
            except:
                try_i += 1
                time.sleep(10)            

        title_options = [
            title_response.choices[0].text,
            title_response.choices[1].text,
            title_response.choices[2].text
        ]
        title_options = list(set(title_options))

        title = '<br><br>'.join(title_options)

        # generate descriptions
        tries = 3
        try_i = 0
        success = ''

        while ((try_i < tries) and (success == '')):
            try:
                description_response = openai.Completion.create(
                    model='text-davinci-003',
                    prompt=description_prompt,
                    max_tokens=max_tokens_output,
                    temperature=0.9,
                    user=user,
                    stop='\n',
                    n=3,
                )
                success = 'success'
            except:
                try_i += 1
                time.sleep(10)   

        description_options = [
            description_response.choices[0].text,
            description_response.choices[1].text,
            description_response.choices[2].text        
        ]

        description_options = [d.lstrip() for d in description_options]
        description_options = [d[0].upper() + d[1:] for d in description_options]

        description = '<br><br>'.join(description_options)

        # do editing on the article if it's short enough
        if int(len(article_prompt) / chars_per_token) + max_tokens_output_article_final < max_tokens_output_base_model:
            print('article short enough for final draft')
            print(article_prompt)

            tries = 3
            try_i = 0
            success = ''

            while ((try_i < tries) and (success == '')):
                try:

                    article_response = openai.Completion.create(
                        model='text-davinci-003',
                        prompt=article_prompt,
                        max_tokens=max_tokens_output_article_final,
                        temperature=temperature,
                        user=user,
                    )
                    success = 'success'
                except:
                    try_i += 1
                    time.sleep(10)      


            article = article_response.choices[0].text
        else:
            print('article too long for final draft')
            article = prompt_base

        article = article.replace("\n\n\n\n", "<br><br>")
        article = article.replace("\n\n", "<br><br>")
        article = article.replace("<br><br><br><br>", "<br><br>")

        print('this is article:')
        print('"' + article + '"')

        # make videos and/or memes
        if make_memes or make_videos:

            image_audio_filenames = []
            image_audio_subtitles_filenames = []
            meme_filenames = []
            num_videos = 0
            num_memes = 0

            # rearrange quotes, audio files, and durations for use in making videos and memes
            image_prompts_l = [(a, b, c, d) for a, b, c,d in zip(audio_quotes,audio_filenames,audio_start_times,audio_durations)]
            sorted_image_prompts_l = sorted(image_prompts_l, key=lambda x: x[3], reverse=True)

            print('this is sorted image prompts')
            print(sorted_image_prompts_l)

            print('this is make_videos')
            print(make_videos)

            for top_quote, top_quote_audio_filename, audio_start_time, audio_duration in sorted_image_prompts_l:
                print('make video filters:')
                print(make_videos)
                print(num_videos < num_videos_to_produce)
                print(top_quote_audio_filename is not None)

                if (make_videos) and (num_videos < num_videos_to_produce) and (top_quote_audio_filename is not None):
                    # generate video
                    image_audio_filename, image_audio_subtitles_filename = create_video(
                        user,
                        filename,
                        transcript_id,
                        num_videos,
                        description_options[0],
                        top_quote,
                        top_quote_audio_filename,
                        audio_start_time,
                        presence_penalty,
                        bucket_name,
                        visual_style,
                        fact_text
                    )
                    image_audio_filenames.append(image_audio_filename)
                    image_audio_subtitles_filenames.append(image_audio_subtitles_filename)
                    num_videos += 1

                # if maximum number of videos have been made, make memes instead
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

        # format video and meme output
        present_image_audio_clips=''
        email_present_image_audio_clips=''
        video_clips_html = ''
        video_subtitles_clips_html = ''
        if make_videos:
            image_audio_filenames = [image_audio_filename for image_audio_filename in image_audio_filenames if image_audio_filename is not None]
            present_image_audio_clips = """<br><br><b><a id="video">Video Clips</a></b><br><br>""" + """<video controls><source src='https://storage.googleapis.com/writersvoice/""" + """' type='video/mp4'></video><br><br><video controls><source src='https://storage.googleapis.com/writersvoice/""".join(image_audio_filenames) + """' type='video/mp4'></video>"""
            tmp_email_image_audio_clips = ['<a href="https://storage.googleapis.com/writersvoice/' + clip + '">' + clip + '</a>' for clip in image_audio_filenames]    
            email_present_image_audio_clips = """<br><br><b><a id="video">Video Clips</a></b><br><br>""" + '<br><br>'.join(tmp_email_image_audio_clips)
            video_clips_html = """<br><a href="#video">Video Clips</a>"""
            
            image_audio_subtitles_filenames = [image_audio_subtitles for image_audio_subtitles in image_audio_subtitles_filenames if image_audio_subtitles_filename is not None]
            present_image_audio_subtitles_clips = """<br><br><b><a id="video_subtitles">Video Clips with subtitles</a></b><br><br>""" + """<video controls><source src='https://storage.googleapis.com/writersvoice/""" + """' type='video/mp4'></video><br><br><video controls><source src='https://storage.googleapis.com/writersvoice/""".join(image_audio_subtitles_filenames) + """' type='video/mp4'></video>"""
            tmp_email_image_audio_subtitles_clips = ['<a href="https://storage.googleapis.com/writersvoice/' + clip + '">' + clip + '</a>' for clip in image_audio_subtitles_filenames]    
            email_present_image_audio_subtitles_clips = """<br><br><b><a id="video_subtitles">Video Clips with subtitles</a></b><br><br>""" + '<br><br>'.join(tmp_email_image_audio_subtitles_clips)
            video_subtitles_clips_html = """<br><a href="#video">Video Clips with subtitles</a>"""

        present_memes = ''
        email_present_memes = ''
        memes_html = ''
        if make_memes:
            present_memes = """<br><br><b><a id="images">Quote Memes</a></b><br><br>""" + """<img src='https://storage.googleapis.com/writersvoice/""" + """'><br><br><img src='https://storage.googleapis.com/writersvoice/""".join(meme_filenames) + """'>"""
            tmp_email_memes = ['<a href="https://storage.googleapis.com/writersvoice/' + meme + '">' + meme + '</a>' for meme in meme_filenames]    
            email_present_memes = """<br><br><b><a id="images">Images</a></b><br><br>""" + '<br><br>'.join(tmp_email_memes)
            memes_html = """<br><a href="#images">Quote Memes</a>"""

        # format web and email response
        combined_base = """<br><br>File: """ + content\
        + """<br><br><b>Result Sections</b>""" \
        + """<br><a href="#title_suggestions">Title Suggestions</a>""" \
        + """<br><a href="#description_suggestions">Description Suggestions</a>""" \
        + """<br><a href="#blog_post">Blog Post</a>""" \
        + """<br><a href="#top_quotes">Top Quotes</a>""" \
        + """<br><a href="#audio">Audio Clips</a>""" \
        + video_clips_html \
        + video_subtitles_clips_html \
        + memes_html \
        + """<br><a href="#transcript">Transcript</a>""" \
        + """<br><br><b><a id="title_suggestions">Title Suggestions</a></b><br><br>""" + title \
        + """<br><br><b><a id="description_suggestions">Description Suggestions</a></b><br><br>""" + description \
        + """<br><br><b><a id="blog_post">Blog Post</a></b>""" + article \
        + """<br><br><b><a id="top_quotes">Top Quotes</a></b><br><br>""" + present_top_quotes

        combined_email = combined_base + """<br><br><b><a id="audio">Audio Clips</a></b><br><br>""" + email_present_audio_clips \
        + email_present_image_audio_clips \
        + email_present_image_audio_subtitles_clips \
        + email_present_memes \
        + """<br><br><b><a id="transcript">Transcript</a></b><br><br>""" + present_sentences_present
        
        combined_html = combined_base + """<br><br><b><a id="audio">Audio Clips</a></b><br><br>""" + present_audio_clips \
        + present_image_audio_clips \
        + present_image_audio_subtitles_clips \
        + present_memes \
        + """<br><br><b><a id="transcript">Transcript</a></b><br><br>""" + present_sentences_present

        user_combined_html = 'Here are the results for your podcast from <a href="https://www.dubb.media/">Dubb</a>. If you like them, consider upgrading to Premium for unlimited podcast submissions!' \
        + combined_email

        print('email to dubb results')
        # email dubb.results@gmail.com with the output
        response = requests.\
            post("https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN,
                auth=("api", MAILGUN_API_KEY),
                 data={
                     "from": 'results@'+ str(MAILGUN_DOMAIN),
                     "to": str(MAIL_USERNAME), ## to be updated to email
                     "subject": "Dubb results",
                     "text": '<b>TO BE REMOVED: </b>' + user + '<b>TO BE REMOVED</b>' + combined_email,
                     "html": '<b>TO BE REMOVED: </b>' + user + '<b>TO BE REMOVED</b>' + combined_email
                 }
             )
        print('email to user')
        # email user with their results 
        response = requests.\
            post("https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN,
                auth=("api", MAILGUN_API_KEY),
                 data={
                     "from": 'results@'+ str(MAILGUN_DOMAIN),
                     "to": user, ## to be updated to email
                     "subject": "Dubb results",
                     "text": user_combined_html,
                     "html": user_combined_html
                 }
             )
        
        return combined_html, user, False

    # email about error
    except Exception as e:
        print(e)
        response = requests.\
            post("https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN,
                auth=("api", MAILGUN_API_KEY),
                 data={
                     "from": 'results@'+ str(MAILGUN_DOMAIN),
                     "to": str(MAIL_USERNAME), ## to be updated to email
                     "subject": "Dubb results",
                     "text": '<b>GENERAL ERROR: </b>' + user + ' Details: ' + filename + ' ' + transcript_id + ' ' + str(e),
                     "html": '<b>GENERAL ERROR: </b>' + user + ' Details: ' + filename + ' ' + transcript_id + ' ' + str(e)
                 }
             )
        return '>There was an error. Sorry about that. We will fix it as soon as possible!', user, True
    
# (not for use in production) make article more readable
def present_article(article):
    print('\n\n'.join([x for x in article.split('\n') if x not in ['', ' ']])) 
    
# (not for use in production) get transcript only, used for training data
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