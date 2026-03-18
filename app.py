from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from config import Config
from functools import wraps
import os
import datetime

app = Flask(__name__)
app.config.from_object(Config)
mysql = MySQL(app)

# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


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


def coordinator_required(f):
    """
    Coordinator routes are student routes — same role='student'.
    Extra check: session['is_coordinator'] must be True.
    The student keeps full student access PLUS these coordinator routes.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Access denied.', 'error')
            return redirect(url_for('login'))
        if not session.get('is_coordinator'):
            flash('You are not a coordinator of any club.', 'error')
            return redirect(url_for('student_dashboard'))
        return f(*args, **kwargs)
    return decorated


def _load_coordinator_data(cur, student_id):
    """
    Fetches all coordinator-related data for a student who is a coordinator.
    Returns (coord_clubs, pending_memberships, club_events, member_counts).
    Returns empty structures if not a coordinator.
    """
    if not session.get('is_coordinator'):
        return [], [], [], {}

    cur.execute("""
        SELECT m.club_id, c.club_name, c.club_type, c.status
        FROM membership m
        JOIN clubs c ON m.club_id = c.club_id
        WHERE m.student_id = %s AND m.role = 'coordinator' AND m.status = 'approved'
    """, [student_id])
    coord_clubs = cur.fetchall()

    if not coord_clubs:
        session['is_coordinator'] = False
        session['coord_club_ids'] = []
        return [], [], [], {}

    club_ids     = [c['club_id'] for c in coord_clubs]
    placeholders = ','.join(['%s'] * len(club_ids))

    cur.execute(f"""
        SELECT m.*, s.name, s.reg_no, s.semester, c.club_name
        FROM membership m
        JOIN students s ON m.student_id = s.reg_no
        JOIN clubs    c ON m.club_id    = c.club_id
        WHERE m.club_id IN ({placeholders}) AND m.status = 'pending'
        ORDER BY m.join_date DESC
    """, club_ids)
    pending_memberships = cur.fetchall()

    cur.execute(f"""
        SELECT e.*, c.club_name,
               (SELECT COUNT(*) FROM event_attendance
                WHERE event_id = e.event_id) AS registered_count
        FROM events e
        JOIN clubs c ON e.club_id = c.club_id
        WHERE e.club_id IN ({placeholders})
        ORDER BY e.event_date DESC
    """, club_ids)
    club_events = cur.fetchall()

    cur.execute(f"""
        SELECT club_id, COUNT(*) AS cnt
        FROM membership
        WHERE club_id IN ({placeholders}) AND status = 'approved'
        GROUP BY club_id
    """, club_ids)
    member_counts = {row['club_id']: row['cnt'] for row in cur.fetchall()}

    return coord_clubs, pending_memberships, club_events, member_counts


# ═══════════════════════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':   return redirect(url_for('admin_dashboard'))
        if role == 'faculty': return redirect(url_for('faculty_dashboard'))
        if role == 'student': return redirect(url_for('student_dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role     = request.form.get('role',  '').strip()
        cur      = mysql.connection.cursor()

        # ── STUDENT (+ coordinator) ──────────────────────────────────────────
        if role == 'student':
            cur.execute("SELECT * FROM students WHERE email = %s", [email])
            user = cur.fetchone()
            if user and user['password'] == password:
                session['user_id'] = user['reg_no']
                session['role']    = 'student'        # always 'student', never changes
                session['name']    = user['name']
                session['dept_id'] = user['dept_id']

                # Check coordinator status
                cur.execute("""
                    SELECT m.club_id, c.club_name
                    FROM membership m
                    JOIN clubs c ON m.club_id = c.club_id
                    WHERE m.student_id = %s
                      AND m.role = 'coordinator'
                      AND m.status = 'approved'
                """, [user['reg_no']])
                coord_rows = cur.fetchall()

                session['is_coordinator'] = bool(coord_rows)
                session['coord_club_ids'] = [r['club_id'] for r in coord_rows]

                cur.close()
                # ── Single entry point for ALL students ──────────────────────
                return redirect(url_for('student_dashboard'))

        # ── FACULTY ──────────────────────────────────────────────────────────
        elif role == 'faculty':
            cur.execute("SELECT * FROM faculty WHERE email = %s", [email])
            user = cur.fetchone()
            if user and user['password'] == password:
                session['user_id']        = user['faculty_id']
                session['role']           = 'faculty'
                session['name']           = user['faculty_name']
                session['class_incharge'] = user['class_incharge']
                cur.close()
                return redirect(url_for('faculty_dashboard'))

        # ── ADMIN ─────────────────────────────────────────────────────────────
        elif role == 'admin':
            cur.execute("SELECT * FROM admins WHERE email = %s", [email])
            user = cur.fetchone()
            if user and user['password'] == password:
                session['user_id'] = user['admin_id']
                session['role']    = 'admin'
                session['name']    = user['name']
                cur.close()
                return redirect(url_for('admin_dashboard'))

        cur.close()
        flash('Invalid email, password, or role.', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    """
    Serve uploaded certificate files securely.
    Only logged-in users can access. Handles PDF, JPG, PNG correctly.
    """
    from flask import send_from_directory
    return send_from_directory(
        os.path.abspath(app.config['UPLOAD_FOLDER']),
        filename
    )


# ═══════════════════════════════════════════════════════════
# STUDENT DASHBOARD  ← coordinator also lands here
# Passes coordinator data when is_coordinator=True so the
# template can render the coordinator panel as an extra section.
# ═══════════════════════════════════════════════════════════

@app.route('/student/dashboard')
@login_required
@role_required('student')
def student_dashboard():
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    # Student data
    cur.execute("""
        SELECT s.*, d.dept_name
        FROM students s
        LEFT JOIN departments d ON s.dept_id = d.dept_id
        WHERE s.reg_no = %s
    """, [student_id])
    student = cur.fetchone()

    cur.execute("""
        SELECT COUNT(*) AS cnt FROM membership
        WHERE student_id = %s AND status = 'approved'
    """, [student_id])
    clubs_count = cur.fetchone()['cnt']

    cur.execute("""
        SELECT e.*, c.club_name
        FROM events e
        JOIN event_attendance ea ON e.event_id = ea.event_id
        JOIN clubs c ON e.club_id = c.club_id
        WHERE ea.student_id = %s
          AND e.event_date >= CURDATE()
          AND e.status = 'approved'
        ORDER BY e.event_date ASC LIMIT 5
    """, [student_id])
    upcoming_events = cur.fetchall()

    cur.execute("""
        SELECT e.event_name, e.event_date, ea.attendance_status
        FROM event_attendance ea
        JOIN events e ON ea.event_id = e.event_id
        WHERE ea.student_id = %s
        ORDER BY e.event_date DESC LIMIT 5
    """, [student_id])
    recent_attendance = cur.fetchall()

    cur.execute("""
        SELECT a.title, a.message, a.created_date, c.club_name
        FROM announcements a
        LEFT JOIN clubs c ON a.club_id = c.club_id
        WHERE a.club_id IN (
            SELECT club_id FROM membership
            WHERE student_id = %s AND status = 'approved'
        ) OR a.club_id IS NULL
        ORDER BY a.created_date DESC LIMIT 5
    """, [student_id])
    announcements = cur.fetchall()

    progress = min(student['total_points'], 100)

    # Coordinator data (empty when not a coordinator)
    coord_clubs, pending_memberships, club_events, member_counts = \
        _load_coordinator_data(cur, student_id)

    cur.close()
    return render_template('student/dashboard.html',
        # ── student data ────────────────────────────────
        student           = student,
        clubs_count       = clubs_count,
        upcoming_events   = upcoming_events,
        recent_attendance = recent_attendance,
        announcements     = announcements,
        progress          = progress,
        # ── coordinator data (empty lists when not coord) ──
        coord_clubs         = coord_clubs,
        pending_memberships = pending_memberships,
        club_events         = club_events,
        member_counts       = member_counts,
    )


# ═══════════════════════════════════════════════════════════
# STUDENT — CLUBS
# ═══════════════════════════════════════════════════════════

@app.route('/student/clubs')
@login_required
@role_required('student')
def view_clubs():
    cur        = mysql.connection.cursor()
    student_id = session['user_id']
    cur.execute("""
        SELECT c.*, f.faculty_name,
            (SELECT COUNT(*) FROM membership
             WHERE club_id = c.club_id AND status = 'approved') AS member_count,
            (SELECT status FROM membership
             WHERE club_id = c.club_id AND student_id = %s)    AS my_status
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
    cur        = mysql.connection.cursor()
    student_id = session['user_id']
    cur.execute("""
        SELECT c.*, m.role, m.join_date, m.status AS mem_status, f.faculty_name
        FROM membership m
        JOIN clubs   c ON m.club_id          = c.club_id
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
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT COUNT(*) AS cnt FROM membership
        WHERE student_id = %s AND status != 'rejected'
    """, [student_id])
    if cur.fetchone()['cnt'] >= 5:
        cur.close()
        flash('You can join a maximum of 5 clubs only!', 'error')
        return redirect(url_for('view_clubs'))

    cur.execute("""
        SELECT membership_id FROM membership
        WHERE student_id = %s AND club_id = %s
    """, [student_id, club_id])
    if cur.fetchone():
        cur.close()
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
    cur        = mysql.connection.cursor()
    student_id = session['user_id']
    cur.execute("DELETE FROM membership WHERE student_id = %s AND club_id = %s",
                [student_id, club_id])
    mysql.connection.commit()
    cur.close()
    flash('You have left the club.', 'success')
    return redirect(url_for('my_clubs'))


