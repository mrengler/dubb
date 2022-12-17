from __future__ import absolute_import

import requests
import sys
import time
sys.path.append('/Users/samplank/anaconda/envs/py3/lib/python3.9/site-packages')

import openai

import os
from dotenv import load_dotenv
from config import *
import media_generation
import text_conversion
import transcription
import utils

load_dotenv()

openai.api_key = os.environ.get('OPENAI_API_KEY')
ASSEMBLY_API_KEY = os.environ.get('ASSEMBLY_API_KEY')
REPLICATE_API_TOKEN = os.environ.get('REPLICATE_API_TOKEN')
REPLICATE_ANIMATION_MODEL = os.environ.get('REPLICATE_ANIMATION_MODEL')
REPLICATE_MEME_MODEL = os.environ.get('REPLICATE_MEME_MODEL')
MAILGUN_API_KEY = os.environ["MAILGUN_API_KEY"]
MAILGUN_DOMAIN = os.environ["MAILGUN_DOMAIN"]
MAIL_USERNAME = os.environ["MAIL_USERNAME"]


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
                status = utils.download_yt(content, filename)
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
                    utils.upload_to_gs(bucket_name, filename, filename)
            # if user input is a file, it was already uploaded in app.py, download it here
            elif content_type=='file':
                utils.download_from_gs(bucket_name, filename, filename)

        # make a signed url for sending to assemblyAI for transcription
        audio_file = utils.generate_download_signed_url_v4(bucket_name, filename)
        
        if skip_transcribe==False:
            # send for transcription
            transcript_id = transcription.assembly_start_transcribe(audio_file)
        
        # wait for transcription to complete
        cleaned_paragraphs = 'waiting'
        while cleaned_paragraphs == 'waiting':
            print('wait cleaned sentences')
            cleaned_paragraphs, start_times, cleaned_paragraphs_no_ads, sentences_diarized = transcription.assembly_finish_transcribe(
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
        article, quotes, audio_filenames, audio_start_times, audio_durations, audio_quotes, fact_text = text_conversion.convert(
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

        present_top_quotes = '<br><br>'.join(quotes)

        audio_files_nonnull = [audio for audio in audio_filenames if audio is not None]

        present_audio_clips = """<audio controls><source src='https://storage.googleapis.com/writersvoice/""" + """' type='audio/mpeg'></audio><br><br><audio controls><source src='https://storage.googleapis.com/writersvoice/""".join(audio_files_nonnull) + """' type='audio/mpeg'></audio>"""
        
        tmp_email_audio_clips = ['<a href="https://storage.googleapis.com/writersvoice/' + clip + '">' + clip + '</a>' for clip in audio_files_nonnull]

        email_present_audio_clips = '<br><br>'.join(tmp_email_audio_clips)

        prompt_base = article[:int(MAX_TOKENS_OUTPUT_BASE_MODEL * CHARS_PER_TOKEN)]
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
                    max_tokens=MAX_TOKENS_OUTPUT,
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
        if int(len(article_prompt) / CHARS_PER_TOKEN) + MAX_TOKENS_OUTPUT_ARTICLE_FINAL < MAX_TOKENS_OUTPUT_BASE_MODEL:
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
                        max_tokens=MAX_TOKENS_OUTPUT_ARTICLE_FINAL,
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

            for top_quote, top_quote_audio_filename, audio_start_time in sorted_image_prompts_l:
                print('make video filters:')
                print(make_videos)
                print(num_videos < NUM_VIDEOS_TO_PRODUCE)
                print(top_quote_audio_filename is not None)

                if (make_videos) and (num_videos < NUM_VIDEOS_TO_PRODUCE) and (top_quote_audio_filename is not None):
                    # generate video
                    image_audio_filename, image_audio_subtitles_filename = media_generation.create_video(
                        user,
                        filename,
                        transcript_id,
                        num_videos,
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
                    meme_filename = media_generation.create_meme(
                        user,
                        filename,
                        num_memes,
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