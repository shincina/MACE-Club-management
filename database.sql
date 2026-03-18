CREATE DATABASE IF NOT EXISTS mace_activity_db;
USE mace_activity_db;
CREATE TABLE IF NOT EXISTS admins (
    admin_id   INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(100) UNIQUE NOT NULL,
    password   VARCHAR(255) NOT NULL
);
CREATE TABLE departments (
    dept_id INT AUTO_INCREMENT PRIMARY KEY,
    dept_name VARCHAR(100) NOT NULL,
    dept_code VARCHAR(10) NOT NULL,
    hod_name VARCHAR(100)
);
CREATE TABLE faculty (
    faculty_id INT AUTO_INCREMENT PRIMARY KEY,
    faculty_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    department VARCHAR(100),
    class_incharge VARCHAR(20),
    password VARCHAR(255) NOT NULL,
    role ENUM('hod','faculty') DEFAULT 'faculty'
);
CREATE TABLE students (
    reg_no VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(15),
    dept_id INT,
    semester VARCHAR(5),
    password VARCHAR(255) NOT NULL,
    total_points INT DEFAULT 0,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
);
CREATE TABLE clubs (
    club_id INT AUTO_INCREMENT PRIMARY KEY,
    club_name VARCHAR(100) NOT NULL,
    club_type VARCHAR(50),
    faculty_incharge INT,
    created_date DATE,
    status ENUM('Active','Inactive') DEFAULT 'Active',
    FOREIGN KEY (faculty_incharge) REFERENCES faculty(faculty_id)
);
CREATE TABLE membership (
    membership_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20),
    club_id INT,
    role ENUM('member','coordinator') DEFAULT 'member',
    join_date DATE,
    status ENUM('pending','approved','rejected') DEFAULT 'pending',
    FOREIGN KEY (student_id) REFERENCES students(reg_no),
    FOREIGN KEY (club_id) REFERENCES clubs(club_id),
    UNIQUE KEY unique_membership (student_id, club_id)
);
CREATE TABLE events (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    club_id INT,
    event_name VARCHAR(150) NOT NULL,
    event_date DATE,
    event_time TIME,
    location VARCHAR(200),
    description TEXT,
    max_participants INT,
    points INT DEFAULT 0,
    status ENUM('pending','approved','rejected','completed') DEFAULT 'pending',
    created_by VARCHAR(20),
    FOREIGN KEY (club_id) REFERENCES clubs(club_id)
);
CREATE TABLE event_attendance (
    attendance_id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT,
    student_id VARCHAR(20),
    attendance_status ENUM('present','absent') DEFAULT 'absent',
    payment_status ENUM('paid','not_paid') DEFAULT 'not_paid',
    FOREIGN KEY (event_id) REFERENCES events(event_id),
    FOREIGN KEY (student_id) REFERENCES students(reg_no)
);
CREATE TABLE certificates (
    certificate_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20),
    event_id INT NULL,
    certificate_type ENUM('event','self_initiative') NOT NULL,
    file_path VARCHAR(500),
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending','approved','rejected','auto_approved') DEFAULT 'pending',
    verified_by INT NULL,
    points_awarded INT DEFAULT 0,
    remarks TEXT,
    activity_category VARCHAR(50),
    FOREIGN KEY (student_id) REFERENCES students(reg_no),
    FOREIGN KEY (event_id) REFERENCES events(event_id),
    FOREIGN KEY (verified_by) REFERENCES faculty(faculty_id)
);
CREATE TABLE activity_points (
    point_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20),
    event_id INT NULL,
    certificate_id INT NULL,
    points INT NOT NULL,
    date_awarded DATETIME DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR(200),
    FOREIGN KEY (student_id) REFERENCES students(reg_no),
    FOREIGN KEY (event_id) REFERENCES events(event_id),
    FOREIGN KEY (certificate_id) REFERENCES certificates(certificate_id)
);
CREATE TABLE announcements (
    announcement_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    message TEXT,
    club_id INT NULL,
    event_id INT NULL,
    created_by VARCHAR(100),
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (club_id) REFERENCES clubs(club_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id)
);
INSERT INTO admins (name, email, password) VALUES
('Administrator', 'admin@mace.ac.in', 'admin123');

