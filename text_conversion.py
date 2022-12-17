from __future__ import absolute_import

from pydub import AudioSegment
import re
import random
from fuzzywuzzy import process
import sys
sys.path.append('/Users/samplank/anaconda/envs/py3/lib/python3.9/site-packages')

import openai

from config import *
import os
import time
from dotenv import load_dotenv
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
    prompt_chunks = transcription.split_transcript(cleaned_paragraphs, for_transcript=False, prompt_end_string=prompt_end_string)

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
                        max_tokens=MAX_TOKENS_FACTS_QUOTES,
                        temperature=0.0,
                        presence_penalty=pres_penalty,
                        user=user,
                    )
                r_fact_text = r_fact.choices[0].text
                r_fact_text_list = r_fact_text.split('\n\n')
                new_facts = [r_fact_text_list[0][1:]] + [fact[3:] for fact in r_fact_text_list[1:]]
                for fact in new_facts:
                    fact_classification = utils.content_filter(fact, user)
                    if fact_classification  != '2':
                        facts.append(fact)
                
                ## get top quotes from that chunk
                r_quote = openai.Completion.create(
                        model='text-davinci-003',
                        prompt=quote_prompt_chunk,
                        max_tokens=MAX_TOKENS_FACTS_QUOTES,
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
                            quote_classification = utils.content_filter(quote, user)
                            # check that it's not unsafe
                            if quote_classification  != '2':
                                quotes.append(quote)

                                # generate audiograms
                                if num_audios < NUM_AUDIOS_TO_PRODUCE:
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
                                    utils.upload_to_gs(bucket_name, top_quote_audio_filename, top_quote_audio_filename)
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
    num_facts = min(MAX_FACTS, len(facts))
    facts_sample = [
        facts[i] for i in sorted(random.sample(range(len(facts)), num_facts))
    ]
    fact_text = """"""
    for i, r in enumerate(facts_sample):
        fact_text += str(i + 1) + ': ' + r + "\n"

    # combine top quotes
    num_quotes = min(MAX_QUOTES, len(quotes))
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
                        max_tokens=MAX_TOKENS_OUTPUT,
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