from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify, Response
import hashlib
import os
import qrcode
from io import BytesIO
import base64
import cv2
from db_config import db_manager
from cryptography.fernet import Fernet
from datetime import datetime
import logging
import time
import mysql.connector

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Encryption setup
SECRET_KEY = Fernet.generate_key()
cipher_suite = Fernet(SECRET_KEY)

# Ensure upload folder exists
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Political parties list
POLITICAL_PARTIES = [
    'AIADMK', 'BJP', 'DMK', 
    'TVK', 'PMK', 'VCK', 'DMDK'
]
def generate_qr_code(data):
    """Generate QR code image from data"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# Read QR code using OpenCV
def read_qr_code(image_path):
    try:
        img = cv2.imread(image_path)
        detector = cv2.QRCodeDetector()
        data, vertices_array, binary_qrcode = detector.detectAndDecode(img)
        return data if data else None
    except Exception as e:
        logger.error(f"QR read error: {e}")
        return None

# Check if voter has already voted
def has_voted(voter_id):
    
    result = db_manager.execute_query(
        "SELECT 1 FROM votes WHERE voter_id = %s",
        (voter_id,),
        fetch=True
    )
    return bool(result)

# Check if aadhaar is already registered
def is_registered(aadhaar):
    
    result = db_manager.execute_query(
        "SELECT 1 FROM voters WHERE aadhaar = %s",
        (aadhaar,),
        fetch=True
    )
    return bool(result)

# Initialize all required database tables with political parties
def initialize_database():    
    try:
        # Create tables if they don't exist
        if not db_manager.table_exists('voters'):
            db_manager.execute_query("""
                CREATE TABLE voters (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    aadhaar VARCHAR(12) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    dob DATE NOT NULL,
                    password_hash VARCHAR(64) NOT NULL,
                    qr_code_data VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT chk_aadhaar_length CHECK (LENGTH(aadhaar) = 12),
                    CONSTRAINT chk_aadhaar_numeric CHECK (aadhaar REGEXP '^[0-9]+$')
                )
            """)

        if not db_manager.table_exists('votes'):
            db_manager.execute_query("""
                CREATE TABLE votes (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    voter_id INT NOT NULL,
                    candidate TEXT NOT NULL,
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (voter_id) REFERENCES voters(id) ON DELETE CASCADE,
                    CONSTRAINT unique_voter UNIQUE (voter_id)
                )
            """)

        if not db_manager.table_exists('candidate_results'):
            db_manager.execute_query("""
                CREATE TABLE candidate_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    candidate_name VARCHAR(100) UNIQUE NOT NULL,
                    vote_count INT DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            # Insert political parties
            for party in POLITICAL_PARTIES:
                db_manager.execute_query(
                    "INSERT INTO candidate_results (candidate_name) VALUES (%s)",
                    (party,)
                )
        
        logger.info("Database initialization with political parties complete")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

# Initialize database on startup
initialize_database()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            aadhaar = request.form['aadhaar']
            name = request.form['name']
            dob = request.form['dob']
            password = request.form['password']
            
            if is_registered(aadhaar):
                return redirect(url_for('done', message='already_registered'))
            
            if len(aadhaar) != 12 or not aadhaar.isdigit():
                flash('Aadhaar must be 12 digits', 'error')
                return redirect(url_for('register'))
            
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            qr_data = f"{aadhaar}:{password_hash}"
            qr_code_img = generate_qr_code(qr_data)

            db_manager.execute_query(
                "INSERT INTO voters (aadhaar, name, dob, password_hash, qr_code_data) "
                "VALUES (%s, %s, %s, %s, %s)",
                (aadhaar, name, dob, password_hash, qr_data)
            )
            
            result = db_manager.execute_query(
                "SELECT id FROM voters WHERE aadhaar = %s", 
                (aadhaar,), 
                fetch=True
            )
            
            if result:
                session['new_voter_id'] = result[0]['id']
                session['qr_code_img'] = qr_code_img
                session['voter_name'] = name
                return redirect(url_for('show_qr_code'))
            
            flash('Registration failed', 'error')
        except mysql.connector.Error as err:
            if err.errno == 1062:
                return redirect(url_for('done', message='already_registered'))
            else:
                flash('Registration failed. Please try again.', 'error')
            logger.error(f"Registration error: {err}")
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
            logger.error(f"Registration error: {e}")

    return render_template('register.html')

@app.route('/done')
def done():
    message = request.args.get('message', 'default')
    
    messages = {
        'already_registered': 'You have already registered and cannot register again.',
        'already_voted': 'You have already cast your vote and cannot vote again.',
        'default': 'You have already completed this action.'
    }
    
    return render_template('done.html', 
                         message=messages.get(message, messages['default']))

