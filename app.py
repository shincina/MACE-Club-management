from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from functools import wraps
import os
import datetime

app = Flask(__name__)
app.config.from_object(Config)
mysql = MySQL(app)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Access denied.', 'error')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for(session['role'] + '_dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role     = request.form.get('role', '').strip()   # student / faculty / admin

        cur = mysql.connection.cursor()

        if role == 'student':
            cur.execute("SELECT * FROM students WHERE email = %s", [email])
            user = cur.fetchone()
            if user and user['password'] == password:   # swap for check_password_hash in production
                session['user_id']  = user['reg_no']
                session['role']     = 'student'
                session['name']     = user['name']
                session['dept_id']  = user['dept_id']
                return redirect(url_for('student_dashboard'))

        elif role == 'faculty':
            cur.execute("SELECT * FROM faculty WHERE email = %s", [email])
            user = cur.fetchone()
            if user and user['password'] == password:
                session['user_id']       = user['faculty_id']
                session['role']          = 'faculty'
                session['name']          = user['faculty_name']
                session['class_incharge']= user['class_incharge']
                # Check if this faculty member is a coordinator of any club
                cur.execute("""
                    SELECT m.club_id FROM membership m
                    WHERE m.student_id = %s AND m.role = 'coordinator' AND m.status = 'approved'
                """, [user['faculty_id']])
                # faculty are not coordinators — coordinators are students
                return redirect(url_for('faculty_dashboard'))

        elif role == 'admin':
            cur.execute("SELECT * FROM admins WHERE email = %s", [email])
            user = cur.fetchone()
            if user and user['password'] == password:
                session['user_id'] = user['admin_id']
                session['role']    = 'admin'
                session['name']    = user['name']
                return redirect(url_for('admin_dashboard'))

        flash('Invalid email, password, or role.', 'error')
        cur.close()

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# ─────────────────────────────────────────────
# STUDENT ROUTES
# ─────────────────────────────────────────────

@app.route('/student/dashboard')
@login_required
@role_required('student')
def student_dashboard():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("SELECT s.*, d.dept_name FROM students s LEFT JOIN departments d ON s.dept_id=d.dept_id WHERE s.reg_no=%s", [student_id])
    student = cur.fetchone()

    cur.execute("SELECT COUNT(*) as cnt FROM membership WHERE student_id=%s AND status='approved'", [student_id])
    clubs_count = cur.fetchone()['cnt']

    cur.execute("""
        SELECT e.*, c.club_name FROM events e
        JOIN event_attendance ea ON e.event_id = ea.event_id
        JOIN clubs c ON e.club_id = c.club_id
        WHERE ea.student_id = %s AND e.event_date >= CURDATE() AND e.status = 'approved'
        ORDER BY e.event_date ASC LIMIT 5
    """, [student_id])
    upcoming_events = cur.fetchall()

    cur.execute("""
        SELECT e.event_name, e.event_date, ea.attendance_status
        FROM event_attendance ea
        JOIN events e ON ea.event_id = e.event_id
        WHERE ea.student_id = %s ORDER BY e.event_date DESC LIMIT 5
    """, [student_id])
    recent_attendance = cur.fetchall()

    cur.execute("""
        SELECT a.title, a.message, a.created_date, c.club_name
        FROM announcements a
        LEFT JOIN clubs c ON a.club_id = c.club_id
        WHERE a.club_id IN (
            SELECT club_id FROM membership WHERE student_id=%s AND status='approved'
        )
        ORDER BY a.created_date DESC LIMIT 5
    """, [student_id])
    announcements = cur.fetchall()

    progress = min(student['total_points'], 100)
    cur.close()
    return render_template('student/dashboard.html',
        student=student, clubs_count=clubs_count,
        upcoming_events=upcoming_events, recent_attendance=recent_attendance,
        announcements=announcements, progress=progress)