# ═══════════════════════════════════════════════════════════
# STUDENT — EVENTS
# ═══════════════════════════════════════════════════════════

@app.route('/student/events')
@login_required
@role_required('student')
def student_events():
    cur        = mysql.connection.cursor()
    student_id = session['user_id']
    cur.execute("""
        SELECT e.*, c.club_name,
            (SELECT COUNT(*) FROM event_attendance
             WHERE event_id = e.event_id)                             AS registered_count,
            (SELECT attendance_id FROM event_attendance
             WHERE event_id = e.event_id AND student_id = %s)         AS is_registered
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
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT attendance_id FROM event_attendance
        WHERE event_id = %s AND student_id = %s
    """, [event_id, student_id])
    if cur.fetchone():
        cur.close()
        flash('You are already registered for this event.', 'error')
        return redirect(url_for('student_events'))

    cur.execute("SELECT max_participants FROM events WHERE event_id = %s", [event_id])
    event = cur.fetchone()
    cur.execute("SELECT COUNT(*) AS cnt FROM event_attendance WHERE event_id = %s", [event_id])
    if event and cur.fetchone()['cnt'] >= event['max_participants']:
        cur.close()
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
    cur        = mysql.connection.cursor()
    student_id = session['user_id']
    cur.execute("""
        SELECT e.*, c.club_name, ea.attendance_status, ea.payment_status
        FROM event_attendance ea
        JOIN events e ON ea.event_id = e.event_id
        JOIN clubs  c ON e.club_id   = c.club_id
        WHERE ea.student_id = %s
        ORDER BY e.event_date DESC
    """, [student_id])
    my_events_list = cur.fetchall()
    cur.close()
    return render_template('student/my_events.html', my_events=my_events_list)