@app.route('/qr_code')
def show_qr_code():
    if 'new_voter_id' not in session:
        return redirect(url_for('register'))
    return render_template('qr_code.html', 
                         qr_code_img=session['qr_code_img'],
                         name=session['voter_name'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if 'qr_code' not in request.files:
            flash('No QR code uploaded', 'error')
            return redirect(url_for('login'))
            
        qr_file = request.files['qr_code']
        if qr_file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('login'))
            
        if qr_file:
            try:
                filename = os.path.join(app.config['UPLOAD_FOLDER'], qr_file.filename)
                qr_file.save(filename)
                qr_data = read_qr_code(filename)
                os.remove(filename)
                
                if not qr_data:
                    flash('Invalid QR code', 'error')
                    return redirect(url_for('login'))
                
                aadhaar, password_hash = qr_data.split(':')
                result = db_manager.execute_query(
                    "SELECT id, name, dob FROM voters WHERE aadhaar = %s AND password_hash = %s",
                    (aadhaar, password_hash),
                    fetch=True
                )
                
                if result:
                    voter = result[0]
                    if has_voted(voter['id']):
                        return redirect(url_for('done', message='already_voted'))
                    
                    session['voter_id'] = voter['id']
                    session['voter_name'] = voter['name']
                    session['voter_dob'] = voter['dob'].strftime('%Y-%m-%d') if voter['dob'] else ''
                    return redirect(url_for('verify'))
                else:
                    flash('Authentication failed', 'error')
            except Exception as e:
                flash('Login failed. Please try again.', 'error')
                logger.error(f"Login error: {e}")

    return render_template('login.html')

@app.route('/verify')
def verify():
    if 'voter_id' not in session:
        return redirect(url_for('login'))
    
    if has_voted(session['voter_id']):
        return redirect(url_for('done', message='already_voted'))
    
    return render_template('verify.html', 
                         name=session['voter_name'],
                         dob=session['voter_dob'])

@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if 'voter_id' not in session:
        return redirect(url_for('login'))
    
    if has_voted(session['voter_id']):
        return redirect(url_for('done', message='already_voted'))

    if request.method == 'POST':
        party = request.form.get('candidate')
        if not party or party not in POLITICAL_PARTIES:
            flash('Please select a valid political party', 'error')
            return redirect(url_for('vote'))
            
        try:
            db_manager.execute_query("START TRANSACTION")
            
            if has_voted(session['voter_id']):
                return redirect(url_for('done', message='already_voted'))
            
            encrypted_vote = cipher_suite.encrypt(party.encode()).decode()
            
            db_manager.execute_query(
                "INSERT INTO votes (voter_id, candidate) VALUES (%s, %s)",
                (session['voter_id'], encrypted_vote)
            )
            
            db_manager.execute_query(
                "UPDATE candidate_results SET vote_count = vote_count + 1 WHERE candidate_name = %s",
                (party,)
            )
            
            db_manager.execute_query("COMMIT")
            
            return redirect(url_for('thank_you'))
        except Exception as e:
            db_manager.execute_query("ROLLBACK")
            logger.error(f"Voting error: {e}")
            flash('Error casting vote', 'error')
            return redirect(url_for('vote'))

    return render_template('vote.html', parties=POLITICAL_PARTIES)

@app.route('/thank-you')
def thank_you():
    if 'voter_id' not in session:
        return redirect(url_for('login'))
    return render_template('thank_you.html', name=session.get('voter_name', 'Voter'))

@app.route('/results/live')
def live_results():
    return render_template('live_results.html')

@app.route('/results')
def results():
    try:
        results = db_manager.execute_query(
            "SELECT candidate, COUNT(*) as count FROM votes GROUP BY candidate",
            fetch=True
        ) or []
        
        decrypted_results = {}
        for row in results:
            try:
                decrypted_name = cipher_suite.decrypt(row['candidate'].encode()).decode()
                decrypted_results[decrypted_name] = row['count']
            except Exception as e:
                logger.error(f"Decryption error: {e}")
                decrypted_results["Invalid Vote"] = row['count']
        
        return render_template('results.html', results=decrypted_results)
    except Exception as e:
        logger.error(f"Results error: {e}")
        flash('Error retrieving results', 'error')
        return redirect(url_for('home'))

@app.route('/api/results')
def api_results():
    try:
        results = db_manager.execute_query(
            "SELECT candidate_name, vote_count FROM candidate_results ORDER BY vote_count DESC",
            fetch=True
        ) or []
        
        total_votes = sum(row['vote_count'] for row in results)
        
        return jsonify({
            'success': True,
            'results': results,
            'total_votes': total_votes,
            'timestamp': int(time.time())
        })
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/results/stream')
def result_stream():
    def generate():
        while True:
            try:
                results = db_manager.execute_query(
                    "SELECT candidate_name, vote_count FROM candidate_results ORDER BY vote_count DESC",
                    fetch=True
                ) or []
                
                total_votes = sum(row['vote_count'] for row in results)
                
                yield f"data: {json.dumps({
                    'results': results,
                    'total_votes': total_votes,
                    'timestamp': int(time.time())
                })}\n\n"
                time.sleep(5)
            except Exception as e:
                logger.error(f"SSE error: {e}")
                time.sleep(10)
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)