@app.route('/student/clubs')
@login_required
@role_required('student')
def view_clubs():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT c.*, f.faculty_name,
            (SELECT COUNT(*) FROM membership WHERE club_id=c.club_id AND status='approved') as member_count,
            (SELECT status FROM membership WHERE club_id=c.club_id AND student_id=%s) as my_status
        FROM clubs c
        JOIN faculty f ON c.faculty_incharge = f.faculty_id
        WHERE c.status = 'Active'
        ORDER BY c.club_name
    """, [student_id])
    clubs = cur.fetchall()
    cur.close()
    return render_template('student/clubs.html', clubs=clubs)


@app.route('/student/my_clubs')
@login_required
@role_required('student')
def my_clubs():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT c.*, m.role, m.join_date, m.status as mem_status, f.faculty_name
        FROM membership m
        JOIN clubs c ON m.club_id = c.club_id
        JOIN faculty f ON c.faculty_incharge = f.faculty_id
        WHERE m.student_id = %s
        ORDER BY m.join_date DESC
    """, [student_id])
    my_clubs_list = cur.fetchall()
    cur.close()
    return render_template('student/my_clubs.html', my_clubs=my_clubs_list)


@app.route('/student/join_club/<int:club_id>', methods=['POST'])
@login_required
@role_required('student')
def join_club(club_id):
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    # Max 5 clubs rule
    cur.execute("SELECT COUNT(*) as cnt FROM membership WHERE student_id=%s AND status != 'rejected'", [student_id])
    count = cur.fetchone()['cnt']
    if count >= 5:
        flash('You can join a maximum of 5 clubs only!', 'error')
        return redirect(url_for('view_clubs'))

    # Already a member?
    cur.execute("SELECT membership_id FROM membership WHERE student_id=%s AND club_id=%s", [student_id, club_id])
    existing = cur.fetchone()
    if existing:
        flash('You have already requested or joined this club.', 'error')
        return redirect(url_for('view_clubs'))

    cur.execute("""
        INSERT INTO membership (student_id, club_id, role, join_date, status)
        VALUES (%s, %s, 'member', CURDATE(), 'pending')
    """, [student_id, club_id])
    mysql.connection.commit()
    cur.close()
    flash('Membership request sent! Waiting for coordinator approval.', 'success')
    return redirect(url_for('view_clubs'))


@app.route('/student/leave_club/<int:club_id>', methods=['POST'])
@login_required
@role_required('student')
def leave_club(club_id):
    cur = mysql.connection.cursor()
    student_id = session['user_id']
    cur.execute("DELETE FROM membership WHERE student_id=%s AND club_id=%s", [student_id, club_id])
    mysql.connection.commit()
    cur.close()
    flash('You have left the club.', 'success')
    return redirect(url_for('my_clubs'))


@app.route('/student/events')
@login_required
@role_required('student')
def student_events():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT e.*, c.club_name,
            (SELECT COUNT(*) FROM event_attendance WHERE event_id=e.event_id) as registered_count,
            (SELECT attendance_id FROM event_attendance WHERE event_id=e.event_id AND student_id=%s) as is_registered
        FROM events e
        JOIN clubs c ON e.club_id = c.club_id
        WHERE e.status = 'approved' AND e.event_date >= CURDATE()
        ORDER BY e.event_date ASC
    """, [student_id])
    events = cur.fetchall()
    cur.close()
    return render_template('student/events.html', events=events)


@app.route('/student/register_event/<int:event_id>', methods=['POST'])
@login_required
@role_required('student')
def register_event(event_id):
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    # Check max participants
    cur.execute("SELECT max_participants FROM events WHERE event_id=%s", [event_id])
    event = cur.fetchone()
    cur.execute("SELECT COUNT(*) as cnt FROM event_attendance WHERE event_id=%s", [event_id])
    current = cur.fetchone()['cnt']

    if event and current >= event['max_participants']:
        flash('Event is full!', 'error')
        return redirect(url_for('student_events'))

    cur.execute("""
        INSERT INTO event_attendance (event_id, student_id, attendance_status, payment_status)
        VALUES (%s, %s, 'absent', 'not_paid')
    """, [event_id, student_id])
    mysql.connection.commit()
    cur.close()
    flash('Successfully registered for the event!', 'success')
    return redirect(url_for('student_events'))


@app.route('/student/my_events')
@login_required
@role_required('student')
def my_events():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT e.*, c.club_name, ea.attendance_status, ea.payment_status
        FROM event_attendance ea
        JOIN events e ON ea.event_id = e.event_id
        JOIN clubs c ON e.club_id = c.club_id
        WHERE ea.student_id = %s
        ORDER BY e.event_date DESC
    """, [student_id])
    my_events_list = cur.fetchall()
    cur.close()
    return render_template('student/my_events.html', my_events=my_events_list)