INSERT INTO departments (dept_name, dept_code, hod_name) VALUES
('Computer Science and Engineering', 'CS', 'Prof. Joby George'),
('CSE with Artificial Intelligence', 'AIM', 'Prof. Joby George'),
('CSE with Data Science', 'CD', 'Prof. Joby George'),
('Electronics and Communication Engineering', 'EC', 'Dr. Aji Joy'),
('Civil Engineering', 'CE', 'Dr. Elson John'),
('Electrical and Electronics Engineering', 'EE', 'Dr. Siny Paul'),
('Mechanical Engineering', 'ME', 'Dr. Soni Kuriakose'),
('Computer Applications', 'MCA', 'Prof. Biju Skaria'),
('Mathematics', 'Math', 'Prof. Rani Thomas'),
('Science and Humanities', 'SH', 'Dr. Arunkumar S');


INSERT INTO faculty (faculty_name, email, department, class_incharge, password) VALUES
('Prof. Joby George','joby.george@mace.ac.in','CS', NULL, 'faculty123'),
('Dr. Aji Joy','aji.joy@mace.ac.in','EC', NULL, 'faculty123'),
('Dr. Elson John','elson.john@mace.ac.in','CE', NULL, 'faculty123'),
('Dr. Siny Paul','siny.paul@mace.ac.in','EE', NULL, 'faculty123'),
('Dr. Soni Kuriakose','soni.kuriakose@mace.ac.in','ME', NULL, 'faculty123'),
('Prof. Nithin Eldho Subash','nithin.subash@mace.ac.in','CE', 'S4CE', 'faculty123'),
('Mr. Binu Varghese','binu.varghese@mace.ac.in','ME', NULL, 'faculty123'),
('Dr. Reenu George','reenu.george@mace.ac.in','CS', 'S6CS', 'faculty123'),
('Prof. Eldo P Elias','eldo.elias@mace.ac.in','CS', 'S2CS', 'faculty123'),
('Dr. Kurian John','kurian.john@mace.ac.in','ME', 'S4ME', 'faculty123'),
('Dr. Deepak Eldho Babu','deepak.babu@mace.ac.in','EC', 'S4EC', 'faculty123'),
('Dr. Joby Joseph','joby.joseph@mace.ac.in','CS', 'S6AIM', 'faculty123'),
('Dr. Vinod Yeldho Baby','vinod.baby@mace.ac.in','EC', NULL, 'faculty123');


-- Note: faculty_incharge references the faculty_id auto-assigned above.
-- faculty_id 2 = Dr. Aji Joy (NSS), 4 = Dr. Siny Paul (IEEE), etc.
INSERT INTO clubs (club_name, club_type, faculty_incharge, created_date, status) VALUES
('NSS','Social Service',2,'2024-01-15','Active'),
('IEEE MACE','Technical',4,'2024-01-15','Active'),
('Literary and Debating Club','Cultural',3,'2024-01-15','Active'),
('Dance Club','Cultural',6,'2024-01-15','Active'),
('Sports and Games Association','Sports',7,'2024-01-15','Active'),
('SAE MACE','Technical',5,'2024-01-15','Active'),
('ISTE MACE','Technical',1,'2024-01-15','Active'),
('MACE Film Society','Film',8,'2024-01-15','Active'),
('ASME MACE','Technical',5,'2024-01-15','Active'),
('MACE NetX Club','Technical',9,'2024-01-15','Active'),
('Divaat Club','Arts',10,'2024-01-15','Active'),
('MACE MUN','Academic',11,'2024-01-15','Active'),
('AISA MACE','Technical',9,'2024-01-15','Active'),
('Quiz Club','Academic',12,'2024-01-15','Active'),
('Music Club','Cultural',13,'2024-01-15','Active'),
('ASCE MACE','Technical',3,'2024-01-15','Active'),
('ENCIDE MACE','Technical',9,'2024-01-15','Active'),
('ENCON Club','Environmental',4,'2024-01-15','Active'),
('Developers Students Club (DSC)','Technical',9,'2024-01-15','Active');

INSERT INTO students (reg_no, name, email, phone, dept_id, semester, password, total_points) VALUES
('B24CS001','Arjun Krishna','b24cs001@mace.ac.in','9876543210',1,'S4','student123',45),
('B24CS002','Aditya Menon','b24cs002@mace.ac.in','9876543211',1,'S4','student123',30),
('B24AIM001','Priya Sharma','b24aim001@mace.ac.in','9876543212',2,'S4','student123',60);