# ═══════════════════════════════════════════════════════════
# STUDENT — ACTIVITY POINTS & CERTIFICATES
# ═══════════════════════════════════════════════════════════

@app.route('/student/activity_points')
@login_required
@role_required('student')
def activity_points():
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("SELECT total_points FROM students WHERE reg_no = %s", [student_id])
    student = cur.fetchone()

    cur.execute("""
        SELECT ap.*, e.event_name, cert.certificate_type, cert.activity_category
        FROM activity_points ap
        LEFT JOIN events       e    ON ap.event_id       = e.event_id
        LEFT JOIN certificates cert ON ap.certificate_id = cert.certificate_id
        WHERE ap.student_id = %s
        ORDER BY ap.date_awarded DESC
    """, [student_id])
    history  = cur.fetchall()
    progress = min(student['total_points'], 100)
    cur.close()
    return render_template('student/activity_points.html',
        total_points=student['total_points'], history=history, progress=progress)


@app.route('/student/certificates')
@login_required
@role_required('student')
def my_certificates():
    """
    Student view of ALL their uploaded certificates.
    Filterable by status and type. Shows points earned per cert,
    linked event name, verifying faculty, and remarks.
    """
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    # ── Filter params ────────────────────────────────────────────────────────
    status_filter = request.args.get('status', 'all')     # all/pending/approved/rejected
    type_filter   = request.args.get('cert_type', 'all')  # all/event/self_initiative

    conditions = ["cert.student_id = %s"]
    params     = [student_id]

    if status_filter != 'all':
        conditions.append("cert.status = %s")
        params.append(status_filter)

    if type_filter != 'all':
        conditions.append("cert.certificate_type = %s")
        params.append(type_filter)

    where_clause = 'WHERE ' + ' AND '.join(conditions)

    cur.execute(f"""
        SELECT
            cert.*,
            f.faculty_name  AS verified_by_name,
            e.event_name,
            c.club_name
        FROM certificates cert
        LEFT JOIN faculty f ON cert.verified_by = f.faculty_id
        LEFT JOIN events  e ON cert.event_id    = e.event_id
        LEFT JOIN clubs   c ON e.club_id        = c.club_id
        {where_clause}
        ORDER BY cert.upload_date DESC
    """, params)
    certificates = cur.fetchall()

    # ── Summary counts (always unfiltered — for the filter bar badges) ───────
    cur.execute("""
        SELECT
            COUNT(*)                                     AS total,
            SUM(status = 'pending')                      AS pending,
            SUM(status = 'approved')                     AS approved,
            SUM(status = 'rejected')                     AS rejected,
            SUM(certificate_type = 'event')              AS event_certs,
            SUM(certificate_type = 'self_initiative')    AS self_certs,
            SUM(IFNULL(points_awarded, 0))               AS total_points_from_certs
        FROM certificates
        WHERE student_id = %s
    """, [student_id])
    counts = cur.fetchone()

    cur.close()
    return render_template('student/certificates.html',
        certificates  = certificates,
        counts        = counts,
        status_filter = status_filter,
        type_filter   = type_filter,
    )


