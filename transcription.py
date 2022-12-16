from __future__ import absolute_import

import requests
import time
from fuzzywuzzy import process
import sys
sys.path.append('/Users/samplank/anaconda/envs/py3/lib/python3.9/site-packages')

import openai

import os
from dotenv import load_dotenv

load_dotenv()


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

openai.api_key = os.environ.get('OPENAI_API_KEY')
ASSEMBLY_API_KEY = os.environ.get('ASSEMBLY_API_KEY')
REPLICATE_API_TOKEN = os.environ.get('REPLICATE_API_TOKEN')
REPLICATE_ANIMATION_MODEL = os.environ.get('REPLICATE_ANIMATION_MODEL')
REPLICATE_MEME_MODEL = os.environ.get('REPLICATE_MEME_MODEL')
MAILGUN_API_KEY = os.environ["MAILGUN_API_KEY"]
MAILGUN_DOMAIN = os.environ["MAILGUN_DOMAIN"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]

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

            return cleaned_paragraphs, start_times, cleaned_paragraphs_no_ads, sentences_diarized

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