-- LSPU ScholarHub - Database Schema (structure only, no data)
-- Updated: 2026-11-24
-- Compatible with: MariaDB 10.4+ / MySQL 8.0+
--
-- Import into an empty database:
--   mysql -u root -p lspu_scholarhub < database/lspu_scholarhub_dump.sql
--
-- This file is a schema snapshot, not a seed: it contains no accounts,
-- applications or uploaded files. Seed demo data with:
--   python scripts/dev/seed_database.py
--
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
  `me_form_deadline` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_period` (`academic_year`,`semester`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `campus_form_submissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `campus_form_submissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `form_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `academic_period_id` int(11) DEFAULT NULL,
  `original_filename` varchar(255) NOT NULL,
  `file_url` varchar(500) DEFAULT NULL,
  `cloudinary_public_id` varchar(255) DEFAULT NULL,
  `local_path` varchar(500) DEFAULT NULL,
  `file_type` varchar(10) DEFAULT NULL,
  `file_size` int(11) DEFAULT NULL,
  `uploaded_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `form_id` (`form_id`),
  KEY `user_id` (`user_id`),
  KEY `academic_period_id` (`academic_period_id`),
  CONSTRAINT `campus_form_submissions_ibfk_1` FOREIGN KEY (`form_id`) REFERENCES `campus_forms` (`id`) ON DELETE CASCADE,
  CONSTRAINT `campus_form_submissions_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `campus_form_submissions_ibfk_3` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `campus_forms`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `campus_forms` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `campus_id` int(11) NOT NULL,
  `academic_period_id` int(11) DEFAULT NULL,
  `title` varchar(150) NOT NULL,
  `instructions` varchar(255) DEFAULT NULL,
  `template_url` varchar(500) DEFAULT NULL,
  `template_filename` varchar(255) DEFAULT NULL,
  `template_file_url` varchar(500) DEFAULT NULL,
  `template_local_path` varchar(500) DEFAULT NULL,
  `template_cloudinary_public_id` varchar(255) DEFAULT NULL,
  `due_date` date DEFAULT NULL,
  `is_required` tinyint(1) NOT NULL,
  `sort_order` int(11) NOT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `campus_id` (`campus_id`),
  KEY `academic_period_id` (`academic_period_id`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `campus_forms_ibfk_1` FOREIGN KEY (`campus_id`) REFERENCES `campuses` (`id`) ON DELETE CASCADE,
  CONSTRAINT `campus_forms_ibfk_2` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`) ON DELETE SET NULL,
  CONSTRAINT `campus_forms_ibfk_3` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `campuses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `campuses` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `short_name` varchar(30) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
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
  `cloudinary_url` varchar(500) DEFAULT NULL,
  `cloudinary_public_id` varchar(255) DEFAULT NULL,
  `campus_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `stored_filename` (`stored_filename`),
  KEY `user_id` (`user_id`),
  KEY `application_id` (`application_id`),
  CONSTRAINT `documents_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `documents_ibfk_2` FOREIGN KEY (`application_id`) REFERENCES `scholarship_applications` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
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
DROP TABLE IF EXISTS `monitoring_submissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `monitoring_submissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `application_id` int(11) NOT NULL,
  `academic_period_id` int(11) DEFAULT NULL,
  `original_filename` varchar(255) NOT NULL,
  `file_url` varchar(500) DEFAULT NULL,
  `cloudinary_public_id` varchar(255) DEFAULT NULL,
  `local_path` varchar(500) DEFAULT NULL,
  `file_type` varchar(10) DEFAULT NULL,
  `file_size` int(11) DEFAULT NULL,
  `uploaded_at` datetime NOT NULL,
  `campus_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `application_id` (`application_id`),
  KEY `academic_period_id` (`academic_period_id`),
  CONSTRAINT `monitoring_submissions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `monitoring_submissions_ibfk_2` FOREIGN KEY (`application_id`) REFERENCES `scholarship_applications` (`id`),
  CONSTRAINT `monitoring_submissions_ibfk_3` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
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
  `campus_id` int(11) DEFAULT NULL,
  `academic_period_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `recipient_id` (`recipient_id`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`recipient_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `portal_sync_runs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `portal_sync_runs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `started_at` datetime NOT NULL,
  `finished_at` datetime DEFAULT NULL,
  `trigger` varchar(30) NOT NULL,
  `mode` varchar(20) NOT NULL,
  `status` varchar(20) NOT NULL,
  `seen` int(11) NOT NULL,
  `created` int(11) NOT NULL,
  `updated` int(11) NOT NULL,
  `unchanged` int(11) NOT NULL,
  `skipped` int(11) NOT NULL,
  `failed` int(11) NOT NULL,
  `error` text DEFAULT NULL,
  `details` text DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `requirement_submissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `requirement_submissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `requirement_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `application_id` int(11) DEFAULT NULL,
  `academic_period_id` int(11) DEFAULT NULL,
  `original_filename` varchar(255) NOT NULL,
  `file_url` varchar(500) DEFAULT NULL,
  `cloudinary_public_id` varchar(255) DEFAULT NULL,
  `local_path` varchar(500) DEFAULT NULL,
  `file_type` varchar(10) DEFAULT NULL,
  `file_size` int(11) DEFAULT NULL,
  `status` varchar(20) NOT NULL,
  `remarks` varchar(255) DEFAULT NULL,
  `uploaded_at` datetime NOT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `reviewed_by` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `requirement_id` (`requirement_id`),
  KEY `user_id` (`user_id`),
  KEY `application_id` (`application_id`),
  KEY `academic_period_id` (`academic_period_id`),
  KEY `reviewed_by` (`reviewed_by`),
  CONSTRAINT `requirement_submissions_ibfk_1` FOREIGN KEY (`requirement_id`) REFERENCES `scholarship_requirements` (`id`) ON DELETE CASCADE,
  CONSTRAINT `requirement_submissions_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `requirement_submissions_ibfk_3` FOREIGN KEY (`application_id`) REFERENCES `scholarship_applications` (`id`),
  CONSTRAINT `requirement_submissions_ibfk_4` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`),
  CONSTRAINT `requirement_submissions_ibfk_5` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `scholarship_applications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `scholarship_applications` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `scholarship_id` int(11) NOT NULL,
  `applicant_id` int(11) NOT NULL,
  `application_data` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `documents` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
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
  `campus_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `scholarship_id` (`scholarship_id`),
  KEY `applicant_id` (`applicant_id`),
  KEY `reviewed_by` (`reviewed_by`),
  KEY `batch_id` (`batch_id`),
  KEY `academic_period_id` (`academic_period_id`),
  KEY `campus_id` (`campus_id`),
  CONSTRAINT `scholarship_applications_ibfk_1` FOREIGN KEY (`scholarship_id`) REFERENCES `scholarships` (`id`),
  CONSTRAINT `scholarship_applications_ibfk_2` FOREIGN KEY (`applicant_id`) REFERENCES `users` (`id`),
  CONSTRAINT `scholarship_applications_ibfk_3` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`),
  CONSTRAINT `scholarship_applications_ibfk_4` FOREIGN KEY (`batch_id`) REFERENCES `scholarship_batches` (`id`) ON DELETE SET NULL,
  CONSTRAINT `scholarship_applications_ibfk_5` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`),
  CONSTRAINT `scholarship_applications_ibfk_6` FOREIGN KEY (`campus_id`) REFERENCES `campuses` (`id`) ON DELETE SET NULL,
  CONSTRAINT `scholarship_applications_chk_1` CHECK (json_valid(`application_data`)),
  CONSTRAINT `scholarship_applications_chk_2` CHECK (json_valid(`documents`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
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
  `campus_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_batch` (`scholarship_id`,`academic_period_id`,`batch_name`),
  UNIQUE KEY `uq_scholarship_batches_number` (`scholarship_id`,`academic_period_id`,`batch_number`),
  KEY `academic_period_id` (`academic_period_id`),
  KEY `created_by` (`created_by`),
  KEY `campus_id` (`campus_id`),
  CONSTRAINT `scholarship_batches_ibfk_1` FOREIGN KEY (`scholarship_id`) REFERENCES `scholarships` (`id`) ON DELETE CASCADE,
  CONSTRAINT `scholarship_batches_ibfk_2` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`),
  CONSTRAINT `scholarship_batches_ibfk_3` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL,
  CONSTRAINT `scholarship_batches_ibfk_4` FOREIGN KEY (`campus_id`) REFERENCES `campuses` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `scholarship_requirements`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `scholarship_requirements` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `scholarship_id` int(11) NOT NULL,
  `title` varchar(150) NOT NULL,
  `instructions` varchar(255) DEFAULT NULL,
  `due_date` date DEFAULT NULL,
  `is_required` tinyint(1) NOT NULL,
  `sort_order` int(11) NOT NULL,
  `created_by` int(11) DEFAULT NULL,
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `scholarship_id` (`scholarship_id`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `scholarship_requirements_ibfk_1` FOREIGN KEY (`scholarship_id`) REFERENCES `scholarships` (`id`) ON DELETE CASCADE,
  CONSTRAINT `scholarship_requirements_ibfk_2` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `scholarships`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `scholarships` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `title` varchar(200) NOT NULL,
  `category` varchar(50) DEFAULT 'General',
  `scholarship_type` enum('Financial Assistance','Merit Scholarship','Grant','Other') DEFAULT 'Financial Assistance',
  `funding_type` enum('public','private') NOT NULL DEFAULT 'public',
  `description` text DEFAULT NULL,
  `eligibility_criteria` text DEFAULT NULL,
  `benefits` text DEFAULT NULL,
  `application_deadline` datetime DEFAULT NULL,
  `award_amount` decimal(10,2) DEFAULT NULL,
  `max_applicants` int(11) DEFAULT NULL,
  `current_applicants` int(11) DEFAULT NULL,
  `status` enum('ACTIVE','INACTIVE','CLOSED') NOT NULL,
  `created_by` int(11) NOT NULL,
  `created_at` datetime NOT NULL,
  `updated_at` datetime NOT NULL,
  `is_hidden` tinyint(1) NOT NULL DEFAULT 0,
  `allowed_student_ids` text DEFAULT NULL,
  `custom_form_fields` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`custom_form_fields`)),
  `campus_id` int(11) DEFAULT NULL,
  `scope` enum('campus','university') NOT NULL DEFAULT 'campus',
  `academic_period_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `created_by` (`created_by`),
  KEY `campus_id` (`campus_id`),
  CONSTRAINT `scholarships_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`),
  CONSTRAINT `scholarships_ibfk_2` FOREIGN KEY (`campus_id`) REFERENCES `campuses` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `user_campuses`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `user_campuses` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `campus_id` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_campus` (`user_id`,`campus_id`),
  KEY `campus_id` (`campus_id`),
  CONSTRAINT `user_campuses_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `user_campuses_ibfk_2` FOREIGN KEY (`campus_id`) REFERENCES `campuses` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
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
  `user_type` enum('student','admin','staff','super_admin') NOT NULL DEFAULT 'student',
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
  `ocr_verified` tinyint(1) DEFAULT NULL,
  `ocr_result` text DEFAULT NULL,
  `cor_cloudinary_id` varchar(255) DEFAULT NULL,
  `grades_cloudinary_id` varchar(255) DEFAULT NULL,
  `campus_id` int(11) DEFAULT NULL,
  `is_existing_scholar` tinyint(1) NOT NULL DEFAULT 0,
  `existing_scholarship_name` varchar(150) DEFAULT NULL,
  `must_change_password` tinyint(1) NOT NULL DEFAULT 0,
  `student_status` varchar(20) NOT NULL DEFAULT 'active',
  `status_date` date DEFAULT NULL,
  `portal_student_id` varchar(30) DEFAULT NULL,
  `portal_synced_at` datetime DEFAULT NULL,
  `data_source` varchar(20) NOT NULL DEFAULT 'self_registered',
  `is_archived` tinyint(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `student_id` (`student_id`),
  UNIQUE KEY `password_reset_token` (`password_reset_token`),
  KEY `campus_id` (`campus_id`),
  KEY `ix_users_portal_student_id` (`portal_student_id`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`campus_id`) REFERENCES `campuses` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