-- ==========================================
-- 1. MEMBERSHIP TABLE
-- Assign coordinators and members to clubs
-- ==========================================

INSERT INTO membership (student_id, club_id, role, join_date, status) VALUES
-- Coordinators
('B24CS001', 1, 'coordinator', '2024-02-01', 'approved'),  -- Arjun Krishna - NSS
('B24AIM001', 2, 'coordinator', '2024-02-01', 'approved'), -- Priya Sharma - IEEE MACE
('B24CS002', 3, 'coordinator', '2024-02-01', 'approved'),  -- Aditya Menon - Literary Club

-- Regular Members
('B24CS001', 2, 'member', '2024-02-15', 'approved'),  -- Arjun also in IEEE
('B24CS002', 1, 'member', '2024-02-20', 'approved'),  -- Aditya also in NSS
('B24AIM001', 7, 'member', '2024-03-01', 'approved'); -- Priya also in ISTE

-- ==========================================
-- 2. EVENTS TABLE
-- Sample events from different clubs
-- ==========================================

INSERT INTO events (club_id, event_name, event_date, event_time, location, description, max_participants, points, status, created_by) VALUES
-- NSS Events
(1, 'Blood Donation Camp', '2026-04-15', '09:00:00', 'Main Auditorium', 'Annual blood donation drive', 100, 5, 'approved', 'B24CS001'),
(1, 'Village Cleanup Drive', '2026-04-20', '07:00:00', 'Nearby Village', 'Community service activity', 50, 5, 'approved', 'B24CS001'),

-- IEEE Events
(2, 'Coding Workshop', '2026-04-10', '14:00:00', 'Computer Lab 1', 'Learn Python basics', 40, 5, 'approved', 'B24AIM001'),
(2, 'Hackathon 2026', '2026-05-01', '09:00:00', 'Tech Park', '24-hour coding competition', 80, 5, 'pending', 'B24AIM001'),

-- Literary Club Events
(3, 'Debate Competition', '2026-04-25', '15:00:00', 'Seminar Hall', 'Inter-department debate', 60, 5, 'approved', 'B24CS002'),

-- Dance Club Event
(4, 'Dance Fest 2026', '2026-05-10', '18:00:00', 'College Grounds', 'Annual dance competition', 100, 5, 'pending', NULL),

-- Quiz Club Event
(14, 'General Quiz Competition', '2026-04-18', '16:00:00', 'Auditorium', 'Open quiz for all students', 80, 5, 'approved', NULL);

-- ==========================================
-- 3. EVENT_ATTENDANCE TABLE
-- Students who registered and attended events
-- ==========================================

INSERT INTO event_attendance (event_id, student_id, attendance_status, payment_status) VALUES
-- Event 1: Blood Donation Camp - AUTO AWARD (just attend)
(1, 'B24CS001', 'present', 'paid'),
(1, 'B24CS002', 'present', 'paid'),
(1, 'B24AIM001', 'present', 'paid'),
 
-- Event 2: Village Cleanup - AUTO AWARD (just attend)
(2, 'B24CS001', 'present', 'paid'),
(2, 'B24CS002', 'absent', 'paid'),
 
-- Event 3: Coding Workshop - AUTO AWARD (just attend)
(3, 'B24AIM001', 'present', 'paid'),
(3, 'B24CS001', 'present', 'paid');
 
-- Points awarded automatically when attendance marked
-- event_id filled, certificate_id = NULL
INSERT INTO activity_points (student_id, event_id, certificate_id, points, description) VALUES
('B24CS001', 1, NULL, 5, 'Blood Donation Camp - Auto'),
('B24CS002', 1, NULL, 5, 'Blood Donation Camp - Auto'),
('B24AIM001', 1, NULL, 5, 'Blood Donation Camp - Auto'),
 
('B24CS001', 2, NULL, 5, 'Village Cleanup - Auto'),
 
('B24AIM001', 3, NULL, 5, 'Coding Workshop - Auto'),
('B24CS001', 3, NULL, 5, 'Coding Workshop - Auto');
 
-- ==========================================
-- PART 2: CLUB EVENTS - CERTIFICATE REQUIRED
-- Student attends → Uploads certificate → Faculty verifies → Points awarded
-- Certificate uploaded for CLUB events (event_id NOT NULL)
-- ==========================================
 
