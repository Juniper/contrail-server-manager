# Import smtplib for the actual sending function
import smtplib
import socket
import cgitb
import sys
import argparse

# Import the email modules we'll need
from email.mime.text import MIMEText

def send_mail(subject, message, mail_sender, mail_to, smtp_server, smtp_port='25'):
    if len(mail_to) == 0:
        print "email recepient is not present."
        return

    if mail_sender == '':
        mail_sender = mail_to[0]

    if subject == '' and message == '':
        print "email subject and message are empty."
        return

    if subject == '':
        subject = message

    if message == '':
        message = subject


    msg = MIMEText(message)
    msg['Subject'] = '%s' % subject
    msg['From'] = mail_sender
    msg['To'] = ', '.join(mail_to)

    # Send the message via our own SMTP server, but don't include the
    # envelope header.
    s = None
    try:
        s = smtplib.SMTP(smtp_server, smtp_port)
    except Exception, e:
        print "Unable to connect to Mail Server"
        return
    s.ehlo()

    try:
        s.sendmail(mail_sender, mail_to, msg.as_string())
        s.quit()
    except smtplib.SMTPException, e :
        print "Error while sending mail"
# end send_mail

def get_local_host_ip():
    return socket.gethostbyname(socket.gethostname())
# end get_local_host_ip

def parse_args(args_str):
    conf_parser = argparse.ArgumentParser(add_help=False)
    args, remaining_argv = conf_parser.parse_known_args(args_str.split())
    parser = argparse.ArgumentParser(
        # Inherit options from config_parser
        parents=[conf_parser],
        # script description with -h/--help
        description=__doc__,
        # Don't mess with format of description
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    defaults = {
        'mail_from': 'pmiriyala@juniper.net',
        'mail_to': '',
        'smtp_server': get_local_host_ip(),
        'smtp_port':'25',
        'message':'Lab testing',
        }
    parser.set_defaults(**defaults)
    parser.add_argument(
        "--mail_from", "-f", help="mail from")
    parser.add_argument(
        "mail_to", help="mail to")
    parser.add_argument(
        "--smtp_server", "-s", help="smtp server")
    parser.add_argument(
        "--smtp_port", "-p", help="smtp server port")
    parser.add_argument(
        "--message", "-m", help="message to send")
    args = parser.parse_args(remaining_argv)       
    return args
# end parse_args

def main(args_str=None):
    if not args_str:
        args_str = ' '.join(sys.argv[1:])
    args = parse_args(args_str)
    mail_from = args.mail_from
    mail_to = []
    mail_to.append(args.mail_to)
    if mail_from == '':
        mail_from = args.mail_to

    subject = args.message
    send_mail(subject, args.message, mail_from, mail_to, args.smtp_server, args.smtp_port)
# end main

if __name__ == '__main__':
    cgitb.enable(format='text')
    main()