@app.route('/student/certificates/<int:cert_id>')
@login_required
@role_required('student')
def certificate_detail(cert_id):
    """
    Full detail view of a single certificate.
    Students can only view their own certificates.
    """
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT
            cert.*,
            f.faculty_name  AS verified_by_name,
            e.event_name,
            e.event_date,
            c.club_name,
            ap.points       AS points_awarded_record,
            ap.date_awarded
        FROM certificates cert
        LEFT JOIN faculty        f  ON cert.verified_by  = f.faculty_id
        LEFT JOIN events         e  ON cert.event_id     = e.event_id
        LEFT JOIN clubs          c  ON e.club_id         = c.club_id
        LEFT JOIN activity_points ap ON ap.certificate_id = cert.certificate_id
        WHERE cert.certificate_id = %s AND cert.student_id = %s
    """, [cert_id, student_id])
    cert = cur.fetchone()

    if not cert:
        cur.close()
        flash('Certificate not found.', 'error')
        return redirect(url_for('my_certificates'))

    cur.close()
    return render_template('student/certificate_detail.html', cert=cert)


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

        filename = secure_filename(
            f"{session['user_id']}_{int(datetime.datetime.now().timestamp())}_{file.filename}"
        )
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO certificates
                (student_id, certificate_type, file_path, status, activity_category)
            VALUES (%s, %s, %s, 'pending', %s)
        """, [session['user_id'], cert_type, filename, category])  # store filename only
        mysql.connection.commit()
        cur.close()
        flash('Certificate uploaded! Awaiting faculty approval.', 'success')
        return redirect(url_for('my_certificates'))

    return render_template('student/upload_certificate.html')


# ═══════════════════════════════════════════════════════════
# STUDENT — PROFILE & ANNOUNCEMENTS
# ═══════════════════════════════════════════════════════════

