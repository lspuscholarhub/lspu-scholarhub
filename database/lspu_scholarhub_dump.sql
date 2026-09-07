-- LSPU ScholarHub — Database Schema Dump
-- Updated: 2026-08-30
-- Compatible with: MariaDB 10.4+ / MySQL 8.0+
-- Use this file to set up a fresh local or production database.
--
-- Import with:
--   mysql -u root -p lspu_scholarhub < lspu_scholarhub_dump.sql
-- Or via phpMyAdmin: Import tab → select this file.

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

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: academic_periods
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `academic_periods`;
CREATE TABLE `academic_periods` (
  `id`            int(11)      NOT NULL AUTO_INCREMENT,
  `academic_year` varchar(20)  NOT NULL,
  `semester`      varchar(30)  NOT NULL,
  `is_current`    tinyint(1)   DEFAULT 0,
  `start_date`    date         DEFAULT NULL,
  `end_date`      date         DEFAULT NULL,
  `created_at`    datetime     DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_period` (`academic_year`, `semester`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: users
-- (must be created before tables that reference it)
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id`                     int(11)                              NOT NULL AUTO_INCREMENT,
  `username`               varchar(80)                          NOT NULL,
  `email`                  varchar(120)                         NOT NULL,
  `password_hash`          varchar(255)                         NOT NULL,
  `first_name`             varchar(50)                          NOT NULL,
  `last_name`              varchar(50)                          NOT NULL,
  `middle_name`            varchar(50)                          DEFAULT NULL,
  `phone_number`           varchar(20)                          DEFAULT NULL,
  `gender`                 enum('Male','Female')                DEFAULT NULL,
  `town`                   varchar(100)                         DEFAULT NULL,
  `province`               varchar(100)                         DEFAULT NULL,
  `date_of_birth`          date                                 DEFAULT NULL,
  `address`                text                                 DEFAULT NULL,
  -- Student academic fields
  `student_id`             varchar(30)                          DEFAULT NULL,
  `course`                 varchar(100)                         DEFAULT NULL,
  `year_level`             varchar(20)                          DEFAULT NULL,
  -- Registration documents (local path OR Cloudinary URL)
  `cor_file_path`          varchar(500)                         DEFAULT NULL,
  `grades_file_path`       varchar(500)                         DEFAULT NULL,
  `cor_cloudinary_id`      varchar(255)                         DEFAULT NULL,
  `grades_cloudinary_id`   varchar(255)                         DEFAULT NULL,
  `grades_semester`        varchar(50)                          DEFAULT NULL,
  `grades_updated_at`      datetime                             DEFAULT NULL,
  -- Background OCR result
  `ocr_verified`           tinyint(1)                           DEFAULT NULL,
  `ocr_result`             text                                 DEFAULT NULL,
  -- Academic monitoring
  `gwa`                    float                                DEFAULT NULL,
  `units_enrolled`         int(11)                              DEFAULT NULL,
  -- Account fields
  `user_type`              enum('student','admin','staff')      NOT NULL DEFAULT 'student',
  `is_active`              tinyint(1)                           NOT NULL DEFAULT 1,
  `is_verified`            tinyint(1)                           NOT NULL DEFAULT 0,
  `created_at`             datetime                             NOT NULL DEFAULT current_timestamp(),
  `updated_at`             datetime                             NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `last_login`             datetime                             DEFAULT NULL,
  -- Password reset
  `password_reset_token`   varchar(100)                         DEFAULT NULL,
  `password_reset_expires` datetime                             DEFAULT NULL,
  -- Phone verification
  `phone_verified`         tinyint(1)                           NOT NULL DEFAULT 0,
  `phone_otp`              varchar(10)                          DEFAULT NULL,
  `phone_otp_expires`      datetime                             DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username`             (`username`),
  UNIQUE KEY `email`                (`email`),
  UNIQUE KEY `student_id`           (`student_id`),
  UNIQUE KEY `password_reset_token` (`password_reset_token`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: audit_logs
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `audit_logs`;
CREATE TABLE `audit_logs` (
  `id`          int(11)      NOT NULL AUTO_INCREMENT,
  `user_id`     int(11)      DEFAULT NULL,
  `user_name`   varchar(120) DEFAULT NULL,
  `user_role`   varchar(20)  DEFAULT NULL,
  `action`      varchar(80)  NOT NULL,
  `category`    varchar(40)  DEFAULT NULL,
  `description` text         DEFAULT NULL,
  `target_type` varchar(40)  DEFAULT NULL,
  `target_id`   int(11)      DEFAULT NULL,
  `ip_address`  varchar(45)  DEFAULT NULL,
  `timestamp`   datetime     NOT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `audit_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: chat_history
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `chat_history`;
CREATE TABLE `chat_history` (
  `id`         int(11)                  NOT NULL AUTO_INCREMENT,
  `user_id`    int(11)                  NOT NULL,
  `role`       enum('user','model')     NOT NULL,
  `content`    text                     NOT NULL,
  `created_at` datetime                 NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `ix_chat_history_user_id` (`user_id`),
  CONSTRAINT `chat_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: scholarships
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `scholarships`;
CREATE TABLE `scholarships` (
  `id`                   int(11)                                                        NOT NULL AUTO_INCREMENT,
  `title`                varchar(200)                                                   NOT NULL,
  `category`             varchar(50)                                                    DEFAULT 'General',
  `scholarship_type`     enum('Financial Assistance','Merit Scholarship','Grant','Other') DEFAULT 'Financial Assistance',
  `funding_type`         enum('public','private')                                       NOT NULL DEFAULT 'public',
  `description`          text                                                           DEFAULT NULL,
  `eligibility_criteria` text                                                           DEFAULT NULL,
  `benefits`             text                                                           DEFAULT NULL,
  `application_deadline` datetime                                                       DEFAULT NULL,
  `award_amount`         decimal(10,2)                                                  DEFAULT NULL,
  `max_applicants`       int(11)                                                        DEFAULT NULL,
  `current_applicants`   int(11)                                                        DEFAULT 0,
  `status`               enum('active','inactive','closed')                             NOT NULL DEFAULT 'active',
  `created_by`           int(11)                                                        NOT NULL,
  `created_at`           datetime                                                       NOT NULL DEFAULT current_timestamp(),
  `updated_at`           datetime                                                       NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `is_hidden`            tinyint(1)                                                     NOT NULL DEFAULT 0,
  `allowed_student_ids`  text                                                           DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `created_by` (`created_by`),
  CONSTRAINT `scholarships_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: scholarship_batches
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `scholarship_batches`;
CREATE TABLE `scholarship_batches` (
  `id`                 int(11)                          NOT NULL AUTO_INCREMENT,
  `scholarship_id`     int(11)                          NOT NULL,
  `academic_period_id` int(11)                          NOT NULL,
  `batch_name`         varchar(50)                      NOT NULL,
  `batch_number`       float                            NOT NULL DEFAULT 1,
  `amount_per_scholar` decimal(10,2)                    DEFAULT NULL,
  `total_scholars`     int(11)                          DEFAULT 0,
  `total_male`         int(11)                          DEFAULT 0,
  `total_female`       int(11)                          DEFAULT 0,
  `total_amount`       decimal(12,2)                    DEFAULT 0.00,
  `status`             enum('open','closed','finalized') DEFAULT 'open',
  `notes`              text                             DEFAULT NULL,
  `created_by`         int(11)                          DEFAULT NULL,
  `created_at`         datetime                         DEFAULT current_timestamp(),
  `updated_at`         datetime                         DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_batch` (`scholarship_id`, `academic_period_id`, `batch_name`),
  KEY `academic_period_id` (`academic_period_id`),
  KEY `created_by`         (`created_by`),
  CONSTRAINT `scholarship_batches_ibfk_1` FOREIGN KEY (`scholarship_id`)     REFERENCES `scholarships`     (`id`) ON DELETE CASCADE,
  CONSTRAINT `scholarship_batches_ibfk_2` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods` (`id`),
  CONSTRAINT `scholarship_batches_ibfk_3` FOREIGN KEY (`created_by`)         REFERENCES `users`            (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: scholarship_applications
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `scholarship_applications`;
CREATE TABLE `scholarship_applications` (
  `id`                    int(11)                                                             NOT NULL AUTO_INCREMENT,
  `scholarship_id`        int(11)                                                             NOT NULL,
  `applicant_id`          int(11)                                                             NOT NULL,
  `application_data`      longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin                 DEFAULT NULL CHECK (json_valid(`application_data`)),
  `documents`             longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin                 DEFAULT NULL CHECK (json_valid(`documents`)),
  `status`                enum('pending','under_review','approved','rejected','withdrawn')    NOT NULL DEFAULT 'pending',
  `scholar_tag`           enum('active','at_risk','probation','inactive')                    DEFAULT 'active',
  `submitted_at`          datetime                                                            NOT NULL DEFAULT current_timestamp(),
  `reviewed_at`           datetime                                                            DEFAULT NULL,
  `reviewed_by`           int(11)                                                             DEFAULT NULL,
  `review_notes`          text                                                                DEFAULT NULL,
  `final_decision_date`   datetime                                                            DEFAULT NULL,
  `approved_at`           datetime                                                            DEFAULT NULL,
  `scholar_status`        varchar(30)                                                         DEFAULT 'active',
  `compliance_status`     varchar(20)                                                         DEFAULT 'compliant',
  `last_compliance_check` datetime                                                            DEFAULT NULL,
  `status_updated_at`     datetime                                                            DEFAULT NULL,
  `renewal_notified_at`   datetime                                                            DEFAULT NULL,
  `is_active`             tinyint(1)                                                          DEFAULT 1,
  `batch_id`              int(11)                                                             DEFAULT NULL,
  `academic_period_id`    int(11)                                                             DEFAULT NULL,
  `amount_received`       decimal(10,2)                                                       DEFAULT NULL,
  `seq_number`            int(11)                                                             DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `scholarship_id`    (`scholarship_id`),
  KEY `applicant_id`      (`applicant_id`),
  KEY `reviewed_by`       (`reviewed_by`),
  KEY `batch_id`          (`batch_id`),
  KEY `academic_period_id`(`academic_period_id`),
  CONSTRAINT `scholarship_applications_ibfk_1` FOREIGN KEY (`scholarship_id`)     REFERENCES `scholarships`      (`id`),
  CONSTRAINT `scholarship_applications_ibfk_2` FOREIGN KEY (`applicant_id`)       REFERENCES `users`             (`id`),
  CONSTRAINT `scholarship_applications_ibfk_3` FOREIGN KEY (`reviewed_by`)        REFERENCES `users`             (`id`),
  CONSTRAINT `scholarship_applications_ibfk_4` FOREIGN KEY (`batch_id`)           REFERENCES `scholarship_batches`(`id`) ON DELETE SET NULL,
  CONSTRAINT `scholarship_applications_ibfk_5` FOREIGN KEY (`academic_period_id`) REFERENCES `academic_periods`  (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: documents
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `documents`;
CREATE TABLE `documents` (
  `id`                   int(11)      NOT NULL AUTO_INCREMENT,
  `user_id`              int(11)      NOT NULL,
  `application_id`       int(11)      DEFAULT NULL,
  `original_filename`    varchar(255) NOT NULL,
  `stored_filename`      varchar(255) NOT NULL,
  `file_path`            varchar(500) NOT NULL,
  `file_size`            int(11)      DEFAULT NULL,
  `category`             varchar(50)  DEFAULT NULL,
  `file_type`            varchar(10)  DEFAULT NULL,
  `description`          varchar(255) DEFAULT NULL,
  `is_verified`          tinyint(1)   NOT NULL DEFAULT 0,
  `ctc_detected`         tinyint(1)   DEFAULT NULL,
  `uploaded_at`          datetime     NOT NULL DEFAULT current_timestamp(),
  `updated_at`           datetime     DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  -- Cloudinary cloud storage
  `cloudinary_url`       varchar(500) DEFAULT NULL,
  `cloudinary_public_id` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `stored_filename` (`stored_filename`),
  KEY `user_id`        (`user_id`),
  KEY `application_id` (`application_id`),
  CONSTRAINT `documents_ibfk_1` FOREIGN KEY (`user_id`)        REFERENCES `users`                  (`id`),
  CONSTRAINT `documents_ibfk_2` FOREIGN KEY (`application_id`) REFERENCES `scholarship_applications`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: gwa_history
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `gwa_history`;
CREATE TABLE `gwa_history` (
  `id`          int(11)      NOT NULL AUTO_INCREMENT,
  `student_id`  int(11)      NOT NULL,
  `gwa`         float        NOT NULL,
  `semester`    varchar(30)  NOT NULL,
  `school_year` varchar(20)  NOT NULL,
  `recorded_by` int(11)      DEFAULT NULL,
  `notes`       varchar(255) DEFAULT NULL,
  `recorded_at` datetime     NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `student_id`  (`student_id`),
  KEY `recorded_by` (`recorded_by`),
  CONSTRAINT `gwa_history_ibfk_1` FOREIGN KEY (`student_id`)  REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `gwa_history_ibfk_2` FOREIGN KEY (`recorded_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE: notifications
-- ─────────────────────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
  `id`                  int(11)      NOT NULL AUTO_INCREMENT,
  `recipient_id`        int(11)      NOT NULL,
  `title`               varchar(200) NOT NULL,
  `message`             text         NOT NULL,
  `notification_type`   enum(
                          'APPLICATION_SUBMITTED',
                          'APPLICATION_APPROVED',
                          'APPLICATION_REJECTED',
                          'DEADLINE_REMINDER',
                          'NEW_SCHOLARSHIP',
                          'SYSTEM_ANNOUNCEMENT'
                        )            NOT NULL,
  `channel`             enum('EMAIL','SMS','IN_APP','PUSH') NOT NULL DEFAULT 'IN_APP',
  `is_read`             tinyint(1)   NOT NULL DEFAULT 0,
  `sent_at`             datetime     NOT NULL DEFAULT current_timestamp(),
  `read_at`             datetime     DEFAULT NULL,
  `related_entity_type` varchar(50)  DEFAULT NULL,
  `related_entity_id`   int(11)      DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `recipient_id` (`recipient_id`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`recipient_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ─────────────────────────────────────────────────────────────────────────────
-- Default admin account
-- Password: Admin@1234  (change after first login)
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO `users` (
  `username`, `email`, `password_hash`,
  `first_name`, `last_name`,
  `user_type`, `is_active`, `is_verified`,
  `created_at`, `updated_at`
) VALUES (
  'admin',
  'admin@lspu-scholarhub.edu',
  'REDACTED_ADMIN_HASH',
  'Admin', 'User',
  'admin', 1, 1,
  NOW(), NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Restore settings
-- ─────────────────────────────────────────────────────────────────────────────
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- ─────────────────────────────────────────────────────────────────────────────
-- Schema version: 2026-08-30
-- Changes from previous version:
--   users      → added cor_cloudinary_id, grades_cloudinary_id,
--                         ocr_verified, ocr_result
--   documents  → added cloudinary_url, cloudinary_public_id
--   scholarships → description/eligibility_criteria/benefits now nullable
--                  application_deadline now nullable
--   All tables → consistent DEFAULT values and comments
-- ─────────────────────────────────────────────────────────────────────────────
