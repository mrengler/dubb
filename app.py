import json
from flask import request, Flask, render_template
from helper_functions import *

app = Flask(__name__)

# get_transcript()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transcribe', methods=['GET', 'POST'])
def transcribe():
    if request.method == 'POST':

        output = request.get_json()
        print(output) # This is the output that was stored in the JSON within the browser
        print(type(output))
        result = json.loads(output) #this converts the json output to a python dictionary
        print(result) # Printing the new dictionary
        print(type(result))#this shows the json converted as a python dictionary
        return result
    else:
        return 'else'

if __name__ == '__main__':
  app.run(debug=True)