@app.route('/student/profile')
@login_required
@role_required('student')
def student_profile():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT s.*, d.dept_name FROM students s
        LEFT JOIN departments d ON s.dept_id = d.dept_id
        WHERE s.reg_no = %s
    """, [session['user_id']])
    student = cur.fetchone()
    cur.close()
    return render_template('student/profile.html', student=student)


@app.route('/student/edit_profile', methods=['GET', 'POST'])
@login_required
@role_required('student')
def edit_profile():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        cur.execute("UPDATE students SET phone = %s WHERE reg_no = %s",
                    [request.form.get('phone'), session['user_id']])
        mysql.connection.commit()
        cur.close()
        flash('Profile updated!', 'success')
        return redirect(url_for('student_profile'))
    cur.execute("SELECT * FROM students WHERE reg_no = %s", [session['user_id']])
    student = cur.fetchone()
    cur.close()
    return render_template('student/edit_profile.html', student=student)


@app.route('/student/announcements')
@login_required
@role_required('student')
def student_announcements():
    cur        = mysql.connection.cursor()
    student_id = session['user_id']
    cur.execute("""
        SELECT a.*, c.club_name, e.event_name
        FROM announcements a
        LEFT JOIN clubs  c ON a.club_id  = c.club_id
        LEFT JOIN events e ON a.event_id = e.event_id
        WHERE a.club_id IN (
                SELECT club_id FROM membership
                WHERE student_id = %s AND status = 'approved'
            )
           OR a.event_id IN (
                SELECT event_id FROM event_attendance WHERE student_id = %s
            )
           OR a.club_id IS NULL
        ORDER BY a.created_date DESC
    """, [student_id, student_id])
    announcements = cur.fetchall()
    cur.close()
    return render_template('student/announcements.html', announcements=announcements)


# ═══════════════════════════════════════════════════════════
# COORDINATOR PANEL  (extra section — same student session)
#
# How it works:
#   • Coordinator logs in → role='student', is_coordinator=True
#   • Lands on student_dashboard which also renders coordinator panel
#   • /coordinator/panel is a dedicated full-page view of coordinator tools
#   • All student routes still work normally for a coordinator
# ═══════════════════════════════════════════════════════════

@app.route('/coordinator/panel')
@login_required
@coordinator_required
def coordinator_panel():
    """Full-page coordinator panel — accessible from student dashboard nav."""
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    coord_clubs, pending_memberships, club_events, member_counts = \
        _load_coordinator_data(cur, student_id)

    cur.close()
    return render_template('coordinator/panel.html',
        coord_clubs         = coord_clubs,
        pending_memberships = pending_memberships,
        club_events         = club_events,
        member_counts       = member_counts,
    )


@app.route('/coordinator/create_event', methods=['GET', 'POST'])
@login_required
@coordinator_required
def create_event():
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT m.club_id, c.club_name FROM membership m
        JOIN clubs c ON m.club_id = c.club_id
        WHERE m.student_id = %s AND m.role = 'coordinator' AND m.status = 'approved'
    """, [student_id])
    coord_clubs = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO events
                (club_id, event_name, event_date, event_time,
                 location, description, max_participants, points, status, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)
        """, [
            request.form.get('club_id'),      request.form.get('event_name'),
            request.form.get('event_date'),   request.form.get('event_time'),
            request.form.get('location'),     request.form.get('description'),
            request.form.get('max_participants'), request.form.get('points'),
            student_id,
        ])
        mysql.connection.commit()
        cur.close()
        flash('Event created and sent to faculty for approval!', 'success')
        return redirect(url_for('coordinator_panel'))

    cur.close()
    return render_template('coordinator/create_event.html', coord_clubs=coord_clubs)


@app.route('/coordinator/approve_member/<int:membership_id>', methods=['POST'])
@login_required
@coordinator_required
def approve_member(membership_id):
    cur    = mysql.connection.cursor()
    action = request.form.get('action')
    status = 'approved' if action == 'approve' else 'rejected'

    cur.execute("SELECT club_id FROM membership WHERE membership_id = %s", [membership_id])
    row = cur.fetchone()
    if row and row['club_id'] in session.get('coord_club_ids', []):
        cur.execute("UPDATE membership SET status = %s WHERE membership_id = %s",
                    [status, membership_id])
        mysql.connection.commit()
        flash(f'Membership {status}.', 'success')
    else:
        flash('Unauthorized action.', 'error')

    cur.close()
    return redirect(url_for('coordinator_panel'))


@app.route('/coordinator/mark_attendance/<int:event_id>', methods=['GET', 'POST'])
@login_required
@coordinator_required
def mark_attendance(event_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM events WHERE event_id = %s", [event_id])
    event = cur.fetchone()

    if not event or event['club_id'] not in session.get('coord_club_ids', []):
        cur.close()
        flash('Unauthorized action.', 'error')
        return redirect(url_for('coordinator_panel'))

    if request.method == 'POST':
        present_ids = request.form.getlist('present_students')
        event_pts   = event['points'] or 0

        cur.execute("SELECT student_id FROM event_attendance WHERE event_id = %s", [event_id])
        all_students = [r['student_id'] for r in cur.fetchall()]

        for sid in all_students:
            att_status = 'present' if sid in present_ids else 'absent'
            cur.execute("""
                UPDATE event_attendance SET attendance_status = %s
                WHERE event_id = %s AND student_id = %s
            """, [att_status, event_id, sid])

            if att_status == 'present' and event_pts > 0:
                cur.execute("""
                    SELECT point_id FROM activity_points
                    WHERE student_id = %s AND event_id = %s
                """, [sid, event_id])
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO activity_points
                            (student_id, event_id, points, description)
                        VALUES (%s, %s, %s, 'Event attendance')
                    """, [sid, event_id, event_pts])
                    cur.execute("""
                        UPDATE students SET total_points = total_points + %s
                        WHERE reg_no = %s
                    """, [event_pts, sid])

        cur.execute("UPDATE events SET status = 'completed' WHERE event_id = %s", [event_id])
        mysql.connection.commit()
        cur.close()
        flash('Attendance marked and points awarded!', 'success')
        return redirect(url_for('coordinator_panel'))

    cur.execute("""
        SELECT ea.*, s.name, s.reg_no FROM event_attendance ea
        JOIN students s ON ea.student_id = s.reg_no
        WHERE ea.event_id = %s ORDER BY s.name
    """, [event_id])
    registrations = cur.fetchall()
    cur.close()
    return render_template('coordinator/mark_attendance.html',
        event=event, registrations=registrations)


@app.route('/coordinator/members')
@login_required
@coordinator_required
def coordinator_members():
    cur      = mysql.connection.cursor()
    club_ids = session.get('coord_club_ids', [])
    if not club_ids:
        cur.close()
        return redirect(url_for('coordinator_panel'))

    placeholders = ','.join(['%s'] * len(club_ids))
    cur.execute(f"""
        SELECT m.*, s.name, s.reg_no, s.semester, s.total_points, c.club_name
        FROM membership m
        JOIN students s ON m.student_id = s.reg_no
        JOIN clubs    c ON m.club_id    = c.club_id
        WHERE m.club_id IN ({placeholders}) AND m.status = 'approved'
        ORDER BY c.club_name, m.role DESC, s.name ASC
    """, club_ids)
    members = cur.fetchall()
    cur.close()
    return render_template('coordinator/members.html', members=members)


