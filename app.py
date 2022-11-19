import json
import requests
import smtplib
from email.mime.text import MIMEText
from flask import request, Flask, url_for, render_template, render_template_string, redirect, send_from_directory
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
from werkzeug.utils import secure_filename
import replicate

import os
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

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

# Create a directory in a known location to save uploaded files to.
uploads_dir = os.path.join(app.instance_path, 'uploads')
os.makedirs(uploads_dir, exist_ok=True)

# Create a directory in a known location to save created files to.
media_dir = os.path.join(app.instance_path, 'media')
os.makedirs(media_dir, exist_ok=True)

ALLOWED_EXTENSIONS = {'wav', 'mp3'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_template(result=None, refresh=False, failed=False):
    
    if refresh==False:
        if failed==False:
            template_str='''<html>
                <head>
                  {% if refresh %}
                  <meta http-equiv="refresh" content="5">
                  {% endif %}
                  <link rel="stylesheet" href="https://unpkg.com/style.css">
                </head>
                <body style="padding: 3% 10% 3% 10%">
                <body><div style="font-size:30px;">Your results are ready! Check them out below. Your results will also be sent to your email within 24 hours.
                Look in your inbox and spam folder for an email from dubb.results@gmail.com. Please check your results before posting them publicly.
                <br><br
                ''' + result + '''
                </div></body>
                </html>'''
        elif failed==True:

            template_str='''<html>
                <head>
                  {% if refresh %}
                  <meta http-equiv="refresh" content="5">
                  {% endif %}
                  <link rel="stylesheet" href="https://unpkg.com/style.css">
                </head>
                <body style="padding: 3% 10% 3% 10%">
                <body><div style="font-size:30px;">There was an error processing your results! Sorry about that. We will look into it.
                </div></body>
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
            <body>
                <div style="font-size:30px;">We're working on your results!<br><br>They will load on this page and be sent to your email within 24 hours after we check them for quality.
                Look in your inbox and spam folder for an email from dubb.results@gmail.com</div>
            </body>
            </html>'''

    return render_template_string(template_str, refresh=refresh)


@app.route('/result/<string:id>')
def result(id):
    job = Job.fetch(id, connection=conn)
    status = job.get_status()
    if status in ['queued', 'started', 'deferred', 'failed']:
        return get_template(refresh=True)
    elif status == 'finished':
        combined, user = job.result
        return get_template(combined)


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

        print("This is file and url")
        print(request.files['file'])
        print(request.form['url'])
        email = request.form['email']
        visual_style=request.form['visual_style']
        editorial_style=request.form['editorial_style']

        if (request.files['file'].filename == '') & (request.form['url'] == ''):
            error="Please upload a file or include a url"
            return render_template('index.html', error=error)

        file = request.files['file']
        print(file.filename)

        if file:
            if allowed_file(file.filename):
                print('is allowed file')
                filename = secure_filename(file.filename)
                upload_path = os.path.join(uploads_dir, filename)
                print('This is upload path: ' + upload_path)
                file.save(upload_path)
                content = upload_path
                content_type = 'file'
                upload_to_gs('writersvoice', upload_path, filename) ##update this to heroku variable
            else:
                print('is not allowed file')
                return render_template('index.html')
        elif not file:
            content = request.form['url']
            if not (('podcasts.google' in content) or ('youtube' in content)):
                error="Sorry, we don't support that podcast player. Please link to your podcast episode from Google Podcasts or Youtube, or upload the file of your episode."
                return render_template('index.html', error=error)

            content_type = 'url'
            filename = content.split('/')[-1]
            filename = re.sub(r'\W+', '', filename) + '.mp3'

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
                'paragraphs': True,
                'visual_style': visual_style,
                'editorial_style': editorial_style
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
    else:
        return render_template('index.html')

@app.route('/')
def index():
    return render_template('index.html', error=None)

@app.route('/accelerated')
def index_accelerated():
    return render_template('index_accelerated.html', error=None)

@app.route('/accelerated_process', methods=["GET", "POST"])
def accelerated_process():
    if request.method == 'POST':

        if (request.files['file'].filename == '') & (request.form['url'] == ''):
            error="Please upload a file or include a url"
            return render_template('index_accelerated.html', error=error)

        print("This is file and url")
        print(request.files['file'])
        print(request.form['url'] == '')
        print("This is transcript_id")
        print(request.form['transcript_id'])
        email = request.form['email']
        transcript_id = request.form['transcript_id']
        skip_upload = False
        skip_transcribe=False
        if transcript_id != '':
            skip_transcribe=True
        make_videos = request.form.get("make_videos") != None
        make_memes = request.form.get("make_memes") != None
        print('make_videos: ' + str(make_videos))
        print('make_memes: ' + str(make_memes))
        visual_style=request.form['visual_style']
        editorial_style=request.form['editorial_style']


        file = request.files['file']
        print(file.filename)

        if file:
            if allowed_file(file.filename):
                print('is allowed file')
                filename = secure_filename(file.filename)
                upload_path = os.path.join(uploads_dir, filename)
                print('This is upload path: ' + upload_path)
                file.save(upload_path)
                content = upload_path
                content_type = 'file'
                upload_to_gs('writersvoice', upload_path, filename) ##update this to heroku variable
            else:
                print('is not allowed file')
                return render_template('index_accelerated.html')
        elif not file:
            content = request.form['url']
            if content != '':
                if not (('podcasts.google' in content) or ('youtube' in content)):
                    error="Sorry, we don't support that podcast player. Please link to your podcast episode from Google Podcasts or Youtube, or upload the file of your episode."
                    return render_template('index_accelerated.html', error=error)

                content_type = 'url'
                filename = content.split('/')[-1]
                filename = re.sub(r'\W+', '', filename) + '.mp3'


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
                'paragraphs': True,
                'transcript_id': transcript_id,
                'skip_upload': skip_upload,
                'skip_transcribe': skip_transcribe,
                'make_videos': make_videos,
                'make_memes': make_memes,
                'visual_style': visual_style,
                'editorial_style': editorial_style
            },
            timeout=600
        )


        return redirect(url_for('result', id=job.id))
    else:
        return render_template('index.html')

if __name__ == '__main__':
  app.run(ssl_context="adhoc")
