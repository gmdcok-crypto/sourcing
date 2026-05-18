CREATE TABLE IF NOT EXISTS `themes` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `theme_code` VARCHAR(100) NOT NULL,
    `theme_name` VARCHAR(255) NOT NULL,
    `display_order` INT UNSIGNED NOT NULL DEFAULT 0,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_themes_theme_code` (`theme_code`),
    UNIQUE KEY `uk_themes_theme_name` (`theme_name`),
    KEY `idx_themes_is_active` (`is_active`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
