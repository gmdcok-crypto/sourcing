CREATE TABLE IF NOT EXISTS `naver_categories` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `cid` VARCHAR(20) NOT NULL,
    `category_name` VARCHAR(255) NOT NULL,
    `full_path` VARCHAR(1000) NOT NULL,
    `depth` TINYINT UNSIGNED NOT NULL,
    `parent_cid` VARCHAR(20) DEFAULT NULL,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_naver_categories_cid` (`cid`),
    KEY `idx_naver_categories_parent_cid` (`parent_cid`),
    KEY `idx_naver_categories_is_active` (`is_active`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
