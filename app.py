import json
import requests
import smtplib
from email.mime.text import MIMEText
from flask import request, Flask, url_for, render_template, render_template_string, redirect
from flask_mail import Mail, Message
from helper_functions import *
from allow_list import allow_list
import logging
import re
from rq import Queue
from rq.job import Job
from worker import conn
from time import sleep
from flask_mail import Mail
import firebase_admin
from firebase_admin import credentials, auth, firestore
from datetime import datetime

import os
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

app.config['MAILGUN_API_KEY'] = os.environ["MAILGUN_API_KEY"]
app.config['MAILGUN_DOMAIN'] = os.environ["MAILGUN_DOMAIN"]
app.config['MAIL_USERNAME'] = os.environ["MAIL_USERNAME"]

# mail = Mail(app)

openai_model = os.environ["OPENAI_MODEL"]
complete_end_string = os.environ["COMPLETE_END_STRING"]

q = Queue(connection=conn, default_timeout=3600)

ENV_KEYS = {
    "type": "service_account",
    "project_id": os.environ["FIREBASE_PROJECT_ID"],
    "private_key_id": os.environ["FIREBASE_PRIVATE_KEY_ID"],
    "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
    "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
    "client_id": os.environ["FIREBASE_CLIENT_ID"],
    "auth_uri": os.environ["FIREBASE_AUTH_URI"],
    "token_uri": os.environ["FIREBASE_TOKEN_URI"],
    "auth_provider_x509_cert_url": os.environ["FIREBASE_AUTH_PROVIDER_x509_cert_url"],
    "client_x509_cert_url": os.environ["CLIENT_x509_CERT_URL"],
}

cred = credentials.Certificate(ENV_KEYS)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Create a directory in a known location to save files to.
uploads_dir = os.path.join(app.instance_path, 'uploads')
os.makedirs(uploads_dir, exist_ok=True)


def get_template(data, refresh=False):
    
    if refresh==False:
        template_str='''<html>
            <head>
              {% if refresh %}
              <meta http-equiv="refresh" content="5">
              {% endif %}
              <link rel="stylesheet" href="https://unpkg.com/style.css">
            </head>
            <body style="padding: 3% 10% 3% 10%">
            <body><div style="font-size:30px;">''' + data + '''</div></body>
            </html>'''
    elif refresh==True:
        template_str='''<html>
            <head>
              {% if refresh %}
              <meta http-equiv="refresh" content="5">
              {% endif %}
              <link rel="stylesheet" href="https://unpkg.com/style.css">
            </head>
            <body style="padding: 3% 10% 3% 10%">
            <body>Your results will load here! Please check back in a few minutes. </body>
            </html>'''

    return render_template_string(template_str, refresh=refresh)


@app.route('/result/<string:id>')
def result(id):
    job = Job.fetch(id, connection=conn)
    status = job.get_status()
    if status in ['queued', 'started', 'deferred', 'failed']:
        return get_template(status, refresh=True)
    elif status == 'finished':
        result, email = job.result 

        response = requests.\
            post("https://api.mailgun.net/v3/%s/messages" % app.config['MAILGUN_DOMAIN'],
                auth=("api", app.config['MAILGUN_API_KEY']),
                 data={
                     "from": 'dubb@'+ str(app.config['MAILGUN_DOMAIN']),
                     "to": str(app.config['MAIL_USERNAME']), ## to be updated to email
                     "subject": "Dubb results",
                     "text": result,
                     "html": result
                 }
             )
        print(response.raise_for_status()) 

        return get_template(result)

@app.route('/waitlist', methods=["GET", "POST"])
def enqueue():
    if request.method == 'POST':
        email = request.form['email']

        if email not in allow_list:
            db.collection("waitlist").document().set({
                'email': email,
                'time': datetime.now(),
            })

    return render_template('index.html')

   


@app.route('/process', methods=["GET", "POST"])
def process():
    if request.method == 'POST':

        # return render_template('index.html')

        ### TO BE UNCOMMENTED
        # email = request.form['email'] 

        email = 'smgplank@gmail.com'

        if email in allow_list:

            file = request.files['file']
            if file:
                filename = file.filename
                file.save(profile.save(os.path.join(uploads_dir, secure_filename(filename))))
                content = filename
                content_type = 'file'
                print('This is content: ' + filename)
            elif not file:
                content = request.form['url']
                content_type = 'url'
                filename = re.sub(r'\W+', '', url) + '.wav'
            # url = request.form['url']
            # print(url)

            # if file is not None:
            #     filename = file



            speakers = request.form['speakers']
            speakers_input = [name.strip() for name in speakers.split(',')]

            job = q.enqueue(
                run_combined,
                args=(
                    content,
                    content_type,
                    email,
                    speakers_input,
                    filename,
                    openai_model
                ),
                kwargs={
                    'paragraphs': True
                },
                timeout=600
            )

            db.collection("requests").document().set({
                'email': email,
                'content': content,
                'speakers': speakers,
                'time': datetime.now(),
            })



            return redirect(url_for('result', id=job.id))
            # print('This is results: ' + results)

            # return {'article': converting, 'transcript': cleaned_sentences}
        else:
            return render_template('waitlist.html')
    else:
        return render_template('index.html')


@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
  app.run(debug=True)
