import sys
from datetime import timedelta

import sendgrid
from flask import Flask, render_template, request
from minio import Minio
from sendgrid import Email
from sendgrid.helpers.mail import Content, Mail

app = Flask(__name__)
from raven.contrib.flask import Sentry
from third.gitbook2pdf.gitbook import Gitbook2PDF
from config import *

sentry = Sentry(app, dsn=SENTRY_SDN)

from celery import Celery

celery = Celery(app.name, broker=BROKER)

minioClient = Minio('cdn.fht.im',
                    access_key=MINIO_AK,
                    secret_key=MINIO_SK,
                    secure=True)


def send_mail(to_address, subject, message):
    sg = sendgrid.SendGridAPIClient(apikey=SG_KEY)
    from_email = Email("notice@sendgird.fht.im")
    to_email = Email(to_address)
    content = Content("text/html", message)
    mail = Mail(from_email, subject, to_email, content)
    sg.client.mail.send.post(request_body=mail.get())


@celery.task
def convert_task(gitbook_url, email):
    try:
        file_full_name = Gitbook2PDF(gitbook_url).run()
        file_name = file_full_name.split("/")[-1]
        minioClient.fput_object("gitbook2pdf", file_name, file_full_name)
        url = minioClient.presigned_get_object('gitbook2pdf', file_name, expires=timedelta(days=2))
        message = f'You can download at <a href={url}>{file_name}<a>'
        send_mail(email, "Hey, Your gitbook \"%s\" is ready!" % file_name.strip('.pdf'), message)
    except Exception as e:
        sentry.captureException(sys.exc_info())
        send_mail(to_address=email, subject="Sorry, generate failed.",
                  message="Sorry, You request is failed. We have record the exception.")


@app.route('/', methods=["POST"])
def handle_post():
    email = request.form.get('email')
    gitbook_url = request.form.get('url')
    convert_task.delay(gitbook_url, email)
    return "<html> <script>alert(/任务添加成功，请留意邮箱通知!/);history.back()</script> <html>"


@app.route('/')
def index():
    return render_template("index.html")


if __name__ == '__main__':
    app.run(debug=True)
