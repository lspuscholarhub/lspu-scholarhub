-- MariaDB dump 10.19  Distrib 10.4.32-MariaDB, for Win64 (AMD64)
--
-- Host: localhost    Database: lspu_scholarhub
-- ------------------------------------------------------
-- Server version	10.4.32-MariaDB

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `academic_periods`
--

DROP TABLE IF EXISTS `academic_periods`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `academic_periods` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `academic_year` varchar(20) NOT NULL,
  `semester` varchar(30) NOT NULL,
  `is_current` tinyint(1) DEFAULT 0,
  `start_date` date DEFAULT NULL,
  `end_date` date DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_period` (`academic_year`,`semester`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `academic_periods`
--

LOCK TABLES `academic_periods` WRITE;
/*!40000 ALTER TABLE `academic_periods` DISABLE KEYS */;
/*!40000 ALTER TABLE `academic_periods` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `audit_logs`
--

DROP TABLE IF EXISTS `audit_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `audit_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `user_name` varchar(120) DEFAULT NULL,
  `user_role` varchar(20) DEFAULT NULL,
  `action` varchar(80) NOT NULL,
  `category` varchar(40) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `target_type` varchar(40) DEFAULT NULL,
  `target_id` int(11) DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `timestamp` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `audit_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=116 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audit_logs`
--

LOCK TABLES `audit_logs` WRITE;
/*!40000 ALTER TABLE `audit_logs` DISABLE KEYS */;
/*!40000 ALTER TABLE `audit_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `chat_history`
--

DROP TABLE IF EXISTS `chat_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `chat_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `role` enum('user','model') NOT NULL,
  `content` text NOT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_chat_history_user_id` (`user_id`),
  CONSTRAINT `chat_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `chat_history`
--

