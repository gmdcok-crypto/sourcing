CREATE TABLE IF NOT EXISTS `theme_category_maps` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `theme_id` BIGINT UNSIGNED NOT NULL,
    `category_id` BIGINT UNSIGNED NOT NULL,
    `display_order` INT UNSIGNED NOT NULL DEFAULT 0,
    `is_active` TINYINT(1) NOT NULL DEFAULT 1,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_theme_category_maps_theme_category` (`theme_id`, `category_id`),
    KEY `idx_theme_category_maps_theme_id` (`theme_id`),
    KEY `idx_theme_category_maps_category_id` (`category_id`),
    CONSTRAINT `fk_theme_category_maps_theme`
        FOREIGN KEY (`theme_id`) REFERENCES `themes` (`id`),
    CONSTRAINT `fk_theme_category_maps_category`
        FOREIGN KEY (`category_id`) REFERENCES `naver_categories` (`id`)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