@app.route('/student/activity_points')
@login_required
@role_required('student')
def activity_points():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("SELECT total_points FROM students WHERE reg_no=%s", [student_id])
    student = cur.fetchone()

    cur.execute("""
        SELECT ap.*, e.event_name, cert.certificate_type, cert.activity_category
        FROM activity_points ap
        LEFT JOIN events e ON ap.event_id = e.event_id
        LEFT JOIN certificates cert ON ap.certificate_id = cert.certificate_id
        WHERE ap.student_id = %s
        ORDER BY ap.date_awarded DESC
    """, [student_id])
    history = cur.fetchall()

    progress = min(student['total_points'], 100)
    cur.close()
    return render_template('student/activity_points.html',
        total_points=student['total_points'], history=history, progress=progress)


@app.route('/student/certificates')
@login_required
@role_required('student')
def my_certificates():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT cert.*, f.faculty_name as verified_by_name
        FROM certificates cert
        LEFT JOIN faculty f ON cert.verified_by = f.faculty_id
        WHERE cert.student_id = %s
        ORDER BY cert.upload_date DESC
    """, [student_id])
    certs = cur.fetchall()
    cur.close()
    return render_template('student/certificates.html', certificates=certs)


@app.route('/student/upload_certificate', methods=['GET', 'POST'])
@login_required
@role_required('student')
def upload_certificate():
    if request.method == 'POST':
        cert_type = request.form.get('certificate_type')
        category  = request.form.get('activity_category')
        file      = request.files.get('certificate_file')

        if not file or file.filename == '':
            flash('Please select a file.', 'error')
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash('Only PDF, PNG, JPG files are allowed.', 'error')
            return redirect(request.url)

        filename = secure_filename(f"{session['user_id']}_{int(datetime.datetime.now().timestamp())}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO certificates (student_id, certificate_type, file_path, status, activity_category)
            VALUES (%s, %s, %s, 'pending', %s)
        """, [session['user_id'], cert_type, filepath, category])
        mysql.connection.commit()
        cur.close()
        flash('Certificate uploaded successfully! Awaiting faculty approval.', 'success')
        return redirect(url_for('my_certificates'))

    return render_template('student/upload_certificate.html')


@app.route('/student/profile')
@login_required
@role_required('student')
def student_profile():
    cur = mysql.connection.cursor()
    cur.execute("SELECT s.*, d.dept_name FROM students s LEFT JOIN departments d ON s.dept_id=d.dept_id WHERE s.reg_no=%s", [session['user_id']])
    student = cur.fetchone()
    cur.close()
    return render_template('student/profile.html', student=student)


@app.route('/student/edit_profile', methods=['GET', 'POST'])
@login_required
@role_required('student')
def edit_profile():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        phone = request.form.get('phone')
        cur.execute("UPDATE students SET phone=%s WHERE reg_no=%s", [phone, session['user_id']])
        mysql.connection.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('student_profile'))
    cur.execute("SELECT * FROM students WHERE reg_no=%s", [session['user_id']])
    student = cur.fetchone()
    cur.close()
    return render_template('student/edit_profile.html', student=student)