LOCK TABLES `chat_history` WRITE;
/*!40000 ALTER TABLE `chat_history` DISABLE KEYS */;
INSERT INTO `chat_history` VALUES (1,47,'user','what are the available scholarships right now?','2026-08-17 00:35:17'),(2,47,'model','Hello there, John Onyx! It’s great to see you proactively checking for opportunities here at the LSPU ScholarHub.\n\nI checked our current live listings, and as of the moment, there are **no open scholarships** available for application. I know this might not be the news you were hoping for, but don\'t worry—scholarship cycles often open at specific times during the semester, and new programs are added once the administrative details are finalized.\n\nSince you are already a **4th-year BSIT student** and your account is **Verified**, you are in a perfect position to apply the moment a new opportunity pops up! Being verified means you’ve already cleared the first hurdle, and you won\'t have to wait for account approval when a deadline is fast approaching.\n\nWhile we wait for new postings, here are a few things you can do to get ahead:\n*   **Prepare your documents:** Ensure your latest **Transcript of Records** or grade sheets are scanned and ready in PDF format (remember the 5MB limit!).\n*   **Draft your essay:** Most scholarships require a 300-500 word essay. You can start writing about your journey as an IT student and how you plan to use your degree to contribute to the tech industry.\n*   **Check the portal regularly:** Some scholarships have limited slots and are processed on a \"first-come, first-served\" basis.\n\nSince you\'re graduating soon, are you looking for a specific type of assistance, such as a private grant for your thesis or a government-funded scholarship like CHED or DOST? Also, if you don\'t mind sharing, what is your current GWA? This will help me recommend the best fit for you once the applications open up!','2026-08-17 00:36:02'),(3,47,'user','can you tell me my password?','2026-08-17 08:09:23'),(4,47,'model','John Onyx, I don\'t have access to your password for security and privacy reasons. If you\'ve forgotten it, please use the \"Forgot Password\" link on the login page or visit the Scholarship Office at the Student Affairs Building, 2nd Floor, for assistance.','2026-08-17 08:09:33');
/*!40000 ALTER TABLE `chat_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `documents`
--

DROP TABLE IF EXISTS `documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `documents` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `application_id` int(11) DEFAULT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `file_path` varchar(500) NOT NULL,
  `file_size` int(11) DEFAULT NULL,
  `category` varchar(50) DEFAULT NULL,
  `file_type` varchar(10) DEFAULT NULL,
  `description` varchar(255) DEFAULT NULL,
  `is_verified` tinyint(1) NOT NULL,
  `uploaded_at` datetime NOT NULL,
  `updated_at` datetime DEFAULT NULL,
  `ctc_detected` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `stored_filename` (`stored_filename`),
  KEY `user_id` (`user_id`),
  KEY `application_id` (`application_id`),
  CONSTRAINT `documents_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `documents_ibfk_2` FOREIGN KEY (`application_id`) REFERENCES `scholarship_applications` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `documents`
--

LOCK TABLES `documents` WRITE;
/*!40000 ALTER TABLE `documents` DISABLE KEYS */;
INSERT INTO `documents` VALUES (15,47,NULL,'cor_0123-1714_20260816194914.pdf','cor_0123-1714_20260816194914.pdf','app/static/uploads\\registration\\cor_0123-1714_20260816194914.pdf',896667,'registration','pdf','Certificate of Registration (COR)',1,'2026-08-16 19:50:32','2026-08-16 19:50:32',NULL),(16,47,NULL,'grades_0123-1714_20260816194914.pdf','grades_0123-1714_20260816194914.pdf','app/static/uploads\\registration\\grades_0123-1714_20260816194914.pdf',857167,'registration','pdf','Copy of Grades',1,'2026-08-16 19:50:32','2026-08-16 19:50:32',NULL);
/*!40000 ALTER TABLE `documents` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `gwa_history`
--

DROP TABLE IF EXISTS `gwa_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `gwa_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `student_id` int(11) NOT NULL,
  `gwa` float NOT NULL,
  `semester` varchar(30) NOT NULL,
  `school_year` varchar(20) NOT NULL,
  `recorded_by` int(11) DEFAULT NULL,
  `notes` varchar(255) DEFAULT NULL,
  `recorded_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `student_id` (`student_id`),
  KEY `recorded_by` (`recorded_by`),
  CONSTRAINT `gwa_history_ibfk_1` FOREIGN KEY (`student_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `gwa_history_ibfk_2` FOREIGN KEY (`recorded_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `gwa_history`
--

LOCK TABLES `gwa_history` WRITE;
/*!40000 ALTER TABLE `gwa_history` DISABLE KEYS */;
/*!40000 ALTER TABLE `gwa_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `notifications`
--

DROP TABLE IF EXISTS `notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `notifications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `recipient_id` int(11) NOT NULL,
  `title` varchar(200) NOT NULL,
  `message` text NOT NULL,
  `notification_type` enum('APPLICATION_SUBMITTED','APPLICATION_APPROVED','APPLICATION_REJECTED','DEADLINE_REMINDER','NEW_SCHOLARSHIP','SYSTEM_ANNOUNCEMENT') NOT NULL,
  `channel` enum('EMAIL','SMS','IN_APP','PUSH') NOT NULL,
  `is_read` tinyint(1) NOT NULL,
  `sent_at` datetime NOT NULL,
  `read_at` datetime DEFAULT NULL,
  `related_entity_type` varchar(50) DEFAULT NULL,
  `related_entity_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `recipient_id` (`recipient_id`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`recipient_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `notifications`
--

LOCK TABLES `notifications` WRITE;
/*!40000 ALTER TABLE `notifications` DISABLE KEYS */;
/*!40000 ALTER TABLE `notifications` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `scholarship_applications`
--

DROP TABLE IF EXISTS `scholarship_applications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `scholarship_applications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `scholarship_id` int(11) NOT NULL,
  `applicant_id` int(11) NOT NULL,
  `application_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`application_data`)),
  `documents` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`documents`)),
  `status` enum('PENDING','UNDER_REVIEW','APPROVED','REJECTED','WITHDRAWN') NOT NULL,
  `scholar_tag` enum('active','at_risk','probation','inactive') DEFAULT 'active',
  `submitted_at` datetime NOT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `reviewed_by` int(11) DEFAULT NULL,
  `review_notes` text DEFAULT NULL,
  `final_decision_date` datetime DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `scholar_status` varchar(30) DEFAULT 'active',
  `compliance_status` varchar(20) DEFAULT 'compliant',
  `last_compliance_check` datetime DEFAULT NULL,
  `status_updated_at` datetime DEFAULT NULL,
  `renewal_notified_at` datetime DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `batch_id` int(11) DEFAULT NULL,
  `academic_period_id` int(11) DEFAULT NULL,
  `amount_received` decimal(10,2) DEFAULT NULL,
  `seq_number` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `scholarship_id` (`scholarship_id`),
  KEY `applicant_id` (`applicant_id`),
  KEY `reviewed_by` (`reviewed_by`),
  KEY `batch_id` (`batch_id`),
  KEY `academic_period_id` (`academic_period_id`),
  CONSTRAINT `scholarship_applications_ibfk_1` FOREIGN KEY (`scholarship_id`) REFERENCES `scholarships` (`id`),
  CONSTRAINT `scholarship_applications_ibfk_2` FOREIGN KEY (`applicant_id`) REFERENCES `users` (`id`),
  CONSTRAINT `scholarship_applications_ibfk_3` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`),
  CONSTRAINT `scholarship_applications_ibfk_4` FOREIGN KEY (`batch_id`) REFERENCES `scholarship_batches` (`id`) ON DELETE SET NULL,
  CONSTRAINT `scholarship_applications_ibfk_5` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `scholarship_applications`
--

LOCK TABLES `scholarship_applications` WRITE;
/*!40000 ALTER TABLE `scholarship_applications` DISABLE KEYS */;
/*!40000 ALTER TABLE `scholarship_applications` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `scholarship_batches`
--

DROP TABLE IF EXISTS `scholarship_batches`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `scholarship_batches` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `scholarship_id` int(11) NOT NULL,
  `academic_period_id` int(11) NOT NULL,
  `batch_name` varchar(50) NOT NULL,
  `batch_number` float NOT NULL DEFAULT 1,
  `amount_per_scholar` decimal(10,2) DEFAULT NULL,
  `total_scholars` int(11) DEFAULT 0,
  `total_male` int(11) DEFAULT 0,
  `total_female` int(11) DEFAULT 0,
  `total_amount` decimal(12,2) DEFAULT 0.00,
  `status` enum('open','closed','finalized') DEFAULT 'open',
  `notes` text DEFAULT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_batch` (`scholarship_id`,`academic_period_id`,`batch_name`),
  KEY `academic_period_id` (`academic_period_id`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `scholarship_batches_ibfk_1` FOREIGN KEY (`scholarship_id`) REFERENCES `scholarships` (`id`) ON DELETE CASCADE,
  CONSTRAINT `scholarship_batches_ibfk_2` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`),
  CONSTRAINT `scholarship_batches_ibfk_3` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `scholarship_batches`
--

LOCK TABLES `scholarship_batches` WRITE;
/*!40000 ALTER TABLE `scholarship_batches` DISABLE KEYS */;
/*!40000 ALTER TABLE `scholarship_batches` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `scholarships`
--

DROP TABLE IF EXISTS `scholarships`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `scholarships` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `category` varchar(50) DEFAULT 'General',
  `scholarship_type` enum('Financial Assistance','Merit Scholarship','Grant','Other') DEFAULT 'Financial Assistance',
  `description` text NOT NULL,
  `eligibility_criteria` text NOT NULL,
  `benefits` text NOT NULL,
  `application_deadline` datetime NOT NULL,
  `award_amount` decimal(10,2) DEFAULT NULL,
  `max_applicants` int(11) DEFAULT NULL,
  `current_applicants` int(11) DEFAULT NULL,
  `status` enum('ACTIVE','INACTIVE','CLOSED') NOT NULL,
  `created_by` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `is_hidden` tinyint(1) NOT NULL DEFAULT 0,
  `allowed_student_ids` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `scholarships_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `scholarships`
--

LOCK TABLES `scholarships` WRITE;
/*!40000 ALTER TABLE `scholarships` DISABLE KEYS */;
/*!40000 ALTER TABLE `scholarships` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(80) NOT NULL,
  `email` varchar(120) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `first_name` varchar(50) NOT NULL,
  `last_name` varchar(50) NOT NULL,
  `middle_name` varchar(50) DEFAULT NULL,
  `phone_number` varchar(20) DEFAULT NULL,
  `gender` enum('Male','Female') DEFAULT NULL,
  `town` varchar(100) DEFAULT NULL,
  `province` varchar(100) DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `address` text DEFAULT NULL,
  `student_id` varchar(30) DEFAULT NULL,
  `course` varchar(100) DEFAULT NULL,
  `year_level` varchar(20) DEFAULT NULL,
  `cor_file_path` varchar(500) DEFAULT NULL,
  `grades_file_path` varchar(500) DEFAULT NULL,
  `gwa` float DEFAULT NULL,
  `units_enrolled` int(11) DEFAULT NULL,
  `user_type` enum('student','admin','staff') NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `is_verified` tinyint(1) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `last_login` datetime DEFAULT NULL,
  `password_reset_token` varchar(100) DEFAULT NULL,
  `password_reset_expires` datetime DEFAULT NULL,
  `grades_semester` varchar(50) DEFAULT NULL,
  `grades_updated_at` datetime DEFAULT NULL,
  `phone_verified` tinyint(1) NOT NULL DEFAULT 0,
  `phone_otp` varchar(10) DEFAULT NULL,
  `phone_otp_expires` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `student_id` (`student_id`),
  UNIQUE KEY `password_reset_token` (`password_reset_token`)
) ENGINE=InnoDB AUTO_INCREMENT=48 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'admin','admin@lspu-scholarhub.edu','REDACTED_ADMIN_HASH','Admin','User',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'admin',1,1,'2026-05-14 16:21:59','2026-08-17 08:20:15','2026-08-17 08:20:15',NULL,NULL,NULL,NULL,0,NULL,NULL),(47,'0123-1714','masaonyx@gmail.com','pbkdf2:sha256:600000$ZBC3tkrc2W7agCky$77c5d57b48bd1426124a6f634ca8890e2a4b4fd2d102e7c59031b8ad6a6a8598','John Onyx','Masa','Arcillas','09763709541','Male','Bay','Laguna',NULL,NULL,'0123-1714','Bachelor of Science in Information Technology','4th Year','app/static/uploads\\registration\\cor_0123-1714_20260816194914.pdf','app/static/uploads\\registration\\grades_0123-1714_20260816194914.pdf',2.04,NULL,'student',1,1,'2026-08-16 19:50:32','2026-08-17 08:24:20','2026-08-17 08:24:20',NULL,NULL,NULL,NULL,0,NULL,NULL);
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping routines for database 'lspu_scholarhub'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-18 12:15:45
