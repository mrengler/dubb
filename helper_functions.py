from __future__ import absolute_import

max_token_input = 1548
max_tokens_output = 350
max_tokens_output_base_model = 4097
max_tokens_output_image_description = 120
max_tokens_output_article_final = 2000
chars_per_token = 3.70
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


def assembly_finish_transcribe(transcript_id, speakers_input, paragraphs):

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
        if len(unique_speakers) < len(speakers_input):
            speakers_input = speakers_input[:len(unique_speakers)]

        speaker_hash = {}
        for i,speaker in enumerate(speakers_input):
            speaker_hash[unique_speakers[i]] = speaker
        unknown_speakers = list(set(unique_speakers) - set(speaker_hash.keys()))
        for speaker in unknown_speakers:
            speaker_hash[speaker] = 'Unknown'
        speaker_hash['UNK'] = 'Unknown'

        current_speaker_sentences_joined = ''

        max_num_sentences = 15
        num_sentences_used = 0

        if paragraphs==True:
            cleaned_paragraphs = []
            current_speaker = ''
            current_speaker_sentences = []
            start_times = []
            start_times_unformatted = []
            for speaker, sentence, start_time, start_time_unformatted in sentences_diarized:
                speaker = speaker_hash[speaker]
                if (speaker != current_speaker) or (num_sentences_used >= max_num_sentences):
                    if current_speaker != '':
                        current_speaker_sentences_joined = current_speaker + ": " + " ".join(current_speaker_sentences)
                        cleaned_paragraphs.append(current_speaker_sentences_joined)
                        start_times.append(start_time)
                        start_times_unformatted.append(start_time_unformatted)
                    current_speaker = speaker
                    current_speaker_sentences = [sentence]
                    num_sentences_used = 1

                else:
                    current_speaker_sentences.append(sentence)
                    num_sentences_used += 1

            current_speaker_sentences_joined = current_speaker + ": " + " ".join(current_speaker_sentences)
            cleaned_paragraphs.append(current_speaker_sentences_joined)
            start_times.append(start_time)
            start_times_unformatted.append(start_time_unformatted)

            return cleaned_paragraphs, start_times, start_times_unformatted, sentences_diarized

        elif paragraphs==False:

            cleaned_sentences = [speaker_hash[speaker] + ": " +  sentence for speaker, sentence, start_time, start_time_unformatted in sentences_diarized]
            start_times = [start_time for speaker, sentence, start_time, start_time_unformatted in sentences_diarized]
            start_times_unformatted = [start_time_unformatted for speaker, sentence, start_time, start_time_unformatted in sentences_diarized]

            return cleaned_sentences, start_times, start_times_unformatted, sentences_diarized
        
    except:
        return 'waiting', None, None, None


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
            if for_transcript==True:
                prompt_chunks.append("Chunk " + str(chunk_i) + ":\n\n"  + "\n".join(chunk) + "\n\n\n")
            elif for_transcript==False:
                prompt_chunks.append(' ' + "\n".join(chunk) + prompt_end_string)
            used_chars = sentence_chars
            chunk = [sentence]
            chunk_i += 1
    
    if for_transcript==True:        
        prompt_chunks.append("Chunk " + str(chunk_i) + ":\n\n"  + "\n".join(chunk) + "\n\n\n")
    elif for_transcript==False:
        prompt_chunks.append(' ' + "\n".join(chunk) + prompt_end_string)

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