@app.route('/coordinator/post_announcement', methods=['GET', 'POST'])
@login_required
@coordinator_required
def post_announcement():
    cur        = mysql.connection.cursor()
    student_id = session['user_id']

    cur.execute("""
        SELECT m.club_id, c.club_name FROM membership m
        JOIN clubs c ON m.club_id = c.club_id
        WHERE m.student_id = %s AND m.role = 'coordinator' AND m.status = 'approved'
    """, [student_id])
    coord_clubs = cur.fetchall()

    if request.method == 'POST':
        cur.execute("""
            INSERT INTO announcements (title, message, club_id, created_by)
            VALUES (%s, %s, %s, %s)
        """, [request.form.get('title'), request.form.get('message'),
              request.form.get('club_id'), session['name']])
        mysql.connection.commit()
        cur.close()
        flash('Announcement posted!', 'success')
        return redirect(url_for('coordinator_panel'))

    cur.close()
    return render_template('coordinator/post_announcement.html', coord_clubs=coord_clubs)


# ═══════════════════════════════════════════════════════════
# FACULTY ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/faculty/dashboard')
@login_required
@role_required('faculty')
def faculty_dashboard():
    cur    = mysql.connection.cursor()
    fac_id = session['user_id']

    cur.execute("""
        SELECT c.*, COUNT(m.membership_id) AS member_count
        FROM clubs c
        LEFT JOIN membership m ON c.club_id = m.club_id AND m.status = 'approved'
        WHERE c.faculty_incharge = %s GROUP BY c.club_id
    """, [fac_id])
    my_clubs = cur.fetchall()

    cur.execute("""
        SELECT e.*, c.club_name FROM events e
        JOIN clubs c ON e.club_id = c.club_id
        WHERE c.faculty_incharge = %s AND e.status = 'pending'
        ORDER BY e.event_date ASC
    """, [fac_id])
    pending_events = cur.fetchall()

    cur.execute("""
        SELECT cert.*, s.name AS student_name, s.semester, s.reg_no
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
    action = request.form.get('action')
    status = 'approved' if action == 'approve' else 'rejected'
    cur    = mysql.connection.cursor()
    cur.execute("UPDATE events SET status = %s WHERE event_id = %s", [status, event_id])
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
    cur     = mysql.connection.cursor()

    cur.execute("SELECT * FROM certificates WHERE certificate_id = %s", [cert_id])
    cert = cur.fetchone()
    if not cert:
        cur.close()
        flash('Certificate not found.', 'error')
        return redirect(url_for('faculty_dashboard'))

    if action == 'approve':
        points_map = {
            'internship': 20, 'industrial_visit': 15, 'nptel': 5,
            'competition_win': 5, 'workshop': 5, 'hackathon': 5,
        }
        pts = points_map.get(cert['activity_category'], 5)
        cur.execute("""
            UPDATE certificates
            SET status='approved', verified_by=%s, points_awarded=%s, remarks=%s
            WHERE certificate_id=%s
        """, [fac_id, pts, remarks, cert_id])
        cur.execute("SELECT point_id FROM activity_points WHERE certificate_id = %s", [cert_id])
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO activity_points
                    (student_id, event_id, certificate_id, points, description)
                VALUES (%s, %s, %s, %s, %s)
            """, [cert['student_id'], cert['event_id'], cert_id, pts,
                  cert['activity_category'] + ' (certificate)'])
            cur.execute("""
                UPDATE students SET total_points = total_points + %s WHERE reg_no = %s
            """, [pts, cert['student_id']])
    else:
        cur.execute("""
            UPDATE certificates SET status='rejected', verified_by=%s, remarks=%s
            WHERE certificate_id=%s
        """, [fac_id, remarks, cert_id])

    mysql.connection.commit()
    cur.close()
    flash(f'Certificate {action}d successfully.', 'success')
    return redirect(url_for('faculty_dashboard'))


@app.route('/faculty/certificates')
@login_required
@role_required('faculty')
def faculty_all_certificates():
    """
    View ALL certificates uploaded by students.
    Supports filtering by status, certificate type, and student reg_no search.
    Faculty can approve/reject directly from this page too.
    """
    cur = mysql.connection.cursor()

    # ── Read filter params from query string ─────────────────────────────────
    status_filter   = request.args.get('status', 'all')       # all/pending/approved/rejected
    type_filter     = request.args.get('cert_type', 'all')    # all/event/self_initiative
    search          = request.args.get('search', '').strip()  # reg_no or name search

    # ── Build dynamic WHERE clause ───────────────────────────────────────────
    conditions = []
    params     = []

    if status_filter != 'all':
        conditions.append("cert.status = %s")
        params.append(status_filter)

    if type_filter != 'all':
        conditions.append("cert.certificate_type = %s")
        params.append(type_filter)

    if search:
        conditions.append("(s.reg_no LIKE %s OR s.name LIKE %s)")
        params.extend([f'%{search}%', f'%{search}%'])

    where_clause = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

    cur.execute(f"""
        SELECT
            cert.*,
            s.name          AS student_name,
            s.reg_no,
            s.semester,
            d.dept_name,
            e.event_name,
            fv.faculty_name AS verified_by_name
        FROM certificates cert
        JOIN students   s   ON cert.student_id  = s.reg_no
        LEFT JOIN departments d  ON s.dept_id        = d.dept_id
        LEFT JOIN events      e  ON cert.event_id     = e.event_id
        LEFT JOIN faculty     fv ON cert.verified_by  = fv.faculty_id
        {where_clause}
        ORDER BY cert.upload_date DESC
    """, params)
    certificates = cur.fetchall()

    # ── Summary counts for the filter bar ────────────────────────────────────
    cur.execute("""
        SELECT
            COUNT(*)                                          AS total,
            SUM(status = 'pending')                           AS pending,
            SUM(status = 'approved')                          AS approved,
            SUM(status = 'rejected')                          AS rejected,
            SUM(certificate_type = 'event')                   AS event_certs,
            SUM(certificate_type = 'self_initiative')         AS self_certs
        FROM certificates
    """)
    counts = cur.fetchone()

    cur.close()
    return render_template('faculty/all_certificates.html',
        certificates  = certificates,
        counts        = counts,
        status_filter = status_filter,
        type_filter   = type_filter,
        search        = search,
    )


