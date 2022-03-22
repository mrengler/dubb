import json
from flask import request, Flask, render_template
from helper_functions import *
from allow_list import allow_list
import logging
import re
from rq import Queue
from worker import conn


app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

openai_model = "davinci:ft-summarize-2022-02-16-06-31-03"
complete_end_string = "+++"

# filename='temp3.wav'
# speakers_input = [
#     'Ryan Knutson', 
#     'Barista', 
#     'Jesse Newman', 
#     'Ad', 
#     'Khadeeja Safdar',
#     'Tony Peterson',
#     'Ad',
#     ]
# transcript_id='os62z6y348-b33a-4d3c-94e5-e85b21377f12'
# filename='temp4.wav'
# speakers_input=[
#     'John',    
#     'Kalyan',
# ]
# transcript_id='os0h1626vt-d735-4829-8aab-250d32664e75'

q = Queue(connection=conn, default_timeout=600)


@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == 'POST':
        # return render_template('index.html')
        email = request.form['email'] 

        if email in allow_list:

            url = request.form['url']
            speakers = request.form['speakers']
            speakers_input = [name.strip() for name in speakers.split(',')]

            # time.sleep(3) ##remove later
            # converting="Blank Blank Blank"
            # cleaned_sentences=['blah blah blah']
            filename = re.sub(r'\W+', '', url) + '.wav'
            print('This is filename: ' + filename)

            # converting, cleaned_sentences = run_combined(
            #     url,
            #     email,
            #     speakers_input,
            #     filename,
            #     model=openai_model,
            #     complete_end_string=complete_end_string,
            #     skip_upload=False,
            #     skip_transcribe=False,
            #     paragraphs=True,
            # )

            converting, cleaned_sentences = q.enqueue(
                run_combined,
                args=(
                    url,
                    email,
                    speakers_input,
                    filename,
                ),
                timeout=600
            )

            return {'article': converting, 'transcript': cleaned_sentences}
        else:
            return {'article': "We're sorry, we haven't opened up Dubb to you yet!", 'transcript': None}
    else:
        return render_template('index.html')

# @app.route('/transcribe', methods=['GET', 'POST'])
# def transcribe():
#     if request.method == 'POST':

#         output = request.get_json()
#         print(output) # This is the output that was stored in the JSON within the browser
#         print(type(output))
#         result = json.loads(output) #this converts the json output to a python dictionary
#         print(result) # Printing the new dictionary
#         print(type(result))#this shows the json converted as a python dictionary
#         return result
#     else:
#         return 'else'

if __name__ == '__main__':
  app.run(debug=True)