def convert(
    user,
    cleaned_sentences,
    sentences_diarized,
    speakers_input,
    filename,
    bucket_name, 
    temp, 
    pres_penalty, 
    model="davinci:ft-summarize-2022-01-02-20-59-54",
    prompt_end_string="\n\n===\n\n",
    complete_end_string=[" +++"]):

    replicate_model = replicate.models.get("deforum/deforum_stable_diffusion")

    summary_chunks = []
    top_quotes = []
    images = []
    audio_filenames = []
    image_audio_filenames = [] 

    image_count = 0
    image_audio_count = 0

    start_times_unformatted = [timestamp for (_, _, _, timestamp) in sentences_diarized]
    prompt_chunks = split_transcript(cleaned_sentences, for_transcript=False, prompt_end_string=prompt_end_string)

    print(sentences_diarized)

    for prompt_chunk in prompt_chunks:
        attempts = 0
        # while attempts < 5:
        #     try:
        summary_chunk_response = openai.Completion.create(
            model=model,
            prompt=prompt_chunk,
            max_tokens=max_tokens_output,
            temperature=temp,
            presence_penalty=pres_penalty,
            stop=complete_end_string,
            user=user,
        )

        top_quote_response = openai.Completion.create(
            model='text-davinci-002',
            prompt='The full transcript:\n\n' + prompt_chunk + '\n\nThe most engaging section of the transcript: "',
            max_tokens=max_tokens_output,
            temperature=0.0,
            presence_penalty=pres_penalty,
            stop='"',
            user=user,
        )

        top_quote = top_quote_response.choices[0].text

        summary_classification = content_filter(top_quote, user)

        if summary_classification != '2': ##unsafe
            summary_chunk = summary_chunk_response.choices[0].text
            summary_chunk = clean_chunk(summary_chunk)
            summary_chunks.append(summary_chunk)
        else:
            print('UNSAFE RESPONSE:')
            print(summary_chunk_response)

        top_quote_classification = content_filter(top_quote_response.choices[0].text, user)
        
        print('This is top quote classification: ' + str(top_quote_classification))

        if top_quote_classification != '2': ##unsafe

            top_quote = top_quote.replace("The full transcript:\n\n", '')
            for speaker in speakers_input:
                top_quote = top_quote.replace(speaker + ": ", '')
            top_quotes.append(top_quote)
            
            ## generate audiograms
            print('this is debug section')
            print("'" + top_quote + "'")
            try:

                top_quote_split = re.split('\n\n|(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', top_quote)

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

                ## find quote audio start time, end time, duration
                find_top_quote_start = [timestamp for (_, sentence, _, timestamp) in sentences_diarized if top_quote_split[off_index_start].casefold() in sentence.casefold()][0]
                tq_start_i = start_times_unformatted.index(find_top_quote_start)
                tq_start = start_times_unformatted[tq_start_i - off_index_start]
                find_top_quote_end = [timestamp for (_, sentence, _, timestamp) in sentences_diarized if top_quote_split[off_index_end].casefold() in sentence.casefold()][0]
                tq_end_i = start_times_unformatted.index(find_top_quote_end)

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
                upload_to_gs(bucket_name, top_quote_audio_filename, top_quote_audio_filename)

                ##generate audio and visuals combined
                if (image_audio_count < num_image_audios_to_produce) and (tq_duration >= min_video_length):

                    print('this is first prompt:')
                    print('"' + top_quote + '"\n\nDescribe the image that accompanies this quote:\n\nThe image is of')

                    top_quote_image_description_response = openai.Completion.create(
                        model='text-davinci-002',
                        prompt='"' + top_quote + '"\n\nDescribe the image that accompanies this quote:\n\nThe image is of',
                        max_tokens=max_tokens_output_image_description,
                        temperature=0.7,
                        presence_penalty=pres_penalty,
                        user=user,
                    )

                    top_quote_image_description = top_quote_image_description_response.choices[0].text

                    ## first log the classification
                    top_quote_image_description_classification = content_filter(top_quote_image_description, user)

                    top_quote_image_description = top_quote_image_description.lstrip()
                    top_quote_image_description = top_quote_image_description[0].upper() + top_quote_image_description[1:]

                    print("top_quote_image_description")
                    print(top_quote_image_description)

                    print("this is second prompt:")
                    print('The first scene of the animation:\n\n"' + top_quote_image_description + '"\n\nThe second scene of the animation:')

                    top_quote_image_description_response_part_2 = openai.Completion.create(
                        model='text-davinci-002',
                        prompt='The first scene of the animation:\n\n"' + top_quote_image_description + '"\n\nThe second scene of the animation:\n\n"',
                        max_tokens=max_tokens_output_image_description,
                        temperature=0.7,
                        presence_penalty=pres_penalty,
                        user=user,
                        stop='"',
                    )

                    top_quote_image_description_part_2 = top_quote_image_description_response_part_2.choices[0].text

                    ## first log the classification
                    top_quote_image_description_classification_part_2 = content_filter(top_quote_image_description_part_2, user)

                    top_quote_image_description_part_2 = top_quote_image_description_part_2.replace('"', '')
                    top_quote_image_description_part_2 = top_quote_image_description_part_2.lstrip()
                    top_quote_image_description_part_2 = top_quote_image_description_part_2[0].upper() + top_quote_image_description_part_2[1:]

                    print("this is top_quote_image_description_part_2")
                    print(top_quote_image_description_part_2)

                    print("this is third prompt:")
                    print('The first scene of the animation:\n\n"' + top_quote_image_description_part_2 + '"\n\nThe second scene of the animation:')

                    top_quote_image_description_response_part_3 = openai.Completion.create(
                        model='text-davinci-002',
                        prompt='The first scene of the animation:\n\n"' + top_quote_image_description_part_2 + '"\n\nThe second scene of the animation:\n\n"',
                        max_tokens=max_tokens_output_image_description,
                        temperature=0.7,
                        presence_penalty=pres_penalty,
                        user=user,
                        stop='"',
                    )

                    top_quote_image_description_part_3 = top_quote_image_description_response_part_3.choices[0].text

                    ## first log the classification
                    top_quote_image_description_classification_part_3 = content_filter(top_quote_image_description_part_3, user)

                    top_quote_image_description_part_3 = top_quote_image_description_part_3.replace('"', '')
                    top_quote_image_description_part_3 = top_quote_image_description_part_3.lstrip()
                    top_quote_image_description_part_3 = top_quote_image_description_part_3[0].upper() + top_quote_image_description_part_3[1:]

                    print(top_quote_image_description_part_3)                    


                    if (top_quote_image_description_classification != '2') and (top_quote_image_description_classification_part_2 != '2') and (top_quote_image_description_part_3 != '2'): ##unsafe

                        style_text = ' By Edward Hopper. Vibrant colors. Trending on ArtStation.'
                        image = replicate.predictions.create(
                            version=replicate_model.versions.list()[0],
                            input={
                                "animation_prompts": '0: ' + top_quote_image_description + style_text + ' | 10: '\
                                + top_quote_image_description_part_2 + style_text + ' | 20: ' \
                                + top_quote_image_description_part_3 + style_text,
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


                        images.append(src)
                        image_count += 1


                        l = get_length(src)
                        fps_full = l * double * frame_rate
                        desired_length = get_length(top_quote_audio_filename)
                        multiplier = desired_length / (l * 2)
                        loop = math.ceil(multiplier)

                        ##make looped animation
                        image_looped_filename = "image_looped"  + str(tq_start) + "_" + str(tq_end) + ".mp4"
                        os.system("""ffmpeg -i """ + src + """ -filter_complex "[0]reverse[r];[0][r]concat,loop=""" + str(loop) + """:""" + str(fps_full) + """  " """ + image_looped_filename)
                        upload_to_gs(bucket_name, image_looped_filename, image_looped_filename)

                        ###join looped animation with audio
                        image_audio_filename = "image_audio" + str(tq_start) + "_" + str(tq_end) + ".mp4"
                        tmp_image_audio_filename = 'tmp_' + image_audio_filename
                        os.system("""ffmpeg -i """ + image_looped_filename + """ -i """ + top_quote_audio_filename + """ -c:v copy -c:a aac """ + tmp_image_audio_filename)
                        
                        ##trim end of video
                        os.system("""ffmpeg -i """ + tmp_image_audio_filename + """ -ss 00:00:00 -t """ + millsecond_to_timestamp(math.ceil(desired_length) * 1000) + """ """ + image_audio_filename)

                        image_audio_filenames.append(image_audio_filename)
                        upload_to_gs(bucket_name, image_audio_filename, image_audio_filename)

                        image_audio_count += 1
            except:
                pass



        else:
            print('UNSAFE RESPONSE:')
            print(top_quote_response)
                
            #         break
            # except:
            #     attempts += 1
            #     print('number of attempts: ' + str(attempts))
            #     time.sleep(30)
    
    return summary_chunks, top_quotes, images, audio_filenames, image_audio_filenames


def run_combined(
    content,
    content_type,
    user, 
    speakers_input, 
    filename,
    model,
    bucket_name='writersvoice', 
    temperature=1.0, 
    presence_penalty=0.0, 
    prompt_end_string="\n\n===\n\n",
    complete_end_string=["+++"],
    skip_upload=False,
    skip_transcribe=False,
    transcript_id='',
    paragraphs=False):


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
    
    cleaned_sentences = 'waiting'
    while cleaned_sentences == 'waiting':
        print('wait cleaned sentences')
        cleaned_sentences, start_times, start_times_unformatted, sentences_diarized = assembly_finish_transcribe(transcript_id, speakers_input, paragraphs)
        time.sleep(60)

    # try:
    #     audio = AudioSegment.from_mp3(filename)
    # except:
    #     audio = None
    #     print('error with AudioSegment')

        
    summary_chunks, top_quotes, images, audio_filenames, image_audio_filenames = convert(
        user,
        cleaned_sentences,
        sentences_diarized,
        speakers_input,
        filename,
        bucket_name, 
        temperature,
        presence_penalty, 
        model=model,
        prompt_end_string=prompt_end_string,
        complete_end_string=complete_end_string
    )

    present_sentences_timestamps = ['[' + str(start_time) + '] ' + sentence for sentence, start_time in zip(cleaned_sentences, start_times)]
    present_sentences_present = '<br><br>'.join(present_sentences_timestamps)

    present_summary_chunks = '<br><br>'.join(summary_chunks)
    present_top_quotes = '<br><br>'.join(top_quotes)

    present_image_audio_clips = """<video controls><source src='https://storage.googleapis.com/writersvoice/""" + """' type='video/mp4'></video><br><br><video controls><source src='https://storage.googleapis.com/writersvoice/""".join(image_audio_filenames) + """' type='video/mp4'></video>"""
    present_audio_clips = """<audio controls><source src='https://storage.googleapis.com/writersvoice/""" + """' type='audio/mpeg'></audio><br><br><audio controls><source src='https://storage.googleapis.com/writersvoice/""".join(audio_filenames) + """' type='audio/mpeg'></audio>"""
    
    tmp_email_image_audio_clips = ['<a href="https://storage.googleapis.com/writersvoice/' + clip + '">' + clip + '</a>' for clip in image_audio_filenames]
    tmp_email_audio_clips = ['<a href="https://storage.googleapis.com/writersvoice/' + clip + '">' + clip + '</a>' for clip in audio_filenames]

    email_present_image_audio_clips = '<br><br>'.join(tmp_email_image_audio_clips)
    email_present_audio_clips = '<br><br>'.join(tmp_email_audio_clips)

    l1 = [chunk.replace('\n', '\n\n') for chunk in summary_chunks]
    l2 = [chunk.replace('\n\n\n\n', '\n\n') for chunk in l1]
    l3 = [chunk for chunk in filter(lambda chunk: chunk != '', l2)]
    l4 = [chunk[1:] if chunk[0] == ' ' else chunk for chunk in l3]
    l5 = filter(lambda chunk: chunk != '', l4)
    joined_l5 = '\n\n'.join(l5)
    prompt_base = joined_l5[:int(max_tokens_output_base_model * chars_per_token)]
    title_prompt = prompt_base + '\n\nWrite the title of the article: "'
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

    article_response = openai.Completion.create(
        model='text-davinci-002',
        prompt=article_prompt,
        max_tokens=max_tokens_output_article_final,
        temperature=0.7,
        user=user,
    )

    article = article_response.choices[0].text
    article = article.replace("\n\n", "<br><br>")

    combined_base = """<br><br><b>Result Sections</b>""" \
    + """<br><a href="#title_suggestions">Title Suggestions</a>""" \
    + """<br><a href="#description_suggestions">Description Suggestions</a>""" \
    + """<br><a href="#blog_post">Blog Post</a>""" \
    + """<br><a href="#top_quotes">Top Quotes</a>""" \
    + """<br><a href="#audio">Audio Clips</a>""" \
    + """<br><a href="#video">Video Clips</a>""" \
    + """<br><a href="#transcript">Transcript</a>""" \
    + """<br><br><b><a id="title_suggestions">Title Suggestions</a></b><br><br>""" + title \
    + """<br><br><b><a id="description_suggestions">Description Suggestions</a></b><br><br>""" + description \
    + """<br><br><b><a id="blog_post">Blog Post</a></b>""" + article \
    + """<br><br><b><a id="top_quotes">Top Quotes</a></b><br><br>""" + present_top_quotes

    combined_email = combined_base + """<br><br><b><a id="audio">Audio Clips</a></b><br><br>""" + email_present_audio_clips \
    + """<br><br><b><a id="video">Video Clips</a></b><br><br>""" + email_present_image_audio_clips \
    + """<br><br><b><a id="transcript">Transcript</a></b><br><br>""" + present_sentences_present
    
    combined_html = combined_base + """<br><br><b><a id="audio">Audio Clips</a></b><br><br>""" + present_audio_clips \
    + """<br><br><b><a id="video">Video Clips</a></b><br><br>""" + present_image_audio_clips \
    + """<br><br><b><a id="transcript">Transcript</a></b><br><br>""" + present_sentences_present


    response = requests.\
        post("https://api.mailgun.net/v3/%s/messages" % MAILGUN_DOMAIN,
            auth=("api", MAILGUN_API_KEY),
            # files=[("attachment", open('media' + ".zip", "rb"))],
             data={
                 "from": 'dubb@'+ str(MAILGUN_DOMAIN),
                 "to": str(MAIL_USERNAME), ## to be updated to email
                 "subject": "Dubb results",
                 "text": '<b>TO BE REMOVED: </b>' + user + '<b>TO BE REMOVED</b>' + combined_email,
                 "html": '<b>TO BE REMOVED: </b>' + user + '<b>TO BE REMOVED</b>' + combined_email
             }
         )
    
    return combined_html, audio_filenames, image_audio_filenames, user
    

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
    paragraphs=False,
    for_transcript=True):   
    
    if skip_upload==False:
        download_yt(url, filename)
        upload_to_gs(bucket_name, filename, filename)
    
    if skip_transcribe==False:
        audio_file = generate_download_signed_url_v4(bucket_name, filename)
        transcript_id = assembly_start_transcribe(audio_file)
    
    cleaned_sentences = 'waiting'
    while cleaned_sentences == 'waiting':
        print('wait cleaned sentences')
        cleaned_sentences, start_times, start_times_unformatted, sentences_diarized = assembly_finish_transcribe(transcript_id, speakers_input, paragraphs)
        time.sleep(10)
        
    prompt_chunks = split_transcript(cleaned_sentences, for_transcript=for_transcript)

    for prompt in prompt_chunks:
        print(prompt)
    
    if write == True:
        ## TODO: the below should be updates
        file1 = open('transcript_2022_02_07/' + write_title + ".txt","w")
        file1.writelines(prompt_chunks)
        file1.close()

    return prompt_chunks