@app.route('/faculty/certificates/student/<string:reg_no>')
@login_required
@role_required('faculty')
def faculty_student_certificates(reg_no):
    """View all certificates for one specific student."""
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT s.*, d.dept_name FROM students s
        LEFT JOIN departments d ON s.dept_id = d.dept_id
        WHERE s.reg_no = %s
    """, [reg_no])
    student = cur.fetchone()

    if not student:
        cur.close()
        flash('Student not found.', 'error')
        return redirect(url_for('faculty_all_certificates'))

    cur.execute("""
        SELECT
            cert.*,
            e.event_name,
            fv.faculty_name AS verified_by_name
        FROM certificates cert
        LEFT JOIN events   e  ON cert.event_id    = e.event_id
        LEFT JOIN faculty  fv ON cert.verified_by = fv.faculty_id
        WHERE cert.student_id = %s
        ORDER BY cert.upload_date DESC
    """, [reg_no])
    certificates = cur.fetchall()

    # Points summary for this student
    cur.execute("""
        SELECT
            SUM(ap.points)                                       AS total_points,
            SUM(CASE WHEN ap.event_id IS NOT NULL
                      AND ap.certificate_id IS NULL
                     THEN ap.points ELSE 0 END)                  AS event_auto_points,
            SUM(CASE WHEN ap.certificate_id IS NOT NULL
                     THEN ap.points ELSE 0 END)                  AS cert_points,
            SUM(CASE WHEN ap.event_id IS NULL
                      AND ap.certificate_id IS NULL
                     THEN ap.points ELSE 0 END)                  AS other_points
        FROM activity_points ap
        WHERE ap.student_id = %s
    """, [reg_no])
    points_summary = cur.fetchone()

    cur.close()
    return render_template('faculty/student_certificates.html',
        student        = student,
        certificates   = certificates,
        points_summary = points_summary,
    )


@app.route('/faculty/events')
@login_required
@role_required('faculty')
def faculty_view_events():
    cur    = mysql.connection.cursor()
    fac_id = session['user_id']
    cur.execute("""
        SELECT e.*, c.club_name FROM events e
        JOIN clubs c ON e.club_id = c.club_id
        WHERE c.faculty_incharge = %s ORDER BY e.event_date DESC
    """, [fac_id])
    events = cur.fetchall()
    cur.close()
    return render_template('faculty/events.html', events=events)


@app.route('/faculty/club_members')
@login_required
@role_required('faculty')
def faculty_view_club():
    cur    = mysql.connection.cursor()
    fac_id = session['user_id']
    cur.execute("""
        SELECT m.*, s.name, s.reg_no, s.semester, c.club_name
        FROM membership m
        JOIN students s ON m.student_id = s.reg_no
        JOIN clubs    c ON m.club_id    = c.club_id
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
    cur        = mysql.connection.cursor()
    class_code = session.get('class_incharge')   # e.g. 'S4CE'
    if not class_code:
        cur.close()
        flash('You are not assigned as a class in-charge.', 'error')
        return redirect(url_for('faculty_dashboard'))

    semester_part = class_code[:2]   # 'S4CE' → 'S4'
    cur.execute("""
        SELECT s.*, d.dept_name FROM students s
        LEFT JOIN departments d ON s.dept_id = d.dept_id
        WHERE s.semester = %s ORDER BY s.reg_no
    """, [semester_part])
    students = cur.fetchall()
    cur.close()
    return render_template('faculty/view_class.html',
        students=students, class_code=class_code)


