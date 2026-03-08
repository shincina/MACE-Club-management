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
