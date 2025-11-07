<?php
/**
 * The base configuration for WordPress
 *
 * The wp-config.php creation script uses this file during the installation.
 * You don't have to use the website, you can copy this file to "wp-config.php"
 * and fill in the values.
 *
 * This file contains the following configurations:
 *
 * * Database settings
 * * Secret keys
 * * Database table prefix
 * * ABSPATH
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/
 *
 * @package WordPress
 */

// ** Database settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define( 'DB_NAME', 'u3261322_wp792' );

/** Database username */
define( 'DB_USER', 'u3261322_wp792' );

/** Database password */
define( 'DB_PASSWORD', '6G7-]41pDS' );

/** Database hostname */
define( 'DB_HOST', 'localhost' );

/** Database charset to use in creating database tables. */
define( 'DB_CHARSET', 'utf8mb4' );

/** The database collate type. Don't change this if in doubt. */
define( 'DB_COLLATE', '' );

/**#@+
 * Authentication unique keys and salts.
 *
 * Change these to different unique phrases! You can generate these using
 * the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}.
 *
 * You can change these at any point in time to invalidate all existing cookies.
 * This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
define( 'AUTH_KEY',         'yjwreyiuk9oqvqgn6lxpmmzgobjfa6osks4m08ikupod2tojjzfpvvd2hhdwwsxb' );
define( 'SECURE_AUTH_KEY',  'avmrjp1etqk0mt2osqndn73tbqmdjgtq52h24vo9exggngqvyrhmh17dlu3cutyu' );
define( 'LOGGED_IN_KEY',    'ko1pvdi1sx9fg165vzmcgalyqkchasfvrn1pfkyefxqgxy8p2a5ujndyt96uy2ot' );
define( 'NONCE_KEY',        'viu2opzmrzhlofwvux8jll1f6gohkw8jdbkmbryxnuqmmmijd6llzn0uuf0u2flr' );
define( 'AUTH_SALT',        'mfzaazwgpm9efdcqq1pkv0gyhhhhki6wriq0kvbtdqzahxubyr67i2kq1eoz59db' );
define( 'SECURE_AUTH_SALT', 'c41ohy5nmgjhsjykerhgc1ysjwr7u6wnambt0qjxq3zkpb81q8hveynvbhjeygwz' );
define( 'LOGGED_IN_SALT',   'fzzcosvonvomi9dytbmh2bbnywyp9evqiu80hnrwuatd7ckzriylntzaejijq1ay' );
define( 'NONCE_SALT',       '8s2louwlhlv57vzwjvguiu6gwvqzxgxnnp0kksfu9un3ctat3uqgpfuv2o5yvezj' );

/**#@-*/

/**
 * WordPress database table prefix.
 *
 * You can have multiple installations in one database if you give each
 * a unique prefix. Only numbers, letters, and underscores please!
 *
 * At the installation time, database tables are created with the specified prefix.
 * Changing this value after WordPress is installed will make your site think
 * it has not been installed.
 *
 * @link https://developer.wordpress.org/advanced-administration/wordpress/wp-config/#table-prefix
 */
$table_prefix = 'wpsj_';

/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 *
 * For information on other constants that can be used for debugging,
 * visit the documentation.
 *
 * @link https://developer.wordpress.org/advanced-administration/debug/debug-wordpress/
 */
define( 'WP_DEBUG', false );

/* Add any custom values between this line and the "stop editing" line. */

/* Multisite */
define( 'WP_ALLOW_MULTISITE', true );
define( 'MULTISITE', true );
define( 'SUBDOMAIN_INSTALL', false );
define( 'DOMAIN_CURRENT_SITE', 'miniden.ru' );
define( 'PATH_CURRENT_SITE', '/' );
define( 'SITE_ID_CURRENT_SITE', 1 );
define( 'BLOG_ID_CURRENT_SITE', 1 );

/* That's all, stop editing! Happy publishing. */

/** Absolute path to the WordPress directory. */
if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}

/** Sets up WordPress vars and included files. */
require_once ABSPATH . 'wp-settings.php';
