<?php
add_action('wp_enqueue_scripts', function(){
  wp_enqueue_style('tt5-child-style', get_stylesheet_uri(), [], '1.1.0');
  wp_enqueue_style('tt5-child-custom', get_stylesheet_directory_uri().'/assets/css/custom.css', ['tt5-child-style'], '1.1.0');
  wp_add_inline_style('tt5-child-custom', ':root{--rtl:0;}');
});
add_action('after_setup_theme', function(){ add_theme_support('woocommerce'); });
