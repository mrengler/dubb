from __future__ import absolute_import

import requests
import time
import replicate
import re
import math
import random
import string
import sys
sys.path.append('/Users/samplank/anaconda/envs/py3/lib/python3.9/site-packages')

import openai

import os
from dotenv import load_dotenv
from config import *
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


# create animated video from the audio file
def create_video(
    user,
    filename,
    transcript_id,
    num_videos,
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
        style_text = 'by zdzisław beksiński, dark surrealism'

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
                max_tokens=MAX_TOKENS_OUTPUT_IMAGE_DESCRIPTION,
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
                    max_tokens=MAX_TOKENS_OUTPUT_IMAGE_DESCRIPTION,
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
        top_quote_image_description_classification = utils.content_filter(top_quote_image_description, user)
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
        l = utils.get_length(image_filename) * slow_multiple
        fps_full = l * DOUBLE * FRAME_RATE
        desired_length = utils.get_length(top_quote_audio_filename)
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
        os.system("""ffmpeg -i """ + tmp_image_audio_filename + """ -ss 00:00:00 -t """ + utils.millsecond_to_timestamp(math.ceil(desired_length) * 1000) + """ """ + image_audio_filename)

        # make srt file that starts at beginning of video
        shifted_srt_filename = transcript_id + "_" + random_str + ".srt"
        os.system("""ffmpeg -ss """ + str(audio_start_time / 1000) + """ -i """ + transcript_id + """.srt -c copy """ + shifted_srt_filename)
        utils.upload_to_gs(bucket_name, shifted_srt_filename, shifted_srt_filename)

        # get video with subtitles
        image_audio_subtitles_filename = filename.split('.')[0] + '_video_' + str(num_videos) + random_str + "_subtitles.mp4"
        os.system("""ffmpeg -i """ + image_audio_filename + """ -vf "subtitles=""" + shifted_srt_filename + """:force_style='Fontname=Roboto,OutlineColour=&H40000000,BorderStyle=3'" """ + image_audio_subtitles_filename)

        ## save videos to google cloud
        utils.upload_to_gs(bucket_name, image_audio_filename, image_audio_filename)
        utils.upload_to_gs(bucket_name, image_audio_subtitles_filename, image_audio_subtitles_filename)

        return image_audio_filename, image_audio_subtitles_filename

# create meme of top quote
def create_meme(
    user,
    filename,
    num_memes,
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
        style_text = 'by zdzisław beksiński, dark surrealism'

    prompt_text = "Here are some facts that were discussed in a podcast episode:\n\n" + fact_text +\
    '\n\nHere is the top quote from the podcast episode:\n\n"' + top_quote + '"\n\nUse the top quote and facts to write a description of the image that accompanies the podcast episode:\n\nThe image does not contain any words, quotes, dates, or logos. The image features'

    print(prompt_text)

    # generate descriptions of the image
    top_quote_image_description_response = openai.Completion.create(
        model='text-davinci-003',
        prompt=prompt_text,
        max_tokens=MAX_TOKENS_OUTPUT_IMAGE_DESCRIPTION,
        temperature=0.0,
        presence_penalty=pres_penalty,
        user=user,
    )

    top_quote_image_description = top_quote_image_description_response.choices[0].text

    # get the classification
    top_quote_image_description_classification = utils.content_filter(top_quote_image_description, user)

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
        print("""ffmpeg -i """ + image_filename + """ -vf "drawtext=text='""" + utils.split_txt_into_multi_lines(top_quote, line_length) + """':bordercolor=black:borderw=3:fontcolor=white:fontsize=""" + str(fontsize) + """:x=""" + str(w_padding) + """:y=""" + str(h_padding) + """:" """ + meme_filename)
        os.system("""ffmpeg -i """ + image_filename + """ -vf "drawtext=text='""" + utils.split_txt_into_multi_lines(top_quote, line_length) + """':bordercolor=black:borderw=3:fontcolor=white:fontsize=""" + str(fontsize) + """:x=""" + str(w_padding) + """:y=""" + str(h_padding) + """:" """ + meme_filename)

        # save to google cloud
        utils.upload_to_gs(bucket_name, meme_filename, meme_filename)

        return meme_filename