# ═══════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════════

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    cur = mysql.connection.cursor()
    stats = {}
    for key, sql in [
        ('total_students',      "SELECT COUNT(*) AS cnt FROM students"),
        ('active_clubs',        "SELECT COUNT(*) AS cnt FROM clubs WHERE status='Active'"),
        ('total_events',        "SELECT COUNT(*) AS cnt FROM events WHERE status='approved'"),
        ('pending_memberships', "SELECT COUNT(*) AS cnt FROM membership WHERE status='pending'"),
        ('eligible_students',   "SELECT COUNT(*) AS cnt FROM students WHERE total_points >= 100"),
        ('pending_certs',       "SELECT COUNT(*) AS cnt FROM certificates WHERE status='pending'"),
    ]:
        cur.execute(sql)
        stats[key] = cur.fetchone()['cnt']

    cur.execute("""
        SELECT c.club_name, COUNT(m.membership_id) AS members
        FROM clubs c
        LEFT JOIN membership m ON c.club_id = m.club_id AND m.status = 'approved'
        WHERE c.status = 'Active'
        GROUP BY c.club_id ORDER BY members DESC LIMIT 5
    """)
    top_clubs = cur.fetchall()
    cur.close()
    return render_template('admin/dashboard.html', **stats, top_clubs=top_clubs)


@app.route('/admin/students', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_students():
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            cur.execute("""
                INSERT INTO students
                    (reg_no,name,email,phone,dept_id,semester,password,total_points)
                VALUES (%s,%s,%s,%s,%s,%s,%s,0)
            """, [request.form['reg_no'], request.form['name'], request.form['email'],
                  request.form['phone'], request.form['dept_id'],
                  request.form['semester'], request.form['password']])
            mysql.connection.commit()
            flash('Student added!', 'success')
        elif action == 'delete':
            cur.execute("DELETE FROM students WHERE reg_no = %s", [request.form['reg_no']])
            mysql.connection.commit()
            flash('Student deleted.', 'success')

    cur.execute("""
        SELECT s.*, d.dept_name FROM students s
        LEFT JOIN departments d ON s.dept_id = d.dept_id ORDER BY s.reg_no
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
    if request.method == 'POST' and request.form.get('action') == 'add':
        cur.execute("""
            INSERT INTO faculty (faculty_name,email,department,class_incharge,password)
            VALUES (%s,%s,%s,%s,%s)
        """, [request.form['faculty_name'], request.form['email'],
              request.form['department'],
              request.form.get('class_incharge') or None,
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
    if request.method == 'POST' and request.form.get('action') == 'add':
        cur.execute("""
            INSERT INTO clubs (club_name,club_type,faculty_incharge,created_date,status)
            VALUES (%s,%s,%s,CURDATE(),'Active')
        """, [request.form['club_name'], request.form['club_type'],
              request.form['faculty_incharge']])
        mysql.connection.commit()
        flash('Club created!', 'success')
    cur.execute("""
        SELECT c.*, f.faculty_name,
            (SELECT COUNT(*) FROM membership
             WHERE club_id = c.club_id AND status = 'approved') AS members
        FROM clubs c JOIN faculty f ON c.faculty_incharge = f.faculty_id
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
    cur.execute("SELECT status FROM clubs WHERE club_id = %s", [club_id])
    new_status = 'Inactive' if cur.fetchone()['status'] == 'Active' else 'Active'
    cur.execute("UPDATE clubs SET status = %s WHERE club_id = %s", [new_status, club_id])
    mysql.connection.commit()
    cur.close()
    flash(f'Club status changed to {new_status}.', 'success')
    return redirect(url_for('admin_clubs'))


@app.route('/admin/departments', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_departments():
    cur = mysql.connection.cursor()
    if request.method == 'POST' and request.form.get('action') == 'add':
        cur.execute("""
            INSERT INTO departments (dept_name,dept_code,hod_name) VALUES (%s,%s,%s)
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
        JOIN clubs   c ON e.club_id          = c.club_id
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
        SELECT m.*, s.name AS student_name, s.reg_no, c.club_name
        FROM membership m
        JOIN students s ON m.student_id = s.reg_no
        JOIN clubs    c ON m.club_id    = c.club_id
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
            CASE WHEN s.total_points >= 100 THEN 'Eligible' ELSE 'Not Eligible' END AS grad_status
        FROM students s JOIN departments d ON s.dept_id = d.dept_id
        ORDER BY s.total_points DESC
    """)
    report = cur.fetchall()
    cur.execute("SELECT COUNT(*) AS cnt FROM students WHERE total_points >= 100"); eligible = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) AS cnt FROM students");                            total    = cur.fetchone()['cnt']
    cur.execute("""
        SELECT d.dept_name, AVG(s.total_points) AS avg_pts
        FROM students s JOIN departments d ON s.dept_id = d.dept_id
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
            INSERT INTO announcements (title, message, created_by) VALUES (%s, %s, 'Admin')
        """, [request.form['title'], request.form['message']])
        mysql.connection.commit()
        flash('System announcement posted!', 'success')
    cur.execute("SELECT * FROM announcements ORDER BY created_date DESC")
    announcements = cur.fetchall()
    cur.close()
    return render_template('admin/announcements.html', announcements=announcements)


# ═══════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)