@app.route('/student/announcements')
@login_required
@role_required('student')
def student_announcements():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT a.*, c.club_name, e.event_name
        FROM announcements a
        LEFT JOIN clubs c ON a.club_id = c.club_id
        LEFT JOIN events e ON a.event_id = e.event_id
        WHERE a.club_id IN (
            SELECT club_id FROM membership WHERE student_id=%s AND status='approved'
        )
        OR a.event_id IN (
            SELECT event_id FROM event_attendance WHERE student_id=%s
        )
        ORDER BY a.created_date DESC
    """, [student_id, student_id])
    announcements = cur.fetchall()
    cur.close()
    return render_template('student/announcements.html', announcements=announcements)


# ─────────────────────────────────────────────
# FACULTY ROUTES
# ─────────────────────────────────────────────

@app.route('/faculty/dashboard')
@login_required
@role_required('faculty')
def faculty_dashboard():
    cur = mysql.connection.cursor()
    fac_id = session['user_id']

    # Clubs this faculty is in-charge of
    cur.execute("""
        SELECT c.*, COUNT(m.membership_id) as member_count
        FROM clubs c
        LEFT JOIN membership m ON c.club_id = m.club_id AND m.status = 'approved'
        WHERE c.faculty_incharge = %s
        GROUP BY c.club_id
    """, [fac_id])
    my_clubs = cur.fetchall()

    # Pending event approvals for their clubs
    cur.execute("""
        SELECT e.*, c.club_name FROM events e
        JOIN clubs c ON e.club_id = c.club_id
        WHERE c.faculty_incharge = %s AND e.status = 'pending'
        ORDER BY e.event_date ASC
    """, [fac_id])
    pending_events = cur.fetchall()

    # Pending certificates
    cur.execute("""
        SELECT cert.*, s.name as student_name, s.semester, s.reg_no
        FROM certificates cert
        JOIN students s ON cert.student_id = s.reg_no
        WHERE cert.status = 'pending'
        ORDER BY cert.upload_date DESC
    """)
    pending_certs = cur.fetchall()

    cur.close()
    return render_template('faculty/dashboard.html',
        my_clubs=my_clubs, pending_events=pending_events, pending_certs=pending_certs)


@app.route('/faculty/approve_event/<int:event_id>', methods=['POST'])
@login_required
@role_required('faculty')
def approve_event(event_id):
    action  = request.form.get('action')
    status  = 'approved' if action == 'approve' else 'rejected'
    cur = mysql.connection.cursor()
    cur.execute("UPDATE events SET status=%s WHERE event_id=%s", [status, event_id])
    mysql.connection.commit()
    cur.close()
    flash(f'Event has been {status}.', 'success')
    return redirect(url_for('faculty_dashboard'))


@app.route('/faculty/approve_cert/<int:cert_id>', methods=['POST'])
@login_required
@role_required('faculty')
def approve_cert(cert_id):
    action  = request.form.get('action')
    remarks = request.form.get('remarks', '')
    fac_id  = session['user_id']
    cur = mysql.connection.cursor()

    if action == 'approve':
        # Determine points based on category
        cur.execute("SELECT * FROM certificates WHERE certificate_id=%s", [cert_id])
        cert = cur.fetchone()
        points_map = {
            'internship':       20,
            'industrial_visit': 15,
            'nptel':            5,
            'competition_win':  5,
            'workshop':         5,
            'hackathon':        5,
        }
        pts = points_map.get(cert['activity_category'], 5)

        cur.execute("""
            UPDATE certificates
            SET status='approved', verified_by=%s, points_awarded=%s, remarks=%s
            WHERE certificate_id=%s
        """, [fac_id, pts, remarks, cert_id])

        # Insert into activity_points
        cur.execute("""
            INSERT INTO activity_points (student_id, certificate_id, points, description)
            VALUES (%s, %s, %s, %s)
        """, [cert['student_id'], cert_id, pts, cert['activity_category']])

        # Update student total
        cur.execute("UPDATE students SET total_points = total_points + %s WHERE reg_no=%s",
                    [pts, cert['student_id']])
    else:
        cur.execute("""
            UPDATE certificates SET status='rejected', verified_by=%s, remarks=%s
            WHERE certificate_id=%s
        """, [fac_id, remarks, cert_id])

    mysql.connection.commit()
    cur.close()
    flash(f'Certificate {action}d successfully.', 'success')
    return redirect(url_for('faculty_dashboard'))


@app.route('/faculty/view_events')
@login_required
@role_required('faculty')
def faculty_view_events():
    cur = mysql.connection.cursor()
    fac_id = session['user_id']
    cur.execute("""
        SELECT e.*, c.club_name FROM events e
        JOIN clubs c ON e.club_id = c.club_id
        WHERE c.faculty_incharge = %s
        ORDER BY e.event_date DESC
    """, [fac_id])
    events = cur.fetchall()
    cur.close()
    return render_template('faculty/events.html', events=events)


@app.route('/faculty/view_club')
@login_required
@role_required('faculty')
def faculty_view_club():
    cur = mysql.connection.cursor()
    fac_id = session['user_id']
    cur.execute("""
        SELECT m.*, s.name, s.reg_no, s.semester, c.club_name
        FROM membership m
        JOIN students s ON m.student_id = s.reg_no
        JOIN clubs c ON m.club_id = c.club_id
        WHERE c.faculty_incharge = %s AND m.status = 'approved'
        ORDER BY c.club_name, m.role DESC
    """, [fac_id])
    members = cur.fetchall()
    cur.close()
    return render_template('faculty/club_members.html', members=members)


@app.route('/faculty/view_class')
@login_required
@role_required('faculty')
def faculty_view_class():
    cur = mysql.connection.cursor()
    class_code = session.get('class_incharge')
    if not class_code:
        flash('You are not assigned as a class in-charge.', 'error')
        return redirect(url_for('faculty_dashboard'))

    cur.execute("""
        SELECT s.*, d.dept_name FROM students s
        LEFT JOIN departments d ON s.dept_id = d.dept_id
        WHERE s.semester = %s
        ORDER BY s.reg_no
    """, [class_code])
    students = cur.fetchall()
    cur.close()
    return render_template('faculty/view_class.html', students=students, class_code=class_code)


# ─────────────────────────────────────────────
# COORDINATOR ROUTES
# ─────────────────────────────────────────────

@app.route('/coordinator/dashboard')
@login_required
@role_required('student')   # coordinators are students with coordinator role
def coordinator_dashboard():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    # Check if this student is actually a coordinator
    cur.execute("""
        SELECT m.club_id, c.club_name FROM membership m
        JOIN clubs c ON m.club_id = c.club_id
        WHERE m.student_id = %s AND m.role = 'coordinator' AND m.status = 'approved'
    """, [student_id])
    coord_clubs = cur.fetchall()
    if not coord_clubs:
        flash('You are not a coordinator of any club.', 'error')
        return redirect(url_for('student_dashboard'))

    club_ids = [c['club_id'] for c in coord_clubs]
    format_strings = ','.join(['%s'] * len(club_ids))

    # Pending membership requests
    cur.execute(f"""
        SELECT m.*, s.name, s.reg_no, s.semester, c.club_name
        FROM membership m
        JOIN students s ON m.student_id = s.reg_no
        JOIN clubs c ON m.club_id = c.club_id
        WHERE m.club_id IN ({format_strings}) AND m.status = 'pending'
    """, club_ids)
    pending_memberships = cur.fetchall()

    # Club events
    cur.execute(f"""
        SELECT e.*, c.club_name,
            (SELECT COUNT(*) FROM event_attendance WHERE event_id=e.event_id) as registered_count
        FROM events e
        JOIN clubs c ON e.club_id = c.club_id
        WHERE e.club_id IN ({format_strings})
        ORDER BY e.event_date DESC
    """, club_ids)
    club_events = cur.fetchall()

    cur.close()
    return render_template('coordinator/dashboard.html',
        coord_clubs=coord_clubs, pending_memberships=pending_memberships, club_events=club_events)


@app.route('/coordinator/create_event', methods=['GET', 'POST'])
@login_required
@role_required('student')
def create_event():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    # Get coordinator's clubs
    cur.execute("""
        SELECT m.club_id, c.club_name FROM membership m
        JOIN clubs c ON m.club_id = c.club_id
        WHERE m.student_id = %s AND m.role = 'coordinator' AND m.status = 'approved'
    """, [student_id])
    coord_clubs = cur.fetchall()

    if not coord_clubs:
        flash('Only coordinators can create events.', 'error')
        return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        club_id         = request.form.get('club_id')
        event_name      = request.form.get('event_name')
        event_date      = request.form.get('event_date')
        event_time      = request.form.get('event_time')
        location        = request.form.get('location')
        description     = request.form.get('description')
        max_participants= request.form.get('max_participants')
        points          = request.form.get('points')

        cur.execute("""
            INSERT INTO events (club_id, event_name, event_date, event_time,
                location, description, max_participants, points, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
        """, [club_id, event_name, event_date, event_time,
              location, description, max_participants, points, student_id])
        mysql.connection.commit()
        cur.close()
        flash('Event created and sent to faculty for approval!', 'success')
        return redirect(url_for('coordinator_dashboard'))

    cur.close()
    return render_template('coordinator/create_event.html', coord_clubs=coord_clubs)


@app.route('/coordinator/approve_member/<int:membership_id>', methods=['POST'])
@login_required
@role_required('student')
def approve_member(membership_id):
    action = request.form.get('action')
    status = 'approved' if action == 'approve' else 'rejected'
    cur = mysql.connection.cursor()
    cur.execute("UPDATE membership SET status=%s WHERE membership_id=%s", [status, membership_id])
    mysql.connection.commit()
    cur.close()
    flash(f'Membership {status}.', 'success')
    return redirect(url_for('coordinator_dashboard'))


@app.route('/coordinator/mark_attendance/<int:event_id>', methods=['GET', 'POST'])
@login_required
@role_required('student')
def mark_attendance(event_id):
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        present_ids = request.form.getlist('present_students')

        cur.execute("SELECT points FROM events WHERE event_id=%s", [event_id])
        event = cur.fetchone()
        event_pts = event['points'] if event else 0

        cur.execute("SELECT student_id FROM event_attendance WHERE event_id=%s", [event_id])
        all_students = [row['student_id'] for row in cur.fetchall()]

        for sid in all_students:
            status = 'present' if sid in present_ids else 'absent'
            cur.execute("""
                UPDATE event_attendance SET attendance_status=%s
                WHERE event_id=%s AND student_id=%s
            """, [status, event_id, sid])

            if status == 'present' and event_pts > 0:
                # Avoid double-awarding
                cur.execute("""
                    SELECT point_id FROM activity_points
                    WHERE student_id=%s AND event_id=%s
                """, [sid, event_id])
                already = cur.fetchone()
                if not already:
                    cur.execute("""
                        INSERT INTO activity_points (student_id, event_id, points, description)
                        VALUES (%s, %s, %s, 'Event attendance')
                    """, [sid, event_id, event_pts])
                    cur.execute("""
                        UPDATE students SET total_points = total_points + %s WHERE reg_no=%s
                    """, [event_pts, sid])

        mysql.connection.commit()
        cur.close()
        flash('Attendance marked and points awarded to present students!', 'success')
        return redirect(url_for('coordinator_dashboard'))

    # GET — show attendance form
    cur.execute("SELECT * FROM events WHERE event_id=%s", [event_id])
    event = cur.fetchone()

    cur.execute("""
        SELECT ea.*, s.name, s.reg_no FROM event_attendance ea
        JOIN students s ON ea.student_id = s.reg_no
        WHERE ea.event_id = %s
    """, [event_id])
    registrations = cur.fetchall()
    cur.close()
    return render_template('coordinator/mark_attendance.html', event=event, registrations=registrations)


@app.route('/coordinator/members')
@login_required
@role_required('student')
def coordinator_members():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT m.*, s.name, s.reg_no, s.semester, s.total_points, c.club_name
        FROM membership m
        JOIN students s ON m.student_id = s.reg_no
        JOIN clubs c ON m.club_id = c.club_id
        WHERE m.club_id IN (
            SELECT club_id FROM membership WHERE student_id=%s AND role='coordinator' AND status='approved'
        ) AND m.status = 'approved'
        ORDER BY m.role DESC, s.name ASC
    """, [student_id])
    members = cur.fetchall()
    cur.close()
    return render_template('coordinator/members.html', members=members)


