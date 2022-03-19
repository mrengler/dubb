import json
from flask import request, Flask, render_template
from helper_functions import *

app = Flask(__name__)

openai_model = "davinci:ft-summarize-2022-02-16-06-31-03"
complete_end_string = "+++"

user='smgplank@gmail.com'
filename='temp3.wav'
speakers_input = [
    'Ryan Knutson', 
    'Barista', 
    'Jesse Newman', 
    'Ad', 
    'Khadeeja Safdar',
    'Tony Peterson',
    'Ad',
    ]

@app.route('/', methods=["GET", "POST"])
def index():
    if request.method == 'POST':
        # return render_template('index.html')
        url = request.form['url']
        
        converting, cleaned_sentences = run_combined(
            url,
            user,
            speakers_input,
            filename,
            skip_upload=True,
            skip_transcribe=True,
            transcript_id='os62z6y348-b33a-4d3c-94e5-e85b21377f12',
            paragraphs=True,
        )
        print(present_article(converting))

        # output = request.get_json()
        # print(output) # This is the output that was stored in the JSON within the browser
        # print(type(output))
        # result = json.loads(output) #this converts the json output to a python dictionary
        # print(result) # Printing the new dictionary
        # print(type(result))#this shows the json converted as a python dictionary
        return converting
    else:
        return render_template('templates/index.html')

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