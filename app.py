import requests
import smtplib
from email.mime.text import MIMEText
from flask import request, Flask, url_for, render_template, render_template_string, redirect, jsonify, session
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

import stripe

load_dotenv()


app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.ERROR)

openai_model = os.environ["OPENAI_MODEL"]
complete_end_string = os.environ["COMPLETE_END_STRING"]
stripe.api_key = os.environ["STRIPE_API_KEY"]
webhook_secret = os.environ["STRIPE_WEBHOOK_SECRET"]
app.secret_key = os.environ["APP_SECRET_KEY"]

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

# initialize database
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

# only set a new global user_email var if one does not exist
var_exists = 'user_email' in locals() or 'user_email' in globals()
if not var_exists:
    print('set user email')
    user_email = ''
else:
    print('user email already set')
    print(user_email)

# check if allowed filename
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# handle waiting for results and results rendering
def get_template(result=None, refresh=False):
    
    if refresh==False:
        template_str='''<html>
            <head>
              {% if refresh %}
              <meta http-equiv="refresh" content="5">
              {% endif %}
              <link rel="stylesheet" href="https://unpkg.com/style.css">
              <link rel="stylesheet" href="/static/stylesheets/dubb.css">
            </head>
            <body style="padding: 3% 10% 3% 10%">
            <body><div style="font-size:30px;">Your results are ready! Check them out below. Your results will also be sent to your email.
            Look in your inbox and spam folder for an email from results@dubb.media. Please check your results before posting them publicly.
            <br><br
            ''' + result + '''
            </div></body>
            </html>'''        
    elif refresh==True:
        template_str='''<html>
            <head>
              {% if refresh %}
              <meta http-equiv="refresh" content="5">
              {% endif %}
              <link rel="stylesheet" href="https://unpkg.com/style.css">
              <link rel="stylesheet" href="/static/stylesheets/dubb.css">
            </head>
            <body style="padding: 3% 10% 3% 10%">
            <body>
                <div style="font-size:30px;">We're working on your results!<br><br>They will load on this page and be sent to your email shortly.
                Look in your inbox and spam folder for an email from results@dubb.media</div>
            </body>
            </html>'''

    return render_template_string(template_str, refresh=refresh)


'''Flask app routes. Handles what renders when a user lands at each url'''

# page user lands at after process
@app.route('/result/<string:id>')
def result(id):
    job = Job.fetch(id, connection=conn)
    status = job.get_status()
    if status in ['queued', 'started', 'deferred', 'failed']:
        return get_template(refresh=True)
    elif status == 'finished':
        combined, user, failed = job.result
        return get_template(combined)

# route triggered by form submission
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

        ## log request
        db.collection("requests").document().set({
            'email': email,
            'content': content,
            'speakers': speakers,
            'time': datetime.now(),
        })

        ## decrement credit counter
        ## increase submissions counter
        user_ref = db.collection('users_info').document(email)
        user_ref.update({"free_credits": firestore.Increment(-1)})
        user_ref.update({"submissions": firestore.Increment(1)})



        return redirect(url_for('result', id=job.id))
    else:
        return render_template('index.html')

# home page
@app.route('/')
def index():
    print('this is session')
    if 'email' in session:
        print(session['email'])
    else:
        print('no email recorded')
    return render_template('index.html', error=None)

# for internal use, page that allows for debugging form submissions
@app.route('/accelerated')
def index_accelerated():
    return render_template('index_accelerated.html', error=None)

# for internal use, triggered after form submission at /accelerated
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

# checkout page
@app.route('/checkout', methods=['GET'])
def checkout():
  return render_template('checkout.html')

# privacy page
@app.route('/privacy', methods=['GET', 'POST'])
def privacy():
    return render_template('privacy.html')

# catch user email for use in sending results and submission to openai
@app.route('/log_email', methods=['POST'])
def log_email():    
    global user_email
    data = request.get_json()
    user_email = data['user']
    print('logged user_email')
    print(user_email)
    if user_email != '':
        session['email'] = user_email
    else
        session.pop('email', None)

    return jsonify(status="success", data=data)

# listen to stripe events
@app.route('/webhook', methods=['POST'])
def webhook_received():
    print('webhook')
    # request_data = json.loads(request.data)
    request_data = request.data
    print(request_data)

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']
    data_object = data['object']

    print('this is event type')
    print(event_type)

    if event_type == 'checkout.session.completed':
    # Payment is successful and the subscription is created.
    # You should provision the subscription and save the customer ID to your database.
        print('this is user_email: ' + user_email)
        user_ref = db.collection('users_info').document(user_email)
        user_ref.update({'status': 'premium'})

    elif event_type == 'invoice.paid':
    # Continue to provision the subscription as payments continue to be made.
    # Store the status in your database and check when a user accesses your service.
    # This approach helps you avoid hitting rate limits.
        print('this is user_email')
        print(user_email)
        user_ref = db.collection('users_info').document(user_email)
        user_ref.update({'status': 'premium'})

    elif event_type == 'invoice.payment_failed':
    # The payment failed or the customer does not have a valid payment method.
    # The subscription becomes past_due. Notify your customer and send them to the
    # customer portal to update their payment information.
        user_ref = db.collection('users_info').document(user_email)
        user_ref.update({'status': 'past_due'})

    elif event_type == 'customer.subscription.deleted':
        user_ref = db.collection('users_info').document(user_email)
        user_ref.update({'status': 'trial'})

    else:
      print('Unhandled event type {}'.format(event_type))

    return jsonify({'status': 'success'})

if __name__ == '__main__':
  app.run(ssl_context="adhoc")