@app.route('/coordinator/post_announcement', methods=['GET', 'POST'])
@login_required
@role_required('student')
def post_announcement():
    cur = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT m.club_id, c.club_name FROM membership m
        JOIN clubs c ON m.club_id = c.club_id
        WHERE m.student_id = %s AND m.role = 'coordinator' AND m.status = 'approved'
    """, [student_id])
    coord_clubs = cur.fetchall()

    if request.method == 'POST':
        title   = request.form.get('title')
        message = request.form.get('message')
        club_id = request.form.get('club_id')

        cur.execute("""
            INSERT INTO announcements (title, message, club_id, created_by)
            VALUES (%s, %s, %s, %s)
        """, [title, message, club_id, session['name']])
        mysql.connection.commit()
        cur.close()
        flash('Announcement posted!', 'success')
        return redirect(url_for('coordinator_dashboard'))

    cur.close()
    return render_template('coordinator/post_announcement.html', coord_clubs=coord_clubs)


# ─────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) as cnt FROM students")
    total_students = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM clubs WHERE status='Active'")
    active_clubs = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM events WHERE status='approved'")
    total_events = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM membership WHERE status='pending'")
    pending_memberships = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM students WHERE total_points >= 100")
    eligible_students = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM certificates WHERE status='pending'")
    pending_certs = cur.fetchone()['cnt']

    cur.execute("""
        SELECT c.club_name, COUNT(m.membership_id) as members
        FROM clubs c LEFT JOIN membership m ON c.club_id=m.club_id AND m.status='approved'
        WHERE c.status='Active' GROUP BY c.club_id ORDER BY members DESC LIMIT 5
    """)
    top_clubs = cur.fetchall()

    cur.close()
    return render_template('admin/dashboard.html',
        total_students=total_students, active_clubs=active_clubs,
        total_events=total_events, pending_memberships=pending_memberships,
        eligible_students=eligible_students, pending_certs=pending_certs,
        top_clubs=top_clubs)


@app.route('/admin/students', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_students():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            cur.execute("""
                INSERT INTO students (reg_no, name, email, phone, dept_id, semester, password, total_points)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 0)
            """, [request.form['reg_no'], request.form['name'], request.form['email'],
                  request.form['phone'], request.form['dept_id'],
                  request.form['semester'], request.form['password']])
            mysql.connection.commit()
            flash('Student added successfully!', 'success')
        elif action == 'delete':
            cur.execute("DELETE FROM students WHERE reg_no=%s", [request.form['reg_no']])
            mysql.connection.commit()
            flash('Student deleted.', 'success')

    cur.execute("""
        SELECT s.*, d.dept_name FROM students s
        LEFT JOIN departments d ON s.dept_id = d.dept_id
        ORDER BY s.reg_no
    """)
    students = cur.fetchall()

    cur.execute("SELECT * FROM departments ORDER BY dept_name")
    departments = cur.fetchall()
    cur.close()
    return render_template('admin/students.html', students=students, departments=departments)


@app.route('/admin/faculty', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_faculty():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            cur.execute("""
                INSERT INTO faculty (faculty_name, email, department, class_incharge, password)
                VALUES (%s, %s, %s, %s, %s)
            """, [request.form['faculty_name'], request.form['email'],
                  request.form['department'], request.form.get('class_incharge') or None,
                  request.form['password']])
            mysql.connection.commit()
            flash('Faculty added!', 'success')

    cur.execute("SELECT * FROM faculty ORDER BY faculty_name")
    faculty_list = cur.fetchall()
    cur.close()
    return render_template('admin/faculty.html', faculty_list=faculty_list)


@app.route('/admin/clubs', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_clubs():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            cur.execute("""
                INSERT INTO clubs (club_name, club_type, faculty_incharge, created_date, status)
                VALUES (%s, %s, %s, CURDATE(), 'Active')
            """, [request.form['club_name'], request.form['club_type'], request.form['faculty_incharge']])
            mysql.connection.commit()
            flash('Club created!', 'success')

    cur.execute("""
        SELECT c.*, f.faculty_name,
            (SELECT COUNT(*) FROM membership WHERE club_id=c.club_id AND status='approved') as members
        FROM clubs c JOIN faculty f ON c.faculty_incharge=f.faculty_id
        ORDER BY c.club_name
    """)
    clubs = cur.fetchall()

    cur.execute("SELECT * FROM faculty ORDER BY faculty_name")
    faculty_list = cur.fetchall()
    cur.close()
    return render_template('admin/clubs.html', clubs=clubs, faculty_list=faculty_list)


@app.route('/admin/toggle_club/<int:club_id>')
@login_required
@role_required('admin')
def toggle_club(club_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT status FROM clubs WHERE club_id=%s", [club_id])
    row = cur.fetchone()
    new_status = 'Inactive' if row['status'] == 'Active' else 'Active'
    cur.execute("UPDATE clubs SET status=%s WHERE club_id=%s", [new_status, club_id])
    mysql.connection.commit()
    cur.close()
    flash(f'Club status changed to {new_status}.', 'success')
    return redirect(url_for('admin_clubs'))


@app.route('/admin/departments', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_departments():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            cur.execute("""
                INSERT INTO departments (dept_name, dept_code, hod_name)
                VALUES (%s, %s, %s)
            """, [request.form['dept_name'], request.form['dept_code'], request.form['hod_name']])
            mysql.connection.commit()
            flash('Department added!', 'success')

    cur.execute("SELECT * FROM departments ORDER BY dept_name")
    departments = cur.fetchall()
    cur.close()
    return render_template('admin/departments.html', departments=departments)


@app.route('/admin/events')
@login_required
@role_required('admin')
def admin_events():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT e.*, c.club_name, f.faculty_name
        FROM events e
        JOIN clubs c ON e.club_id = c.club_id
        JOIN faculty f ON c.faculty_incharge = f.faculty_id
        ORDER BY e.event_date DESC
    """)
    events = cur.fetchall()
    cur.close()
    return render_template('admin/events.html', events=events)


