/** Config Tailwind du site (CSS compilé en site.css : npx tailwindcss@3.4.17 -i tailwind-input.css -o site.css --minify) */
module.exports = {
  content: ['./*.html', './bien/**/*.html', './*.js'],
  theme: {
    extend: {
      fontWeight: { 400: '400', 500: '500', 600: '600', 700: '700' },
      colors: {
        cream: '#FBF8F3', sand: '#F1E9DC', ecru: '#ecdbc0', ink: '#2E2410',
        brown: '#463618', cocoa: '#5c4636', muted: '#6B605C', gold: '#E0AE2C', bronze: '#8A5E1A',
      },
      fontFamily: {
        display: ['-apple-system','BlinkMacSystemFont','"SF Pro Display"','"Helvetica Neue"','"Segoe UI"','Roboto','Arial','sans-serif'],
        sans: ['-apple-system','BlinkMacSystemFont','"SF Pro Text"','"Helvetica Neue"','"Segoe UI"','Roboto','Arial','sans-serif'],
      },
    },
  },
}
