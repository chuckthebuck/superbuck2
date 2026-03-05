import os

import mwoauth
import mwoauth.flask
from flask import redirect, request, send_file, session, url_for, render_template

from app import celery as celery_app
from app import flask_app as app
from matchandsplit import match, split
from toolsdb import init_db, get_conn
from logger import get_log_file
from uuid import uuid4 as uuid
init_db()

if not os.environ.get('NOTDEV'):
    from dotenv import load_dotenv
    load_dotenv()
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
else:
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

inspect = celery_app.control.inspect()

@app.route('/match', methods=['POST', 'GET'])
def match_route():
    if session.get('username') is None:
        return redirect(url_for('login', referrer='/match'))
    if request.method == 'GET':
        return render_template(
            'match.html',
            username=session['username'],
            type='match')
    username = session['username']
    lang = request.form['lang']
    title = request.form['title']
    log_file = f'{uuid()}.log'
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO jobs 
                (type, lang, title, username, status)
                VALUES (%s, %s, %s, %s, %s)''', 
                ('match', lang, title, username, 'queued'))
            jid = cursor.lastrowid
        conn.commit()
    match.delay(lang, title, username, log_file, jid)
    return {'status': 'recieved', 'log_file': log_file, 'jid': jid}

@app.route('/split', methods=['POST', 'GET'])
def split_route():
    if session.get('username') is None:
        return redirect(url_for('login', referrer='/split'))
    if request.method == 'GET':
        return render_template(
            'split.html',
            username=session['username'],
            type='split')
    lang = request.form['lang']
    title = request.form['title']
    username  = session['username']
    log_file = f'{uuid()}.log'
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO jobs 
                (type, lang, title, username, status)
                VALUES (%s, %s, %s, %s, %s)''', 
                ('split', lang, title, username, 'queued'))
            jid = cursor.lastrowid
        conn.commit()
    split.delay(lang, title, username, log_file, jid)
    return {'status': 'recieved', 'log_file': log_file, 'jid': jid}

@app.route('/goto')
def goto():
    target = request.args.get('tab')
    if session.get('username') is None:
        return redirect(url_for('login', referrer='/goto?tab=' + target))
    if target == 'match':
        return redirect(url_for('match_route'))
    if target == 'split':
        return redirect(url_for('split_route'))
    if target == 'status':
        return redirect(url_for('status'))
    if target == 'documentation':
        return redirect('https://en.wikisource.org/wiki/Help:Match_and_split')
    return redirect(url_for(target))

@app.route('/internal-status')
def all_internal_status():
    html = open('status.html').read()
    start = 'Tasks in queue: ' + str( len(inspect.active()['worker@mas-sodium']) + len(inspect.scheduled()['worker@mas-sodium']) + len(inspect.reserved()['worker@mas-sodium']) )
    table = '<table class="wikitable"><tbody><tr><th>Task name</th><th>Language</th><th>Title</th><th>Username</th></tr>'
    rowtmpl = '<tr><td>$name</td><td>$1</td><td>$2</td><td>$3</td></tr>'
    for task in inspect.active()['worker@mas-sodium']:
        table += rowtmpl.replace('$name', task['name']).replace('$1', task['args'][0]).replace('$2', task['args'][1]).replace('$3', task['args'][2])
    for task in inspect.reserved()['worker@mas-sodium']:
        table += rowtmpl.replace('$name', task['name']).replace('$1', task['args'][0]).replace('$2', task['args'][1]).replace('$3', task['args'][2])
    for task in inspect.scheduled()['worker@mas-sodium']:
        table += rowtmpl.replace('$name', task['name']).replace('$1', task['args'][0]).replace('$2', task['args'][1]).replace('$3', task['args'][2])
    table += '</tbody></table>'
    return html + start + table

@app.route('/logs')
def logs():
    if session.get('username') is None:
        return redirect(url_for('login', referrer='/logs'))
    logfile = request.args.get('file')
    if not logfile:
        return 'No log file specified'
    if not os.path.exists(get_log_file(logfile)):
        return 'Log file not found'
    return render_template('logs.html', log=open(get_log_file(logfile)).read(), username=session['username'], type='logs', log_name=logfile)

@app.route('/status/json')
def all_status_json():
    return { 'active': inspect.active()['worker@mas-sodium'], 'scheduled': inspect.scheduled()['worker@mas-sodium'], 'reserved': inspect.reserved()['worker@mas-sodium'] }

@app.route('/status')
def status():
    if session.get('username') is None:
        return redirect(url_for('login', referrer='/status'))
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM jobs WHERE username = %s', (session['username'],))
            jobs = cursor.fetchall()
    jobs = sorted(jobs, key=lambda x: x[0], reverse=True)
    return render_template('status.html', jobs=jobs, username=session['username'], type='status')

@app.route('/all-status')
def all_status():
    if session.get('username') is None:
        return redirect(url_for('login', referrer='/status'))
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM jobs')
            jobs = cursor.fetchall()
    jobs = sorted(jobs, key=lambda x: x[0], reverse=True)
    return render_template('all_status.html', jobs=jobs, username=session['username'], type='allstatus')

@app.route('/')
def index():
    return render_template('index.html', username=session.get('username'), type='index')

@app.route('/login')
def login():
    """Initiate an OAuth login.
    
    Call the MediaWiki server to get request secrets and then redirect the
    user to the MediaWiki server to sign the request.
    """
    if request.args.get( 'referrer' ):
        session['referrer'] = request.args.get( 'referrer' )
    consumer_token = mwoauth.ConsumerToken(
        os.environ.get('USER_OAUTH_CONSUMER_KEY'), os.environ.get('USER_OAUTH_CONSUMER_SECRET'))
    try:
        redirect_loc, request_token = mwoauth.initiate(
            'https://meta.wikimedia.org/w/index.php', consumer_token)
    except Exception:
        app.logger.exception('mwoauth.initiate failed')
        return redirect(url_for('index'))
    else:
        session['request_token'] = dict(zip(
            request_token._fields, request_token))
        return redirect(redirect_loc)


@app.route('/mas-oauth-callback')
def oauth_callback():  
    if 'request_token' not in session:
        return redirect(url_for('index'))

    consumer_token = mwoauth.ConsumerToken(
        os.environ.get('USER_OAUTH_CONSUMER_KEY'), os.environ.get('USER_OAUTH_CONSUMER_SECRET'))

    try:
        access_token = mwoauth.complete(
            'https://meta.wikimedia.org/w/index.php',
            consumer_token,
            mwoauth.RequestToken(**session['request_token']),
            request.query_string)

        identity = mwoauth.identify(
            'https://meta.wikimedia.org/w/index.php', consumer_token, access_token)
    except Exception as _:
        app.logger.exception('OAuth authentication failed')
    
    else:
        session['access_token'] = dict(zip(
            access_token._fields, access_token))
        session['username'] = identity['username']
    
    referrer = session.get('referrer')
    session['referrer'] = None

    return redirect(referrer or '/')

@app.route('/logout')
def logout():
    """Log the user out by clearing their session."""
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