@app.route('/admin/memberships')
@login_required
@role_required('admin')
def admin_memberships():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT m.*, s.name as student_name, s.reg_no, c.club_name
        FROM membership m
        JOIN students s ON m.student_id = s.reg_no
        JOIN clubs c ON m.club_id = c.club_id
        ORDER BY m.join_date DESC
    """)
    memberships = cur.fetchall()
    cur.close()
    return render_template('admin/memberships.html', memberships=memberships)


@app.route('/admin/reports')
@login_required
@role_required('admin')
def admin_reports():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT s.reg_no, s.name, d.dept_name, s.semester, s.total_points,
            CASE WHEN s.total_points >= 100 THEN 'Eligible' ELSE 'Not Eligible' END as grad_status
        FROM students s
        JOIN departments d ON s.dept_id = d.dept_id
        ORDER BY s.total_points DESC
    """)
    report = cur.fetchall()

    cur.execute("SELECT COUNT(*) as cnt FROM students WHERE total_points >= 100")
    eligible = cur.fetchone()['cnt']

    cur.execute("SELECT COUNT(*) as cnt FROM students")
    total = cur.fetchone()['cnt']

    cur.execute("""
        SELECT d.dept_name, AVG(s.total_points) as avg_pts
        FROM students s JOIN departments d ON s.dept_id=d.dept_id
        GROUP BY d.dept_id ORDER BY avg_pts DESC
    """)
    dept_stats = cur.fetchall()

    cur.close()
    return render_template('admin/reports.html',
        report=report, eligible=eligible, total=total, dept_stats=dept_stats)


@app.route('/admin/announcements', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_announcements():
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO announcements (title, message, created_by)
            VALUES (%s, %s, 'Admin')
        """, [request.form['title'], request.form['message']])
        mysql.connection.commit()
        flash('System announcement posted!', 'success')

    cur.execute("SELECT * FROM announcements ORDER BY created_date DESC")
    announcements = cur.fetchall()
    cur.close()
    return render_template('admin/announcements.html', announcements=announcements)


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == '__main__':
    # Make sure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)