-- Event 5: Debate Competition - CERTIFICATE REQUIRED (e.g., for winners)
INSERT INTO event_attendance (event_id, student_id, attendance_status, payment_status) VALUES
(5, 'B24CS002', 'present', 'paid'),  -- Winner
(5, 'B24AIM001', 'present', 'paid'); -- Participant (didn't win)
 
-- B24CS002 won the debate, uploads certificate
INSERT INTO certificates (student_id, event_id, certificate_type, file_path, status, verified_by, points_awarded, activity_category) VALUES
('B24CS002', 5, 'event', 'uploads/b24cs002_debate_winner.pdf', 'approved', 1, 5, 'competition_win');
 
-- Points awarded after certificate verification
-- event_id filled, certificate_id filled (both filled for club event with certificate)
INSERT INTO activity_points (student_id, event_id, certificate_id, points, description) VALUES
('B24CS002', 5, 1, 5, 'Debate Competition Winner');
 
-- B24AIM001 participated but didn't win = 0 points (no certificate needed)
 
-- ==========================================
-- PART 3: SELF-INITIATIVE - ALWAYS CERTIFICATE
-- NOT related to any club event
-- event_id = NULL, certificate_type = 'self_initiative'
-- ==========================================
 
INSERT INTO certificates (student_id, event_id, certificate_type, file_path, status, verified_by, points_awarded, activity_category) VALUES
-- Internship certificates (20 points)
('B24CS001', NULL, 'self_initiative', 'uploads/b24cs001_internship.pdf', 'approved', 1, 20, 'internship'),
('B24AIM001', NULL, 'self_initiative', 'uploads/b24aim001_internship.pdf', 'approved', 2, 20, 'internship'),
 
-- Industrial Visit (15 points)
('B24CS002', NULL, 'self_initiative', 'uploads/b24cs002_iv.pdf', 'approved', 1, 15, 'industrial_visit'),
 
-- NPTEL (5 points) - PENDING
('B24AIM001', NULL, 'self_initiative', 'uploads/b24aim001_nptel.pdf', 'pending', NULL, 0, 'nptel');
 
-- Points awarded for verified self-initiative certificates
-- event_id = NULL, certificate_id filled
INSERT INTO activity_points (student_id, event_id, certificate_id, points, description) VALUES
('B24CS001', NULL, 2, 20, 'Internship - Self Initiative'),
('B24AIM001', NULL, 3, 20, 'Internship - Self Initiative'),
('B24CS002', NULL, 4, 15, 'Industrial Visit - Self Initiative');
 
-- ==========================================
-- PART 4: OTHER ACTIVITIES
-- To reach stored totals: 45, 30, 60
-- ==========================================
 
INSERT INTO activity_points (student_id, event_id, certificate_id, points, description) VALUES
-- B24CS001: has 10 (club auto) + 20 (internship) = 30, needs 15 more
('B24CS001', NULL, NULL, 15, 'Previous semester activities'),
 
-- B24CS002: has 5 (club auto) + 5 (club cert) + 15 (IV) = 25, needs 5 more
('B24CS002', NULL, NULL, 5, 'Previous semester activities'),
 
-- B24AIM001: has 10 (club auto) + 20 (internship) = 30, needs 30 more
('B24AIM001', NULL, NULL, 30, 'Previous semester activities');
 
-- ==========================================
-- VERIFICATION QUERIES
-- ==========================================
 
SELECT '=== TOTAL POINTS VERIFICATION ===' as '';
 
SELECT 
    s.reg_no, 
    s.name, 
    s.total_points as stored,
    COALESCE(SUM(ap.points), 0) as calculated,
    CASE 
        WHEN s.total_points = COALESCE(SUM(ap.points), 0) THEN '✓ MATCH'
        ELSE '✗ MISMATCH'
    END as status
FROM students s
LEFT JOIN activity_points ap ON s.reg_no = ap.student_id
GROUP BY s.reg_no, s.name, s.total_points;
 
SELECT '=== POINTS BREAKDOWN BY TYPE ===' as '';
 
SELECT 
    student_id,
    CASE 
        WHEN event_id IS NOT NULL AND certificate_id IS NULL THEN 'Club Event (Auto)'
        WHEN event_id IS NOT NULL AND certificate_id IS NOT NULL THEN 'Club Event (Certificate)'
        WHEN event_id IS NULL AND certificate_id IS NOT NULL THEN 'Self-Initiative'
        ELSE 'Other'
    END as point_source,
    COUNT(*) as entries,
    SUM(points) as total_points
FROM activity_points
GROUP BY student_id, point_source
ORDER BY student_id, point_source;
 
SELECT '=== CERTIFICATES OVERVIEW ===' as '';
 
SELECT 
    s.name,
    CASE 
        WHEN c.event_id IS NOT NULL THEN 'Club Event Certificate'
        ELSE 'Self-Initiative Certificate'
    END as cert_type,
    c.activity_category,
    c.status,
    c.points_awarded
FROM certificates c
JOIN students s ON c.student_id = s.reg_no
ORDER BY s.reg_no, cert_type;
 
-- ==========================================
-- SUMMARY OF CERTIFICATE TYPES:
-- ==========================================
/*
CERTIFICATES TABLE STRUCTURE:
 
1. CLUB EVENT CERTIFICATES:
   - event_id: NOT NULL (references events table)
   - certificate_type: 'event'
   - Examples: Competition winner certificate, Hackathon completion certificate
   - Student uploads AFTER attending the club event
 
2. SELF-INITIATIVE CERTIFICATES:
   - event_id: NULL (not related to any club event)
   - certificate_type: 'self_initiative'
   - Examples: Internship (20pts), IV (15pts), NPTEL (5pts)
   - Student uploads independently
 
ACTIVITY_POINTS TABLE TRACKING:
 
1. Club Event - Auto Award:
   - event_id: filled
   - certificate_id: NULL
   - Example: Workshop attendance (5 points)
 
2. Club Event - Certificate Required:
   - event_id: filled
   - certificate_id: filled
   - Example: Competition winner (5 points after certificate verified)
 
3. Self-Initiative:
   - event_id: NULL
   - certificate_id: filled
   - Example: Internship verified (20 points)
 
4. Other:
   - event_id: NULL
   - certificate_id: NULL
   - Example: Previous semester carryover points
*/

-- ==========================================
-- 6. ANNOUNCEMENTS TABLE
-- System and club announcements
-- ==========================================

INSERT INTO announcements (title, message, club_id, event_id, created_by) VALUES
-- General announcements
('Welcome to Activity Points System', 'Track your participation and earn points for graduation eligibility. Complete 100 points before final year!', NULL, NULL, 'System Admin'),

('Semester Activity Registration Open', 'All students can now register for club activities and events. Join at least one club to start earning points.', NULL, NULL, 'System Admin'),

-- Club-specific announcements
('NSS Blood Donation Camp', 'Registrations are now open! Please register before April 10th.', 1, 1, 'B24CS001'),

('IEEE Hackathon 2026', 'Get ready for the biggest coding event of the year! Form teams of 3-4 members.', 2, 4, 'B24AIM001'),

('Literary Club Meeting', 'All members are requested to attend the monthly meeting on April 5th at 4 PM.', 3, NULL, 'B24CS002');

-- ==========================================
-- VERIFICATION QUERIES
-- Run these to check if data inserted correctly
-- ==========================================

-- Check student total points match activity_points sum
SELECT 
    s.reg_no, 
    s.name, 
    s.total_points as stored_points,
    COALESCE(SUM(ap.points), 0) as calculated_points
FROM students s
LEFT JOIN activity_points ap ON s.reg_no = ap.student_id
GROUP BY s.reg_no, s.name, s.total_points;

-- Should show:
-- B24CS001: 45 points (5+5+5+20 + 10 more from earlier)
-- B24CS002: 30 points (5+5+15 + 5 more from earlier)
-- B24AIM001: 60 points (5+5+5+20 + 25 more from earlier)

-- Check membership counts per club
SELECT c.club_name, COUNT(m.membership_id) as members
FROM clubs c
LEFT JOIN membership m ON c.club_id = m.club_id AND m.status = 'approved'
GROUP BY c.club_id, c.club_name
ORDER BY members DESC;

-- Check events per club
SELECT c.club_name, COUNT(e.event_id) as events
FROM clubs c
LEFT JOIN events e ON c.club_id = e.club_id
GROUP BY c.club_id, c.club_name
HAVING events > 0
ORDER BY events DESC;

-- Check pending certificates
SELECT 
    c.certificate_id,
    s.name as student_name,
    c.activity_category,
    c.status,
    c.upload_date
FROM certificates c
JOIN students s ON c.student_id = s.reg_no
WHERE c.status = 'pending';
